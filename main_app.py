"""RunSync: Strava, Google Sheets und Garmin Connect abgleichen.

Zwei Wege, je nachdem wo das Training dokumentiert wird:

1. Klassisch, Strava ist die Quelle (Titel, Beschreibung, private Notiz, Schuhe auf Strava):
   update_sheets_data   Strava -> Sheet, ab dem ersten leeren Tag
   update_p4_p7         Yoga- und Workout-Anzahl pro Woche in P7/P4
   transfer_to_garmin   Strava -> Garmin (Titel, Beschreibung, Schuhe)

2. Telegram, Lukas schickt die Details an den Bot:
   new_activity         neue Strava-Aktivitaet: Kilometer bzw. Minuten sofort ins Sheet
   log_run              "was, welche Schuhe, Gedanken" -> Sheet (Hauptzelle, Notiz), Garmin (Beschreibung, Schuhe),
                        Strava (Schuhe, private Notiz; nichts Oeffentliches)
   undocumented_runs    Laeufe der letzten Tage, bei denen im Sheet Hauptzelle oder Notiz fehlt

Aufruf lokal: python main_app.py update_sheets_data | update_p4_p7 | transfer_to_garmin [tage] | seed_ledger
"""
import re
import sys
import time
from datetime import datetime, timedelta

import sheets_client as sheets_ledger
import shoes
from garmin_client import GarminClient, GarminError
from sheets_client import SheetsClient, activity_date
from strava_client import StravaClient

RUN_TYPES = ("Run", "TrailRun", "VirtualRun")
# Automatische Strava-Namen ("Morning Run") nicht nach Garmin uebertragen
DEFAULT_NAME = re.compile(r"^(Morning|Afternoon|Evening|Lunch|Night) [A-Za-z ]+$")


class RunSyncError(Exception):
    def __init__(self, error_type, message, **details):
        super().__init__(message)
        self.error_type = error_type
        self.details = details


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def is_run(activity):
    return activity["sport_type"] in RUN_TYPES


def run_info(activity):
    start = activity_date(activity)
    return {
        "strava_id": activity["id"],
        "start_local": start.isoformat(),
        "daytime": "morning" if start.hour < 13 else "afternoon",
        "distance_km": round(activity["distance"] / 1000, 2),
        "moving_minutes": round(activity["moving_time"] / 60),
    }


# ---------- Klassisch: Strava ist die Quelle ----------

def update_sheets_data(sheets_client, strava_client):
    """Alle Aktivitaeten ab dem ersten noch leeren Tag ins Sheet (ohne Yoga), aelteste zuerst."""
    start = sheets_client.get_first_not_completed_day()
    activities = strava_client.get_all_activities_in_timeframe(fmt(start), fmt(datetime.now()))
    added = 0
    for activity in reversed([a for a in activities if a["sport_type"] != "Yoga"]):
        details = strava_client.get_activity(activity["id"])
        added += sheets_client.set_new_entry_from_json(details)
    return {"from": start.date().isoformat(), "found": len(activities), "added": added}


def seed_ledger(sheets_client, strava_client, since="2020-01-01"):
    """Einmalig beim Umstieg: alles vor dem ersten leeren Tag gilt als schon im Sheet."""
    until = sheets_client.get_first_not_completed_day()
    activities = strava_client.get_all_activities_in_timeframe(f"{since} 00:00:00", fmt(until))
    with sheets_ledger.ledger_lock:
        ledger = sheets_ledger.load_ledger()
        for a in activities:
            ledger["activities"].setdefault(str(a["id"]), {"seeded": True})
        sheets_ledger.save_ledger(ledger)
    return {"until": until.isoformat(), "marked": len(activities)}


def update_p4_p7(sheets_client, strava_client):
    """P7 = Anzahl Yoga, P4 = Anzahl Workouts in abgeschlossenen Wochen ohne Werte."""
    done = []
    for ws in sheets_client.get_empty_p4_p7_worksheets() or []:
        parts = ws.acell("B1").value.split()
        start = datetime.strptime(parts[3], "%d.%m.%Y")
        end = datetime.strptime(parts[5], "%d.%m.%Y").replace(hour=23, minute=59, second=59)
        if end > datetime.now():
            continue
        activities = strava_client.get_all_activities_in_timeframe(fmt(start), fmt(end))
        yoga = sum(a["sport_type"] == "Yoga" for a in activities)
        workout = sum(a["sport_type"] == "Workout" for a in activities)
        ws.batch_update([{"range": "P7", "values": [[yoga]]}, {"range": "P4", "values": [[workout]]}])
        done.append({"sheet": ws.title, "yoga": yoga, "workout": workout})
        print(f"{ws.title}: P7={yoga}, P4={workout}")
    return {"weeks": done}


def transfer_to_garmin(strava_client, garmin_client, days=14, stop_at_transferred=True):
    """Titel, Beschreibung und Schuhe von Strava nach Garmin, neueste zuerst.

    Mit stop_at_transferred endet der Lauf bei der ersten Aktivitaet, deren Titel auf Garmin schon stimmt.
    """
    end = datetime.now()
    activities = strava_client.get_all_activities_in_timeframe(fmt(end - timedelta(days=days)), fmt(end))
    transferred, skipped = [], 0
    for activity in activities:
        start = activity_date(activity)
        name = activity["name"] if not DEFAULT_NAME.match(activity["name"]) else None
        details = strava_client.get_activity(activity["id"])
        description = details.get("description") or None
        shoe = shoes.by_strava_id(details.get("gear_id"))
        gear_uuid = shoe["garmin"] if shoe else None
        if not (name or description or gear_uuid):
            skipped += 1
            continue

        garmin = next((g for g in garmin_client.get_activities(start.date().isoformat())
                       if abs((datetime.fromisoformat(g["start_local"]) - start).total_seconds()) <= 60), None)
        if garmin is None:
            print(f"{start}: keine Garmin-Aktivitaet gefunden")
            skipped += 1
            continue
        if stop_at_transferred and name and garmin["name"] == name:
            print(f"{start}: schon uebertragen ('{name}'), Ende")
            break
        result = garmin_client.update_activity(start.isoformat(), name=name, description=description, gear_uuid=gear_uuid)
        transferred.append({"start_local": start.isoformat(), "name": result["name"], "shoe": shoe["name"] if shoe else None})
        print(f"{start}: '{result['name']}' uebertragen")
        time.sleep(1)
    return {"transferred": transferred, "skipped": skipped}


# ---------- Telegram: Lukas schickt die Details ----------

def new_activity(sheets_client, strava_client, activity_id):
    """Neue Strava-Aktivitaet (Webhook): Zahl sofort ins Sheet. Bei Laeufen kommen die Texte spaeter per log_run."""
    activity = strava_client.get_activity(activity_id)
    info = run_info(activity) | {"sport_type": activity["sport_type"], "is_run": is_run(activity)}
    if activity["sport_type"] == "Yoga":
        return info | {"sheet": "skipped"}
    added = sheets_client.set_new_entry_from_json(activity, with_run_texts=False)
    return info | {"sheet": "added" if added else "already"}


def undocumented_runs(sheets_client, strava_client, days=14):
    """Halbtage mit Laeufen der letzten Tage, bei denen im Sheet Hauptzelle oder Notiz leer ist, aelteste zuerst."""
    end = datetime.now()
    found = strava_client.get_all_activities_in_timeframe(fmt(end - timedelta(days=days)), fmt(end))
    blocks = {}
    for activity in sorted((a for a in found if is_run(a)), key=lambda a: a["start_date_local"]):
        info = run_info(activity)
        blocks.setdefault((info["start_local"][:10], info["daytime"]), []).append(info)
    result = []
    for (date, daytime), runs in blocks.items():
        cells = sheets_client.read_run_cells(runs[0]["start_local"])
        # Ohne Kilometer in diesem Block steht der Lauf woanders (von Hand verschoben), dann nicht melden
        if not str(cells["run_value"] or "").strip():
            continue
        missing = [name for name, key in (("what", "run_text"), ("thoughts", "notes")) if not (cells[key] or "").strip()]
        if missing:
            result.append({"date": date, "daytime": daytime, "distance_km": round(sum(r["distance_km"] for r in runs), 2),
                           "strava_ids": [r["strava_id"] for r in runs], "missing": missing})
    return {"days": days, "undocumented": result}


def find_runs(strava_client, date=None, daytime=None, strava_ids=None):
    """Laeufe eines Tagesblocks. Alle muessen im selben Block liegen, sonst ist unklar, welche gemeint sind."""
    if strava_ids:
        runs = [a for a in (strava_client.get_activity(i) for i in strava_ids) if is_run(a)]
    else:
        if not date:
            raise RunSyncError("bad_request", "date oder strava_ids fehlt")
        day = datetime.strptime(date, "%Y-%m-%d")
        # Strava filtert nach UTC, deshalb mit Puffer holen und dann nach Ortszeit filtern
        found = strava_client.get_all_activities_in_timeframe(fmt(day - timedelta(days=1)), fmt(day + timedelta(days=2)))
        runs = [a for a in found if is_run(a) and a["start_date_local"][:10] == date]
        if daytime in ("morning", "afternoon"):
            matching = [a for a in runs if run_info(a)["daytime"] == daytime]
            if not matching:
                raise RunSyncError("run_not_found", f"Kein Lauf am {date} ({daytime})", runs_that_day=[run_info(a) for a in runs])
            runs = matching
    if not runs:
        raise RunSyncError("run_not_found", f"Kein Lauf gefunden ({date or strava_ids})")
    runs.sort(key=lambda a: a["start_date_local"])
    infos = [run_info(a) for a in runs]
    if len({(i["start_local"][:10], i["daytime"]) for i in infos}) > 1:
        raise RunSyncError("ambiguous_run", "Die Laeufe liegen in verschiedenen Tagesbloecken, bitte daytime angeben", runs_that_day=infos)
    return runs


def log_run(sheets_client, strava_client, garmin_client, date=None, daytime=None, strava_ids=None,
            what=None, shoe=None, thoughts=None):
    """Details zu den Laeufen eines Tagesblocks (Vormittag oder Nachmittag) ueberall eintragen.

    Leere Felder bleiben unveraendert. Jedes Ziel wird einzeln versucht, das Ergebnis meldet, was geklappt hat.
    """
    what, thoughts = (what or "").strip() or None, (thoughts or "").strip() or None
    shoe_entry = None
    if shoe:
        shoe_entry, options = shoes.resolve(shoe)
        if options:
            raise RunSyncError("ambiguous_shoe", f"Schuh '{shoe}' ist nicht eindeutig", options=options)
        if not shoe_entry:
            raise RunSyncError("unknown_shoe", f"Schuh '{shoe}' ist unbekannt, mit add_shoe anlegen")
    runs = find_runs(strava_client, date, daytime, strava_ids)
    infos = [run_info(a) for a in runs]
    garmin_gear = shoe_entry["garmin"] if shoe_entry else None
    strava_gear = shoe_entry["strava"] if shoe_entry else None
    result = {"runs": infos, "shoe": shoe_entry["name"] if shoe_entry else None, "garmin": [], "strava": [], "notes": []}

    try:
        for activity in runs:
            sheets_client.set_new_entry_from_json(activity, with_run_texts=False)
        result["sheet"] = {"ok": True, **sheets_client.set_run_texts(infos[0]["start_local"], what, thoughts)}
    except Exception as e:
        result["sheet"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}

    for info in infos:
        if what or garmin_gear:
            try:
                garmin_client.update_activity(info["start_local"], description=what, gear_uuid=garmin_gear)
                result["garmin"].append({"start_local": info["start_local"], "ok": True})
            except GarminError as e:
                result["garmin"].append({"start_local": info["start_local"], "ok": False, "error_type": e.error_type, "error": str(e)[:300]})

        fields = {k: v for k, v in {"gear_id": strava_gear, "private_note": thoughts}.items() if v}
        if fields:
            try:
                strava_client.update_activity(info["strava_id"], **fields)
                result["strava"].append({"strava_id": info["strava_id"], "ok": True})
            except Exception as e:
                result["strava"].append({"strava_id": info["strava_id"], "ok": False, "error": f"{type(e).__name__}: {e}"[:300]})

    if shoe_entry and not garmin_gear:
        result["notes"].append(f"{shoe_entry['name']} gibt es auf Garmin nicht, dort wurde kein Schuh gesetzt. add_shoe kann ihn ergaenzen.")
    if shoe_entry and not strava_gear:
        result["notes"].append(f"{shoe_entry['name']} gibt es auf Strava nicht, dort wurde kein Schuh gesetzt. add_shoe kann ihn ergaenzen.")
    result["ok"] = result["sheet"]["ok"] and all(r["ok"] for r in result["garmin"] + result["strava"])
    return result


def add_shoe(strava_client, garmin_client, name):
    """Neuen Schuh aufnehmen oder einen bekannten auf der fehlenden Seite ergaenzen.

    Garmin: passenden, noch nicht zugeordneten Schuh verknuepfen, sonst neu anlegen.
    Strava: passenden, noch nicht zugeordneten Schuh verknuepfen. Anlegen geht ueber die Strava-API nicht,
    dann muss Lukas ihn in der Strava-App anlegen und add_shoe erneut aufrufen.
    """
    name = " ".join(name.split())
    if len(shoes.words(name)) < 2:
        raise RunSyncError("bad_request", "Bitte Marke und Modell nennen, z.B. 'Nike Pegasus 41 Black'")
    all_shoes = shoes.load_shoes()
    entry = next((s for s in all_shoes if s["name"].lower() == name.lower()), None)
    if entry is None:
        entry = {"name": name, "garmin": None, "strava": None}
        all_shoes.append(entry)
    result = {"name": entry["name"]}

    if entry["garmin"]:
        result["garmin"] = "already"
    else:
        taken = {s["garmin"] for s in all_shoes if s["garmin"]}
        free = {g["name"]: g["uuid"] for g in garmin_client.get_shoes() if g["uuid"] not in taken and g["name"]}
        match, _ = shoes.best(entry["name"], list(free), minimum=2)
        if match:
            entry["garmin"], result["garmin"] = free[match], f"linked to '{match}'"
        else:
            brand, model = entry["name"].split(" ", 1)
            entry["garmin"], result["garmin"] = garmin_client.create_shoe(brand, model, entry["name"])["uuid"], "created"

    if entry["strava"]:
        result["strava"] = "already"
    else:
        taken = {s["strava"] for s in all_shoes if s["strava"]}
        free = {s["name"]: s["id"] for s in strava_client.get_shoes() if s["id"] not in taken and not s.get("retired")}
        match, _ = shoes.best(entry["name"], list(free), minimum=2)
        if match:
            entry["strava"], result["strava"] = free[match], f"linked to '{match}'"
        else:
            result["strava"] = "missing"
            result["note"] = ("Strava erlaubt Apps nicht, Schuhe anzulegen. Lukas muss ihn in der Strava-App anlegen "
                              "(Profil > Ausruestung), danach add_shoe erneut aufrufen, um ihn zu verknuepfen.")

    shoes.save_shoes(all_shoes)
    return result


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    if task == "update_sheets_data":
        print(update_sheets_data(SheetsClient(), StravaClient()))
    elif task == "update_p4_p7":
        print(update_p4_p7(SheetsClient(), StravaClient()))
    elif task == "seed_ledger":
        print(seed_ledger(SheetsClient(), StravaClient()))
    elif task == "transfer_to_garmin":
        print(transfer_to_garmin(StravaClient(), GarminClient(), days=int(sys.argv[2]) if len(sys.argv) > 2 else 14))
    else:
        print(__doc__)

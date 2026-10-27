"""RunSync: keep Strava, Google Sheets and Garmin Connect in sync.

Two workflows, depending on where the training is documented:

1. Classic, Strava is the source (title, description, private note, shoes on Strava):
   update_sheets_data   Strava -> sheet, starting at the first empty day
   update_p4_p7         number of yoga and workout sessions per week in P7/P4
   transfer_to_garmin   Strava -> Garmin (title, description, shoes)

2. Telegram, the details are sent to the bot:
   new_activity         new Strava activity: kilometers or minutes go into the sheet right away
   log_run              "what, which shoes, thoughts" -> sheet (main cell, notes), Garmin (description, shoes),
                        Strava (shoes, private note, description in neutral words if it is empty)
   workout_preview      intervals: find the reps in the watch laps, show the Strava description and lactate rows
   workout_apply        after the athlete confirmed: Strava description with splits, rows in the lactate sheet
   undocumented_runs    recent runs whose main cell or notes are still empty in the sheet

Local usage: python main_app.py update_sheets_data | update_p4_p7 | transfer_to_garmin [days] | seed_ledger
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta

import sheets_client as sheets_ledger
import shoes
import workout as workouts
from garmin_client import GarminClient, GarminError
from sheets_client import SheetsClient, activity_date
from strava_client import StravaClient
from lactate_client import LactateClient

RUN_TYPES = ("Run", "TrailRun", "VirtualRun")
# Runs with at most this break in between belong to one training (e.g. warm-up on the treadmill, then outside)
SAME_TRAINING_GAP = timedelta(minutes=20)
# Don't copy Strava's automatic names ("Morning Run") to Garmin
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


# ---------- Classic: Strava is the source ----------

def update_sheets_data(sheets_client, strava_client):
    """All activities since the first empty day go into the sheet (except yoga), oldest first."""
    start = sheets_client.get_first_not_completed_day()
    activities = strava_client.get_all_activities_in_timeframe(fmt(start), fmt(datetime.now()))
    added = 0
    for activity in reversed([a for a in activities if a["sport_type"] != "Yoga"]):
        details = strava_client.get_activity(activity["id"])
        added += sheets_client.set_new_entry_from_json(details)
    return {"from": start.date().isoformat(), "found": len(activities), "added": added}


def seed_ledger(sheets_client, strava_client, since="2020-01-01"):
    """One-off when switching over: everything before the first empty day counts as already in the sheet."""
    until = sheets_client.get_first_not_completed_day()
    activities = strava_client.get_all_activities_in_timeframe(f"{since} 00:00:00", fmt(until))
    with sheets_ledger.ledger_lock:
        ledger = sheets_ledger.load_ledger()
        for a in activities:
            ledger["activities"].setdefault(str(a["id"]), {"seeded": True})
        sheets_ledger.save_ledger(ledger)
    return {"until": until.isoformat(), "marked": len(activities)}


def update_p4_p7(sheets_client, strava_client):
    """P7 = number of yoga sessions, P4 = number of workouts, for finished weeks without values."""
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
    """Copy title, description and shoes from Strava to Garmin, newest first.

    With stop_at_transferred it stops at the first activity whose Garmin title already matches.
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
            print(f"{start}: no Garmin activity found")
            skipped += 1
            continue
        if stop_at_transferred and name and garmin["name"] == name:
            print(f"{start}: already transferred ('{name}'), stopping")
            break
        result = garmin_client.update_activity(start.isoformat(), name=name, description=description, gear_uuid=gear_uuid)
        transferred.append({"start_local": start.isoformat(), "name": result["name"], "shoe": shoe["name"] if shoe else None})
        print(f"{start}: transferred '{result['name']}'")
        time.sleep(1)
    return {"transferred": transferred, "skipped": skipped}


# ---------- Telegram: details come from the bot ----------

def new_activity(sheets_client, strava_client, activity_id):
    """New Strava activity (webhook): the number goes into the sheet right away. For runs the texts follow via log_run."""
    activity = strava_client.get_activity(activity_id)
    info = run_info(activity) | {"sport_type": activity["sport_type"], "is_run": is_run(activity)}
    if activity["sport_type"] == "Yoga":
        return info | {"sheet": "skipped"}
    added = sheets_client.set_new_entry_from_json(activity, with_run_texts=False)
    if info["is_run"]:
        info |= same_training(strava_client, activity)
    return info | {"sheet": "added" if added else "already"}


def same_training(strava_client, activity):
    """Other runs of the same training: chained with breaks of at most SAME_TRAINING_GAP, same half day.

    first_of_training is true if no run of the training started earlier, so only that one needs a question.
    """
    start = activity_date(activity)
    found = strava_client.get_all_activities_in_timeframe(fmt(start - timedelta(days=1)), fmt(start + timedelta(days=1)))
    runs = sorted([a for a in found if is_run(a) and a["id"] != activity["id"]] + [activity], key=lambda a: a["start_date_local"])
    i = next(k for k, a in enumerate(runs) if a["id"] == activity["id"])
    end = lambda a: activity_date(a) + timedelta(seconds=a["elapsed_time"])
    morning = lambda a: activity_date(a).hour < 13
    group = [runs[i]]
    for a in reversed(runs[:i]):
        if activity_date(group[0]) - end(a) > SAME_TRAINING_GAP or morning(a) != morning(activity):
            break
        group.insert(0, a)
    for a in runs[i + 1:]:
        if activity_date(a) - end(group[-1]) > SAME_TRAINING_GAP or morning(a) != morning(activity):
            break
        group.append(a)
    return {"same_training": [a["id"] for a in group if a["id"] != activity["id"]], "first_of_training": group[0]["id"] == activity["id"]}


def undocumented_runs(sheets_client, strava_client, days=14):
    """Half days with runs in the last days whose main cell or notes are empty in the sheet, oldest first."""
    end = datetime.now()
    found = strava_client.get_all_activities_in_timeframe(fmt(end - timedelta(days=days)), fmt(end))
    blocks = {}
    for activity in sorted((a for a in found if is_run(a)), key=lambda a: a["start_date_local"]):
        info = run_info(activity)
        blocks.setdefault((info["start_local"][:10], info["daytime"]), []).append(info)
    result = []
    for (date, daytime), runs in blocks.items():
        cells = sheets_client.read_run_cells(runs[0]["start_local"])
        # No kilometers in this block means the run was moved elsewhere by hand, so don't report it
        if not str(cells["run_value"] or "").strip():
            continue
        missing = [name for name, key in (("what", "run_text"), ("thoughts", "notes")) if not (cells[key] or "").strip()]
        if missing:
            result.append({"date": date, "daytime": daytime, "distance_km": round(sum(r["distance_km"] for r in runs), 2),
                           "strava_ids": [r["strava_id"] for r in runs], "missing": missing})
    return {"days": days, "undocumented": result}


def find_runs(strava_client, date=None, daytime=None, strava_ids=None):
    """Runs of one half day. All of them must be in the same block, otherwise it is unclear which are meant."""
    if strava_ids:
        runs = [a for a in (strava_client.get_activity(i) for i in strava_ids) if is_run(a)]
    else:
        if not date:
            raise RunSyncError("bad_request", "date or strava_ids is missing")
        day = datetime.strptime(date, "%Y-%m-%d")
        # Strava filters by UTC, so fetch with a margin and then filter by local time
        found = strava_client.get_all_activities_in_timeframe(fmt(day - timedelta(days=1)), fmt(day + timedelta(days=2)))
        runs = [a for a in found if is_run(a) and a["start_date_local"][:10] == date]
        if daytime in ("morning", "afternoon"):
            matching = [a for a in runs if run_info(a)["daytime"] == daytime]
            if not matching:
                raise RunSyncError("run_not_found", f"No run on {date} ({daytime})", runs_that_day=[run_info(a) for a in runs])
            runs = matching
    if not runs:
        raise RunSyncError("run_not_found", f"No run found ({date or strava_ids})")
    runs.sort(key=lambda a: a["start_date_local"])
    infos = [run_info(a) for a in runs]
    if len({(i["start_local"][:10], i["daytime"]) for i in infos}) > 1:
        raise RunSyncError("ambiguous_run", "The runs are in different half days, please pass daytime", runs_that_day=infos)
    return runs


def remove_passages(message, passages):
    """The message without the given passages (case-insensitive, whitespace-tolerant), plus passages not found.

    Used for the thoughts: a language model only names the short passages to drop (day, training, shoes) instead of
    copying a long voice message, so nothing else can get lost. A passage that isn't found simply stays in.
    """
    text = " ".join(message.split())
    missing = []
    for passage in passages:
        passage = " ".join(passage.split())
        if not passage:
            continue
        i = text.lower().find(passage.lower())
        if i < 0:
            missing.append(passage)
            continue
        text = text[:i] + " " + text[i + len(passage):]
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)          # no space before punctuation
    text = re.sub(r"([.,;:!?])(?:\s*[.,;:])+", r"\1", text)  # leftover punctuation pairs like ". ,"
    text = re.sub(r"^[\s.,;:!?]+", "", re.sub(r"\s{2,}", " ", text)).strip()
    return text, missing


def set_strava_description(strava_client, activity_id, text):
    """Strava description, but only if it is empty or still the text RunSync wrote: the athlete's own text stays."""
    text = (text or "").strip()
    norm = lambda t: " ".join((t or "").split())
    current = strava_client.get_activity(activity_id).get("description") or ""
    key = str(activity_id)
    with sheets_ledger.ledger_lock:
        previous = sheets_ledger.load_ledger().get("strava_descriptions", {}).get(key)
    if norm(current) == norm(text):
        status = "unchanged"
    elif norm(current) and norm(current) != norm(previous):
        return "kept_own"
    else:
        strava_client.update_activity(activity_id, description=text)
        status = "set"
    with sheets_ledger.ledger_lock:
        ledger = sheets_ledger.load_ledger()
        ledger.setdefault("strava_descriptions", {})[key] = text
        sheets_ledger.save_ledger(ledger)
    return status


def strava_description_is_own(activity):
    """True if the Strava description was written by the athlete (not empty and not from RunSync)."""
    current = " ".join((activity.get("description") or "").split())
    with sheets_ledger.ledger_lock:
        previous = sheets_ledger.load_ledger().get("strava_descriptions", {}).get(str(activity["id"]))
    return bool(current) and current != " ".join((previous or "").split())


def log_run(sheets_client, strava_client, garmin_client, date=None, daytime=None, strava_ids=None,
            what=None, shoe=None, thoughts=None, message=None, remove=None, thoughts_from_message=False,
            what_neutral=None, has_workout=False):
    """Write the details of the runs of one half day (morning or afternoon) everywhere.

    thoughts_from_message: the thoughts are the whole message minus the passages in remove.
    what_neutral: the training in language-neutral words ("70 min easy") for the Strava description. For a workout
    (has_workout) the description waits for workout_apply, which adds the splits.
    Empty fields stay unchanged. Each target is tried on its own; the result says what worked.
    If the shoe is unknown or ambiguous, everything else is still saved and shoe_problem says why.
    """
    result = {"garmin": [], "strava": [], "notes": []}
    if thoughts_from_message and (message or "").strip():
        thoughts, result["not_removed"] = remove_passages(message, remove or [])
    what, thoughts = (what or "").strip() or None, (thoughts or "").strip() or None
    shoe_entry = None
    if shoe:
        shoe_entry, options = shoes.resolve(shoe)
        if options:
            result["shoe_problem"] = {"error_type": "ambiguous_shoe", "message": f"Shoe '{shoe}' is ambiguous", "options": options}
        elif not shoe_entry:
            result["shoe_problem"] = {"error_type": "unknown_shoe", "message": f"Shoe '{shoe}' is unknown, add it with add_shoe"}
    runs = find_runs(strava_client, date, daytime, strava_ids)
    infos = [run_info(a) for a in runs]
    garmin_gear = shoe_entry["garmin"] if shoe_entry else None
    strava_gear = shoe_entry["strava"] if shoe_entry else None
    result |= {"runs": infos, "shoe": shoe_entry["name"] if shoe_entry else None, "thoughts_saved": thoughts}

    try:
        for activity in runs:
            sheets_client.set_new_entry_from_json(activity, with_run_texts=False)
        run_key = ",".join(sorted(str(i["strava_id"]) for i in infos))
        result["sheet"] = {"ok": True, **sheets_client.set_run_texts(infos[0]["start_local"], what, thoughts, run_key)}
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
        describe = bool((what_neutral or "").strip()) and not has_workout
        if fields or describe:
            entry = {"strava_id": info["strava_id"], "ok": True}
            try:
                if fields:
                    strava_client.update_activity(info["strava_id"], **fields)
                if describe:
                    entry["description"] = set_strava_description(strava_client, info["strava_id"], what_neutral)
            except Exception as e:
                entry |= {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
            result["strava"].append(entry)

    if shoe_entry and not garmin_gear:
        result["notes"].append(f"{shoe_entry['name']} does not exist on Garmin, no shoe was set there. add_shoe can add it.")
    if shoe_entry and not strava_gear:
        result["notes"].append(f"{shoe_entry['name']} does not exist on Strava, no shoe was set there. add_shoe can add it.")
    result["ok"] = result["sheet"]["ok"] and all(r["ok"] for r in result["garmin"] + result["strava"]) and "shoe_problem" not in result
    if "shoe_problem" in result:
        result["action_needed"] = ("Everything except the shoe was saved. Ask the user which shoe it was"
                                   + (f" ({' or '.join(result['shoe_problem']['options'])})" if result["shoe_problem"].get("options") else "")
                                   + ", then call log_run for the same run with only the shoe.")
    return result


def workout_context(strava_client, garmin_client, strava_ids, workout, what_neutral):
    """Everything for preview and apply: the checked workout, laps of all runs, matched reps, description, lactate rows."""
    try:
        w = workouts.normalize(json.loads(workout) if isinstance(workout, str) else workout)
    except ValueError as e:
        raise RunSyncError("bad_request", f"workout: {e}")
    runs = find_runs(strava_client, strava_ids=strava_ids)
    laps, activities = [], []
    for activity in runs:
        info = run_info(activity)
        found = garmin_client.get_laps(info["start_local"])
        activities.append(info | {"garmin_type": found.get("type"), "weather": found.get("weather"), "strava": activity})
        laps += [lap | {"activity": len(activities) - 1} for lap in found["laps"]]
    match = None if w["no_splits"] else workouts.match_laps(laps, w["segments"])
    usable = w["no_splits"] or match["ok"]
    main = activities[match["reps"][0]["activity"]] if match and match["ok"] else activities[0]
    # Shoe: what log_run set on Strava, only the model as the athlete writes it ("Vaporfly 4")
    shoe = shoes.by_strava_id(main["strava"].get("gear_id"))
    rows = workouts.lactate_rows(w, match, {
        "date": main["start_local"][:10], "session": "AM" if main["daytime"] == "morning" else "PM",
        "shoes": workouts.shoe_model(shoe["name"]) if shoe else None, "weather": main["weather"],
        "garmin_type": main["garmin_type"], "strava_id": main["strava_id"],
    }) if usable else []
    return {"workout": w, "laps": laps, "match": match, "usable": usable, "main": main, "activities": activities,
            "rows": rows, "description": workouts.description(what_neutral, w["segments"], match, w["lactate"])}


def workout_preview(strava_client, garmin_client, strava_ids, workout, what_neutral):
    """Shows what workout_apply would write; writes nothing."""
    ctx = workout_context(strava_client, garmin_client, strava_ids, workout, what_neutral)
    return workouts.preview(ctx["workout"], ctx["match"], ctx["laps"], ctx["description"], ctx["rows"]) | {
        "strava_description_own": strava_description_is_own(ctx["main"]["strava"])}


def workout_apply(strava_client, garmin_client, strava_ids, workout, what_neutral):
    """After the athlete confirmed the preview: Strava description with splits on the run with the reps (other runs of
    the training get the title), lactate rows into the lactate sheet (replacing earlier rows of this run)."""
    ctx = workout_context(strava_client, garmin_client, strava_ids, workout, what_neutral)
    if not ctx["usable"]:
        raise RunSyncError("workout_not_matched", f"The reps were not found in the laps ({ctx['match']['reason']})")
    result = {"strava": [], "description": ctx["description"]}
    for activity in ctx["activities"]:
        text = ctx["description"] if activity is ctx["main"] else what_neutral
        if not (text or "").strip():
            continue
        try:
            result["strava"].append({"strava_id": activity["strava_id"], "ok": True,
                                     "description": set_strava_description(strava_client, activity["strava_id"], text)})
        except Exception as e:
            result["strava"].append({"strava_id": activity["strava_id"], "ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
    try:
        result["lactate_sheet"] = {"ok": True, **LactateClient().write_rows(ctx["main"]["strava_id"], ctx["rows"])}
    except Exception as e:
        result["lactate_sheet"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
    result["ok"] = result["lactate_sheet"]["ok"] and all(r["ok"] for r in result["strava"])
    return result


def add_shoe(strava_client, garmin_client, name):
    """Add a new shoe, or complete a known one on the side where it is missing.

    Garmin: link a matching shoe that is not mapped yet, otherwise create it.
    Strava: link a matching shoe that is not mapped yet. The Strava API cannot create gear,
    so the shoe has to be added in the Strava app first and add_shoe called again.
    """
    name = " ".join(name.split())
    if len(shoes.words(name)) < 2:
        raise RunSyncError("bad_request", "Please give brand and model, e.g. 'Nike Pegasus 41 Black'")
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
            result["note"] = ("Strava does not allow apps to create shoes. Add it in the Strava app "
                              "(Profile > Gear), then call add_shoe again to link it.")

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

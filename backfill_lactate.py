"""One-off: fill empty cells of older lactate rows from Strava and Garmin.

- Shoes: from the Strava gear of the run (shoes used to be tracked on Strava)
- Humidity: from the Garmin weather, only for rows with a temperature (rows without one count as indoors)
- With --paces, Prev Avg/Fastest/Slowest Pace: the reps are searched in the Garmin laps like for new workouts. Only used if the
  laps reproduce the rep times in the sheet (within TIME_TOLERANCE), otherwise the session is skipped.
  Not used so far: indoors, on the treadmill and with poor GPS the real rep distances of older sessions are unknown.

Only empty cells are written. Without --apply nothing is written, the plan is printed.
python backfill_lactate.py [--since 2025-11-25] [--paces] [--apply]
"""
import json
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import shoes
import workout as workouts
from garmin_client import GarminClient, GarminError
from lactate_client import EXCEL_EPOCH, LactateClient, cell_value, column_letter
from main_app import fmt, is_run
from sheets_client import activity_date
from strava_client import StravaClient

TIME_TOLERANCE = 1.5  # seconds between the matched lap and the rep time in the sheet


def number(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def uniform(times, share=0.08):
    middle = sorted(times)[len(times) // 2]
    return all(abs(t - middle) <= share * middle for t in times)


def match_session(laps, rows):
    """Reps of the session in the laps, verified against the rep times in the sheet. Returns (match, segment) or None."""
    reps = int(max(number(r["rep_no"]) for r in rows))
    distances = {number(r["rep_dist_m"]) for r in rows}
    times = [number(r["rep_time"]) * 86400 for r in rows]
    if len(distances) > 1 and not all(abs(t - times[0]) < 1 for t in times):
        return None  # different distances and times: a mixed session, the structure is unknown
    rest = number(rows[0]["rest_s"])
    # Same time for every test (6:00, 10:00): time-based reps, else distance-based
    options = []
    if all(abs(t - times[0]) < 1 for t in times):
        options.append({"reps": reps, "duration_s": round(times[0])})
    if len(distances) == 1:
        options.append({"reps": reps, "distance_m": distances.pop()})
    for seg in options:
        for rest_s in (rest, None):
            w = workouts.normalize({"segments": [seg | {"rest_s": rest_s}]})
            match = workouts.match_laps(laps, w["segments"])
            # Reps far off the others (e.g. 800s between 1000s) mean a different structure than the sheet suggests
            if match["ok"] and not uniform([r["time_s"] for r in match["reps"]]):
                continue
            if match["ok"] and all(abs(match["reps"][int(number(r["rep_no"])) - 1]["time_s"] - number(r["rep_time"]) * 86400) <= TIME_TOLERANCE
                                   for r in rows):
                return match, w["segments"][0]
    return None


def previous_paces(match, segment, rows, rep_no):
    """Pace of the reps before rep_no. Time-based reps (treadmill) take the distance of the next tested rep."""
    tested = sorted((int(number(r["rep_no"])), number(r["rep_dist_m"])) for r in rows)
    paces = []
    for rep in match["reps"][:rep_no - 1]:
        if segment["distance_m"]:
            distance = segment["distance_m"]
        else:
            distance = next((d for n, d in tested if n >= rep["rep"]), tested[-1][1])
        paces.append(rep["time_s"] / distance * 1000)
    return paces


def main(since=None, apply=False, with_paces=False):
    lactate, strava, garmin = LactateClient(), StravaClient(), GarminClient()
    cols = lactate.header()
    values = lactate.ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
    sessions = defaultdict(list)
    for number_, row in enumerate(values[1:], start=2):
        r = {key: (row[i] if i < len(row) else "") for key, i in cols.items()}
        if r["date"] in ("", None):
            continue
        day = EXCEL_EPOCH + timedelta(days=int(r["date"]))
        if since and day < since:
            continue
        r |= {"row": number_, "rep_time": r["rep_time_s"]}
        sessions[(day, r["session"] or "AM")].append(r)

    first, last = min(sessions)[0], max(sessions)[0]
    found = strava.get_all_activities_in_timeframe(fmt(datetime.combine(first, datetime.min.time()) - timedelta(days=1)),
                                                   fmt(datetime.combine(last, datetime.min.time()) + timedelta(days=2)))
    runs = defaultdict(list)
    for a in found:
        if is_run(a):
            start = activity_date(a)
            runs[(start.date(), "AM" if start.hour < 13 else "PM")].append(a)

    updates, report = [], []
    for key in sorted(sessions):
        rows = sorted(sessions[key], key=lambda r: number(r["rep_no"]) or 0)
        label = f"{key[0]} {key[1]} ({len(rows)} rows)"
        session_runs = sorted(runs.get(key, []), key=lambda a: a["start_date_local"])
        if not session_runs:
            report.append(f"{label}: no Strava run")
            continue
        laps, owners, weather = [], [], {}
        for a in session_runs:
            try:
                g = garmin.get_laps(activity_date(a).isoformat())
            except GarminError as e:
                report.append(f"{label}: Garmin {e.error_type} for {a['id']}")
                continue
            laps += g["laps"]
            owners += [a] * len(g["laps"])
            weather[a["id"]] = g.get("weather") or {}
            time.sleep(0.5)
        result = match_session(laps, rows) if laps and all(number(r["rep_no"]) for r in rows) else None
        main_run = owners[result[0]["reps"][0]["lap"]] if result else max(session_runs, key=lambda a: a["moving_time"])
        shoe = shoes.by_strava_id(main_run.get("gear_id"))
        shoe_name = workouts.shoe_model(shoe["name"]) if shoe else None
        humidity = (weather.get(main_run["id"]) or {}).get("humidity_pct")

        filled = defaultdict(int)
        for r in rows:
            wanted = {"shoes": shoe_name}
            if r["temp_c"] not in ("", None):
                wanted["humidity"] = humidity
            if with_paces and result and number(r["rep_no"]) > 1:
                paces = previous_paces(*result, rows, int(number(r["rep_no"])))
                wanted |= {"prev_avg": round(sum(paces) / len(paces)), "prev_fastest": round(min(paces)), "prev_slowest": round(max(paces))}
            for k, v in wanted.items():
                if v not in (None, "") and r[k] in ("", None):
                    updates.append({"range": f"{column_letter(cols[k])}{r['row']}", "values": [[cell_value(k, v)]],
                                    "key": k, "value": v, "row": r["row"]})
                    filled[k] += 1
        reps = " ".join(workouts.fmt_time(x["time_s"]) for x in result[0]["reps"]) if result else "reps not found"
        report.append(f"{label}: {dict(filled) or 'nothing'} | shoe {shoe_name} | {reps}")

    print("\n".join(report))
    print(f"\n{len(updates)} cells", {k: sum(u['key'] == k for u in updates) for k in set(u['key'] for u in updates)})
    if apply and updates:
        with open(f"/data/backfill_lactate_{datetime.now():%Y%m%d_%H%M%S}.json", "w") as f:
            json.dump(updates, f)  # empty before, so undoing means clearing these cells
        lactate.ws.batch_update([{"range": u["range"], "values": u["values"]} for u in updates], value_input_option="RAW")
        print("written")


if __name__ == "__main__":
    args = sys.argv[1:]
    since = date.fromisoformat(args[args.index("--since") + 1]) if "--since" in args else None
    main(since=since, apply="--apply" in args, with_paces="--paces" in args)

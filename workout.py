"""Workouts: find the reps the athlete names in the watch laps, write the Strava description and the lactate rows.

The athlete's words win for distances: indoors or on a curvy course the watch measures 330 m for a 400.
Only times and heart rate come from the watch. The laps are expected as recorded with the lap button:
one lap per rep and one per rest. Warm-up, strides and cool-down are simply laps that no segment uses.

A workout as the language model extracts it from the athlete's message:
{
  "segments": [{"reps": 20, "distance_m": 400, "rest_s": 30, "rest_type": "stand"}, ...],
                 per segment distance_m or duration_s; optional speed_kmh or pace_s_per_km (treadmill)
  "lactate": [{"after_rep": 7, "mmol": 3.1}, ...],   rep numbers count through the whole workout
  "surface": "Track", "indoor": false, "incline_pct": null, "workout_type": "Short Reps",
  "no_splits": false                                   true: don't use the watch at all (e.g. a missed lap press)
}
"""
import math
from statistics import mean, median, pstdev

SPLIT_LIST_MAX = 15   # up to this many reps in a segment every time is listed, above that the average per block
BLOCK_SIZE = 5        # block size for long segments without lactate tests
SECONDS_BELOW = 90    # times below 1:30 are shown as seconds ("75.8"), from 1:30 on as m:ss

WORKOUT_TYPES = ["Short Reps", "Long Reps", "Mixed Reps", "Double Threshold - Short Reps",
                 "Double Threshold - Long Reps", "Continuous Threshold", "Fartlek", "Race"]
SURFACES = ["Track", "Treadmill", "Road", "XC", "Grass", "Trail", "Dirtroad"]
REST_TYPES = ["Stand", "Jog", "Float"]
INDOOR_TYPES = ("treadmill_running", "indoor_running", "indoor_track")

# Matching tolerances
DISTANCE_RATIO = (0.6, 1.6)      # watch distance / stated distance (indoor tracks measure far too short)
DURATION_TOLERANCE = (3, 0.1)    # seconds, share of the stated duration (whichever is larger)
REST_SLOWER = 0.85               # a rest lap is slower than this share of the slowest rep
GAP_PENALTY = 0.3                # segments usually follow each other with exactly one rest lap in between
AMBIGUOUS_MARGIN = 0.05


class WorkoutError(ValueError):
    pass


# ---------- Input ----------

def _number(value, field, minimum=0):
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except ValueError:
        raise WorkoutError(f"{field} must be a number, not {value!r}")
    if number <= minimum:
        raise WorkoutError(f"{field} must be greater than {minimum}")
    return number


def _choice(value, options, field):
    if value in (None, ""):
        return None
    match = next((o for o in options if o.lower() == str(value).strip().lower()), None)
    if match is None:
        raise WorkoutError(f"{field} must be one of {', '.join(options)}, not {value!r}")
    return match


def normalize(workout):
    """Checks the workout from the language model and fills defaults. Raises WorkoutError with a readable message."""
    if not isinstance(workout, dict):
        raise WorkoutError("workout must be an object")
    segments = []
    for i, seg in enumerate(workout.get("segments") or []):
        name = f"segments[{i}]"
        reps = _number(seg.get("reps", 1), f"{name}.reps")
        if reps is None or reps != int(reps):
            raise WorkoutError(f"{name}.reps must be a whole number")
        distance, duration = _number(seg.get("distance_m"), f"{name}.distance_m"), _number(seg.get("duration_s"), f"{name}.duration_s")
        if not (distance or duration):
            raise WorkoutError(f"{name} needs distance_m or duration_s")
        segments.append({
            "reps": int(reps), "distance_m": distance, "duration_s": None if distance else duration,
            "rest_s": _number(seg.get("rest_s"), f"{name}.rest_s", minimum=-1),
            "rest_type": _choice(seg.get("rest_type"), REST_TYPES, f"{name}.rest_type"),
            "speed_kmh": _number(seg.get("speed_kmh"), f"{name}.speed_kmh"),
            "pace_s_per_km": _number(seg.get("pace_s_per_km"), f"{name}.pace_s_per_km"),
        })
    if not segments:
        raise WorkoutError("workout needs at least one segment")
    total = sum(s["reps"] for s in segments)
    lactate = []
    for i, test in enumerate(workout.get("lactate") or []):
        rep = _number(test.get("after_rep"), f"lactate[{i}].after_rep")
        mmol = _number(test.get("mmol"), f"lactate[{i}].mmol")
        if rep is None or mmol is None or rep != int(rep) or rep > total:
            raise WorkoutError(f"lactate[{i}] needs after_rep (1 to {total}) and mmol")
        lactate.append({"after_rep": int(rep), "mmol": mmol})
    return {
        "segments": segments,
        "lactate": sorted(lactate, key=lambda t: t["after_rep"]),
        "surface": _choice(workout.get("surface"), SURFACES, "surface"),
        "indoor": workout.get("indoor") in (True, "true"),
        "incline_pct": _number(workout.get("incline_pct"), "incline_pct", minimum=-100),
        "workout_type": _choice(workout.get("workout_type"), WORKOUT_TYPES, "workout_type"),
        "no_splits": workout.get("no_splits") in (True, "true"),
    }


# ---------- Matching ----------

def _speed(lap):
    return lap["distance_m"] / lap["duration_s"] if lap.get("duration_s") else 0


def _placement(laps, seg, start):
    """Cost of putting the reps of a segment on laps start, start+2, ... (rests in between), or None if they don't fit."""
    # Without rest (rest_s 0) the reps follow each other directly, else a rest lap lies between them
    step = 1 if seg["rest_s"] == 0 else 2
    n = len(seg_idx := [start + step * i for i in range(seg["reps"])])
    if seg_idx[-1] >= len(laps):
        return None
    reps = [laps[i] for i in seg_idx]
    rests = [laps[i + 1] for i in seg_idx[:-1]] if step == 2 else []
    if any(not lap.get("duration_s") for lap in reps):
        return None

    if seg["duration_s"]:
        target = seg["duration_s"]
        allowed = max(DURATION_TOLERANCE[0], DURATION_TOLERANCE[1] * target)
        if any(abs(lap["duration_s"] - target) > allowed for lap in reps):
            return None
        cost = mean(abs(lap["duration_s"] - target) / target for lap in reps)
    else:
        ratios = [lap["distance_m"] / seg["distance_m"] for lap in reps]
        if any(not DISTANCE_RATIO[0] <= r <= DISTANCE_RATIO[1] for r in ratios):
            return None
        logs = [math.log(r) for r in ratios]
        # Consistent reps matter more than the absolute distance (a short indoor track is short for every rep)
        cost = abs(median(logs)) + (5 * pstdev(logs) if n > 1 else 0)

    if not seg["rest_s"]:
        # Rest length unknown: rest laps must at least be clearly slower (treadmill rests are not, there rest_s helps)
        slowest = min(_speed(lap) for lap in reps)
        if any(_speed(lap) > REST_SLOWER * slowest for lap in rests):
            return None
    elif rests:
        rest = seg["rest_s"]
        if any(not 0.5 * rest - 5 <= lap["elapsed_s"] <= 2 * rest + 15 for lap in rests):
            return None
        cost += 0.5 * mean(abs(lap["elapsed_s"] - rest) / rest for lap in rests)
    return {"start": start, "end": seg_idx[-1], "laps": seg_idx, "cost": cost}


def _best_path(candidates, forbidden=None):
    """Cheapest choice of one placement per segment in lap order. forbidden: (segment, start) to leave out."""
    best = []
    for k, options in enumerate(candidates):
        row = []
        for c in options:
            if forbidden == (k, c["start"]):
                row.append(None)
                continue
            if k == 0:
                row.append((c["cost"], None))
                continue
            prev = [(best[k - 1][j][0] + (0 if c["start"] - p["end"] == 2 else GAP_PENALTY), j)
                    for j, p in enumerate(candidates[k - 1]) if best[k - 1][j] and p["end"] < c["start"]]
            row.append((min(prev)[0] + c["cost"], min(prev)[1]) if prev else None)
        best.append(row)
    finals = [(r[0], j) for j, r in enumerate(best[-1]) if r]
    if not finals:
        return None, []
    total, j = min(finals)
    path = []
    for k in range(len(candidates) - 1, -1, -1):
        path.insert(0, candidates[k][j])
        j = best[k][j][1]
    return total, path


def match_laps(laps, segments):
    """Finds the laps of all reps. Returns {"ok": True, "reps": [...], "rests_s": [...], "ambiguous": bool}
    or {"ok": False, "reason": ...}."""
    candidates = [[p for s in range(len(laps)) if (p := _placement(laps, seg, s))] for seg in segments]
    for seg, options in zip(segments, candidates):
        if not options:
            return {"ok": False, "reason": f"no {label(seg, with_reps=True)} in the laps"}
    total, path = _best_path(candidates)
    if path == []:
        return {"ok": False, "reason": "the segments are not in this order in the laps"}

    # Is there a different, almost as good solution?
    second = min((t for k, p in enumerate(path) if (t := _best_path(candidates, (k, p["start"]))[0]) is not None), default=None)
    ambiguous = second is not None and second - total < AMBIGUOUS_MARGIN

    reps, rests = [], []
    for k, (seg, placement) in enumerate(zip(segments, path)):
        rest_laps = [laps[i + 1]["elapsed_s"] for i in placement["laps"][:-1]] if seg["rest_s"] != 0 else []
        # Rest after a single rep (e.g. 1600, 1200, ... with 1' each): the lap before the next segment
        if not rest_laps and k + 1 < len(path) and path[k + 1]["start"] - placement["end"] == 2:
            rest_laps = [laps[placement["end"] + 1]["elapsed_s"]]
        rests.append(round(median(rest_laps)) if rest_laps else None)
        for i in placement["laps"]:
            lap = laps[i]
            reps.append({
                "rep": len(reps) + 1, "segment": k, "lap": i, "time_s": round(lap["duration_s"], 1),
                "distance_m": rep_distance(seg, lap), "watch_distance_m": lap["distance_m"],
                "hr": lap.get("avg_hr"), "activity": lap.get("activity", 0),
            })
    return {"ok": True, "reps": reps, "rests_s": rests, "ambiguous": ambiguous,
            "first_lap": path[0]["start"], "last_lap": path[-1]["end"]}


def rep_distance(seg, lap):
    """Stated distance; for time-based reps from the stated treadmill speed or pace, else what the watch measured."""
    if seg["distance_m"]:
        return seg["distance_m"]
    if seg["speed_kmh"]:
        return round(seg["speed_kmh"] / 3.6 * lap["duration_s"])
    if seg["pace_s_per_km"]:
        return round(lap["duration_s"] / seg["pace_s_per_km"] * 1000)
    return round(lap["distance_m"])


# ---------- Text ----------

def fmt_time(seconds):
    if seconds < SECONDS_BELOW:
        return f"{seconds:.1f}"
    s = round(seconds)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def fmt_mmol(mmol):
    return f"{mmol:.1f} mmol"


def label(seg, with_reps=False):
    if seg["distance_m"]:
        d = seg["distance_m"]
        text = f"{d / 1000:g} km" if d >= 5000 and d % 1000 == 0 else f"{d:g}"
    else:
        s = round(seg["duration_s"])
        text = f'{s}"' if s < 60 else f"{s // 60}'" if s % 60 == 0 else f"{s // 60}:{s % 60:02d}"
    return f"{seg['reps']}×{text}" if with_reps and seg["reps"] > 1 else text


def _blocks(times, tests):
    """Rep ranges for a long segment: up to each lactate test, the rest in one block; without tests blocks of BLOCK_SIZE."""
    ends = sorted(r for r in tests if r <= len(times))
    if not ends:
        ends = list(range(BLOCK_SIZE, len(times), BLOCK_SIZE))
    ranges, start = [], 1
    for end in ends + [len(times)]:
        if end >= start:
            ranges.append((start, end))
            start = end + 1
    return ranges


def split_lines(segments, reps, lactate):
    """Description lines below the title: single reps in a row on one line, every segment with several reps on its own."""
    tests = {t["after_rep"]: t["mmol"] for t in lactate}
    by_segment = [[r for r in reps if r["segment"] == k] for k in range(len(segments))]
    groups = []
    for k, seg in enumerate(segments):
        if seg["reps"] == 1 and groups and groups[-1][0] == "singles":
            groups[-1][1].append(k)
        else:
            groups.append(("singles" if seg["reps"] == 1 else "set", [k]))

    # With a single group the title already says what it was, so no "20×400:" in front
    named = len(groups) > 1
    lines = []
    for kind, ks in groups:
        if kind == "singles":
            parts = []
            for k in ks:
                r = by_segment[k][0]
                parts.append(f"{label(segments[k])} {fmt_time(r['time_s'])}" + (f" ({fmt_mmol(tests[r['rep']])})" if r["rep"] in tests else ""))
            lines.append(", ".join(parts))
            continue
        k = ks[0]
        seg_reps, prefix = by_segment[k], f"{label(segments[k], with_reps=True)}:" if named else ""
        if len(seg_reps) <= SPLIT_LIST_MAX:
            times = ", ".join(fmt_time(r["time_s"]) + (f" ({fmt_mmol(tests[r['rep']])})" if r["rep"] in tests else "") for r in seg_reps)
            lines.append(f"{prefix} {times}".strip())
            continue
        first = seg_reps[0]["rep"]
        local_tests = [r - first + 1 for r in tests if first <= r < first + len(seg_reps)]
        if prefix:
            lines.append(prefix)
        for a, b in _blocks(seg_reps, local_tests):
            block = seg_reps[a - 1:b]
            text = f"{a}-{b}: Ø {fmt_time(mean(r['time_s'] for r in block))}" if b > a else f"{a}: {fmt_time(block[0]['time_s'])}"
            test = tests.get(block[-1]["rep"])
            lines.append(text + (f" → {fmt_mmol(test)}" if test else ""))
    return lines


def description(title, segments, match, lactate):
    """Strava description: the title in neutral words, then the times (and lactate) if the laps were found."""
    lines = [title.strip()] if title and title.strip() else []
    if match and match.get("ok"):
        lines += split_lines(segments, match["reps"], lactate)
    elif lactate:
        lines.append("Lactate: " + ", ".join(f"{fmt_mmol(t['mmol'])} after rep {t['after_rep']}" for t in lactate))
    return "\n".join(lines)


# ---------- Lactate sheet ----------

def lactate_rows(workout, match, info):
    """One row per lactate test. info: date, session (AM/PM), shoes, weather, garmin_type, strava_id."""
    segments, reps = workout["segments"], (match or {}).get("reps") if (match or {}).get("ok") else None
    surface = workout["surface"] or ("Treadmill" if info.get("garmin_type") in INDOOR_TYPES else None)
    indoor = workout["indoor"] or surface == "Treadmill" or info.get("garmin_type") in INDOOR_TYPES
    weather = info.get("weather") or {}
    rows = []
    for test in workout["lactate"]:
        n = test["after_rep"]
        seg_index, local = _segment_of(segments, n)
        seg = segments[seg_index]
        rep = reps[n - 1] if reps else None
        previous = [r["time_s"] / r["distance_m"] * 1000 for r in (reps or [])[:n - 1] if r["distance_m"]]
        rest = seg["rest_s"] if seg["rest_s"] is not None else (match["rests_s"][seg_index] if reps else None)
        distance = rep["distance_m"] if rep else seg["distance_m"]
        rows.append({
            "date": info["date"], "session": info["session"], "workout_type": workout["workout_type"],
            "rep_dist_m": round(distance) if distance else None,
            "rep_time_s": rep["time_s"] if rep else (seg["duration_s"] or None),
            "pace_s_per_km": round(rep["time_s"] / distance * 1000) if rep and distance else None,
            "surface": surface,
            "incline": workout["incline_pct"] if workout["incline_pct"] is not None else (0 if surface == "Treadmill" else None),
            "lactate": test["mmol"], "rep_no": n,
            "rest_type": seg["rest_type"] or "Stand",
            "rest_s": round(rest / 5) * 5 if rest else rest,
            "hr": rep["hr"] if rep else None,
            "temp_c": None if indoor else weather.get("temp_c"),
            "humidity": None if indoor else weather.get("humidity_pct"),
            "shoes": info.get("shoes"),
            "prev_avg": round(mean(previous)) if previous else None,
            "prev_fastest": round(min(previous)) if previous else None,
            "prev_slowest": round(max(previous)) if previous else None,
            "strava_id": str(info["strava_id"]),
        })
    return rows


def _segment_of(segments, rep):
    count = 0
    for k, seg in enumerate(segments):
        if rep <= count + seg["reps"]:
            return k, rep - count
        count += seg["reps"]
    raise WorkoutError(f"rep {rep} is not in the workout")


# ---------- Preview (the bot words it for the athlete) ----------

def lap_list(laps):
    return ", ".join(f"{i + 1}) {round(lap['distance_m'])} m {fmt_time(lap['duration_s'])}" for i, lap in enumerate(laps))


def preview(workout, match, laps, desc, rows):
    """What apply would write, as data. The first lactate row stands for the details all rows share."""
    result = {"no_splits": workout["no_splits"], "matched": workout["no_splits"] or bool(match and match["ok"]),
              "laps_total": len(laps), "description": desc, "lactate_rows": len(rows)}
    if match and match["ok"]:
        result |= {"first_lap": match["first_lap"] + 1, "last_lap": match["last_lap"] + 1, "ambiguous": match["ambiguous"]}
    elif match:
        result |= {"reason": match["reason"], "laps": lap_list(laps)}
    if rows:
        r = rows[0]
        result["sheet"] = {k: r[k] for k in ("workout_type", "surface", "temp_c", "humidity", "rest_s", "rest_type", "shoes")}
    return result

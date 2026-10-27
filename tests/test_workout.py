"""Offline tests for workout matching and texts, with laps recorded on a watch (tests/fixtures, times only).

python -m unittest discover tests
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lactate_client  # noqa: E402
import workout as W  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def laps(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def run(name, workout):
    data = laps(name)
    w = W.normalize(workout)
    return w, W.match_laps(data["laps"], w["segments"]), data


class Matching(unittest.TestCase):
    def test_miles_on_the_track_with_strides_before(self):
        # Watch says 1650-1680 m per lap, two strides before the reps
        w, m, _ = run("laps_6x1mile_track.json", {"segments": [{"reps": 6, "distance_m": 1609, "rest_s": 60}]})
        self.assertTrue(m["ok"])
        self.assertEqual([r["time_s"] for r in m["reps"]], [340.3, 338.1, 341.0, 345.5, 343.9, 345.3])
        self.assertEqual({r["distance_m"] for r in m["reps"]}, {1609})

    def test_indoor_400s_measured_short(self):
        # Indoor track: the watch measures 320-350 m, the athlete's 400 counts
        w, m, _ = run("laps_20x400_indoor.json", {"segments": [{"reps": 20, "distance_m": 400, "rest_s": 30}]})
        self.assertTrue(m["ok"])
        self.assertEqual(len(m["reps"]), 20)
        self.assertEqual(m["reps"][5]["time_s"], 75.8)
        self.assertEqual(m["reps"][11]["time_s"], 75.1)

    def test_treadmill_minutes_with_speed(self):
        # Treadmill rests are measured almost as fast as the reps, the rest length tells them apart
        w, m, _ = run("laps_10x3min_treadmill.json",
                      {"segments": [{"reps": 10, "duration_s": 180, "rest_s": 60, "rest_type": "jog", "speed_kmh": 18}]})
        self.assertTrue(m["ok"])
        self.assertEqual(m["reps"][0]["distance_m"], 899)

    def test_mixed_workout(self):
        # 1600, 2000, 1200, 2000, 800, 2000, 600 with 1 min rest, after a break 6x400 /30s
        singles = [{"reps": 1, "distance_m": d, "rest_s": 60} for d in (1600, 2000, 1200, 2000, 800, 2000, 600)]
        w, m, _ = run("laps_ladder_and_400s.json", {"segments": singles + [{"reps": 6, "distance_m": 400, "rest_s": 30}]})
        self.assertTrue(m["ok"])
        self.assertEqual([r["lap"] for r in m["reps"]][:7], [5, 7, 9, 11, 13, 15, 17])
        self.assertEqual([r["time_s"] for r in m["reps"]][7:], [84.4, 80.3, 80.5, 81.2, 80.6, 80.5])

    def test_wrong_count_is_not_matched(self):
        w, m, _ = run("laps_20x400_indoor.json", {"segments": [{"reps": 21, "distance_m": 400, "rest_s": 30}]})
        self.assertFalse(m["ok"])

    def test_missed_lap_press_is_not_matched(self):
        data = laps("laps_6x1mile_track.json")
        # Rep 4 and its rest recorded as one lap
        merged = data["laps"][:11] + [{k: data["laps"][11][k] + data["laps"][12][k] for k in ("distance_m", "duration_s", "elapsed_s")}] + data["laps"][13:]
        w = W.normalize({"segments": [{"reps": 6, "distance_m": 1609, "rest_s": 60}]})
        self.assertFalse(W.match_laps(merged, w["segments"])["ok"])

    def test_bad_input(self):
        with self.assertRaises(W.WorkoutError):
            W.normalize({"segments": [{"reps": 3}]})
        with self.assertRaises(W.WorkoutError):
            W.normalize({"segments": [{"reps": 3, "distance_m": 400}], "lactate": [{"after_rep": 4, "mmol": 2}]})
        with self.assertRaises(W.WorkoutError):
            W.normalize({"segments": [{"reps": 3, "distance_m": 400}], "surface": "Moon"})


class Texts(unittest.TestCase):
    def test_time_format(self):
        self.assertEqual(W.fmt_time(75.84), "75.8")
        self.assertEqual(W.fmt_time(89.9), "89.9")
        self.assertEqual(W.fmt_time(90), "1:30")
        self.assertEqual(W.fmt_time(345.3), "5:45")
        self.assertEqual(W.fmt_time(3725), "1:02:05")

    def test_every_rep_up_to_15(self):
        w, m, _ = run("laps_6x1mile_track.json", {"segments": [{"reps": 6, "distance_m": 1609, "rest_s": 60}],
                                                  "lactate": [{"after_rep": 3, "mmol": 2.5}, {"after_rep": 6, "mmol": 1.6}]})
        self.assertEqual(W.description("6×1 mi /1min", w["segments"], m, w["lactate"]),
                         "6×1 mi /1min\n5:40, 5:38, 5:41 (2.5 mmol), 5:46, 5:44, 5:45 (1.6 mmol)")

    def test_blocks_above_15(self):
        w, m, _ = run("laps_20x400_indoor.json", {"segments": [{"reps": 20, "distance_m": 400, "rest_s": 30}],
                                                  "lactate": [{"after_rep": 6, "mmol": 2.6}, {"after_rep": 12, "mmol": 1.6}]})
        self.assertEqual(W.description('20×400 /30s', w["segments"], m, w["lactate"]),
                         '20×400 /30s\n1-6: Ø 77.0 → 2.6 mmol\n7-12: Ø 76.0 → 1.6 mmol\n13-20: Ø 75.1')

    def test_blocks_without_lactate(self):
        w, m, _ = run("laps_20x400_indoor.json", {"segments": [{"reps": 20, "distance_m": 400, "rest_s": 30}]})
        lines = W.description("", w["segments"], m, []).split("\n")
        self.assertEqual([line.split(":")[0] for line in lines], ["1-5", "6-10", "11-15", "16-20"])

    def test_mixed_lines(self):
        singles = [{"reps": 1, "distance_m": d, "rest_s": 60} for d in (1600, 2000, 1200, 2000, 800, 2000, 600)]
        w, m, _ = run("laps_ladder_and_400s.json", {"segments": singles + [{"reps": 6, "distance_m": 400, "rest_s": 30}]})
        self.assertEqual(W.description("", w["segments"], m, []),
                         "1600 4:44, 2000 6:38, 1200 3:28, 2000 6:46, 800 2:16, 2000 6:31, 600 1:36\n"
                         "6×400: 84.4, 80.3, 80.5, 81.2, 80.6, 80.5")

    def test_no_splits(self):
        w = W.normalize({"segments": [{"reps": 6, "distance_m": 1609}], "lactate": [{"after_rep": 3, "mmol": 2.5}], "no_splits": True})
        self.assertEqual(W.description("6×1 mi", w["segments"], None, w["lactate"]), "6×1 mi\nLactate: 2.5 mmol after rep 3")


class Preview(unittest.TestCase):
    def test_matched(self):
        w, m, data = run("laps_6x1mile_track.json", {"segments": [{"reps": 6, "distance_m": 1609, "rest_s": 60}],
                                                    "lactate": [{"after_rep": 3, "mmol": 2.5}], "surface": "Track"})
        rows = W.lactate_rows(w, m, LactateRows.INFO | {"weather": {}, "garmin_type": data["type"]})
        p = W.preview(w, m, data["laps"], "6×1 mi", rows)
        self.assertEqual((p["matched"], p["first_lap"], p["last_lap"], p["lactate_rows"]), (True, 6, 16, 1))
        self.assertEqual(p["sheet"]["surface"], "Track")

    def test_not_matched_lists_laps(self):
        w, m, data = run("laps_6x1mile_track.json", {"segments": [{"reps": 7, "distance_m": 1609, "rest_s": 60}]})
        p = W.preview(w, m, data["laps"], "", [])
        self.assertFalse(p["matched"])
        self.assertTrue(p["laps"].startswith("1) 3327 m 16:26, 2) 305 m 60.3"))


class LactateRows(unittest.TestCase):
    INFO = {"date": "2026-09-08", "session": "AM", "shoes": "Racing Flat 1", "strava_id": 1}

    def test_outdoor_rows(self):
        w, m, data = run("laps_6x1mile_track.json", {"segments": [{"reps": 6, "distance_m": 1609, "rest_s": 60}],
                                                     "lactate": [{"after_rep": 3, "mmol": 2.5}], "surface": "Track"})
        row = W.lactate_rows(w, m, self.INFO | {"weather": {"temp_c": 26.1, "humidity_pct": 70}, "garmin_type": data["type"]})[0]
        self.assertEqual((row["rep_time_s"], row["rep_no"], row["rest_type"], row["rest_s"]), (341.0, 3, "Stand", 60))
        self.assertEqual((row["temp_c"], row["humidity"]), (26.1, 70))
        # Paces of reps 1 and 2 in s/km
        self.assertEqual((row["prev_avg"], row["prev_fastest"], row["prev_slowest"]), (211, 210, 211))

    def test_indoor_without_weather(self):
        w, m, data = run("laps_20x400_indoor.json", {"segments": [{"reps": 20, "distance_m": 400, "rest_s": 30}],
                                                     "lactate": [{"after_rep": 1, "mmol": 1.2}], "surface": "Track", "indoor": True})
        row = W.lactate_rows(w, m, self.INFO | {"weather": {"temp_c": 20, "humidity_pct": 50}, "garmin_type": "running"})[0]
        self.assertEqual((row["temp_c"], row["humidity"], row["prev_avg"]), (None, None, None))

    def test_treadmill_defaults(self):
        w, m, data = run("laps_10x3min_treadmill.json", {"segments": [{"reps": 10, "duration_s": 180, "rest_s": 60}],
                                                     "lactate": [{"after_rep": 3, "mmol": 1.7}]})
        row = W.lactate_rows(w, m, self.INFO | {"weather": {}, "garmin_type": data["type"]})[0]
        self.assertEqual((row["surface"], row["incline"]), ("Treadmill", 0))

    def test_sheet_units(self):
        # Like the athlete types them: 5:36 rep time, pace 3:29 shown as h:mm
        self.assertEqual(lactate_client.cell_value("rep_time_s", 336), 336 / 86400)
        self.assertAlmostEqual(lactate_client.cell_value("pace_s_per_km", 209), 0.1451388888888889)
        self.assertEqual(lactate_client.cell_value("date", "2026-09-04"), 46269)
        self.assertEqual(lactate_client.cell_value("temp_c", None), "")


class FakeStrava:
    def __init__(self, description=None):
        self.description, self.puts = description, 0

    def get_activity(self, activity_id):
        return {"id": activity_id, "description": self.description}

    def update_activity(self, activity_id, **fields):
        self.puts += 1
        self.description = fields["description"]


class StravaDescription(unittest.TestCase):
    def setUp(self):
        import sheets_client
        self.sheets_client, self.tmp = sheets_client, tempfile.TemporaryDirectory()
        self.old_ledger = sheets_client.LEDGER_FILE
        sheets_client.LEDGER_FILE = os.path.join(self.tmp.name, "ledger.json")

    def tearDown(self):
        self.sheets_client.LEDGER_FILE = self.old_ledger
        self.tmp.cleanup()

    def test_empty_then_replace_own(self):
        import main_app
        strava = FakeStrava()
        self.assertEqual(main_app.set_strava_description(strava, 1, "20×400 /30s"), "set")
        # A preview correction replaces what RunSync wrote
        self.assertEqual(main_app.set_strava_description(strava, 1, "20×400 /30s\n1-6: Ø 77.0"), "set")
        self.assertEqual(main_app.set_strava_description(strava, 1, "20×400 /30s\n1-6: Ø 77.0"), "unchanged")
        self.assertEqual(strava.puts, 2)

    def test_athletes_text_stays(self):
        import main_app
        strava = FakeStrava("Great session with the group")
        self.assertEqual(main_app.set_strava_description(strava, 1, "70 min easy"), "kept_own")
        self.assertEqual((strava.description, strava.puts), ("Great session with the group", 0))
        self.assertTrue(main_app.strava_description_is_own({"id": 1, "description": "Great session with the group"}))


if __name__ == "__main__":
    unittest.main()

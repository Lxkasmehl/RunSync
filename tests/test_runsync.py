"""Tests ohne Netz: python -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sheets_client  # noqa: E402
import shoes  # noqa: E402


class WeekAndCells(unittest.TestCase):
    def test_week_title(self):
        # Wochen laufen von Sonntag bis Samstag
        self.assertEqual(sheets_client.week_title(datetime(2026, 10, 22, 6))[0], "KW4326")
        self.assertEqual(sheets_client.week_title(datetime(2026, 10, 18, 8))[0], "KW4326")
        self.assertEqual(sheets_client.week_title(datetime(2026, 10, 25, 8))[0], "KW4426")
        self.assertEqual(sheets_client.week_title(datetime(2026, 10, 24, 20))[0], "KW4326")

    def test_slot_cells(self):
        # Donnerstag vormittags: Spalten J/K, Zeilen 3-5
        self.assertEqual(sheets_client.slot_cells(datetime(2026, 10, 22, 6, 16)),
                         {"other_text": "J3", "other_value": "K3", "run_text": "J4", "run_value": "K4", "notes": "J5"})
        # Montag 13:00 zaehlt schon zum Nachmittag
        self.assertEqual(sheets_client.slot_cells(datetime(2026, 10, 19, 13))["run_value"], "E7")
        # Sonntag = B/C
        self.assertEqual(sheets_client.slot_cells(datetime(2026, 10, 18, 8))["run_text"], "B4")

    def test_parse_number(self):
        self.assertEqual(sheets_client.parse_number("14,92"), 14.92)
        self.assertEqual(sheets_client.parse_number(17.5), 17.5)
        self.assertEqual(sheets_client.parse_number(""), 0.0)
        self.assertEqual(sheets_client.parse_number(None), 0.0)


class Shoes(unittest.TestCase):
    def check(self, text, expected):
        shoe, options = shoes.resolve(text)
        self.assertEqual(shoe["name"] if shoe else sorted(options), expected)

    def test_unique(self):
        self.check("Pegasus 40", "Nike Pegasus 40 Black")
        self.check("hellgrünen Pegasus", "Nike Pegasus 39 Light Green")
        self.check("die blauen Invincible DE", "Nike Invincible 3 Blue (DE)")
        self.check("meine Structures Bowerman", "Nike Structure 25 Bowerman")
        self.check("Nike Pegasus 39 Grey", "Nike Pegasus 39 Grey")
        # So kam es aus der Sprachnachricht
        self.check("On Cloud Surfer", "On Cloudsurfer")
        self.check("On-Cloud-Surfer", "On Cloudsurfer")
        self.check("Cloud Boom", "On Cloudboom Echo 3")

    def test_ambiguous(self):
        self.check("Invincible 3, in dem blauen", ["Nike Invincible 3 Blue (DE)", "Nike Invincible 3 Blue (US)"])
        self.check("Structures", ["Nike Structure 25 Bowerman", "Nike Structure 25 White Blue"])

    def test_unknown(self):
        # Modellnummer muss passen: nicht stillschweigend den Pegasus 40 Black nehmen
        self.assertEqual(shoes.resolve("Pegasus 41 schwarz"), (None, []))
        self.assertEqual(shoes.resolve("Brooks Ghost"), (None, []))

    def test_ids_unique(self):
        all_shoes = shoes.load_shoes()
        for side in ("garmin", "strava"):
            ids = [s[side] for s in all_shoes if s[side]]
            self.assertEqual(len(ids), len(set(ids)), side)


class FakeWorksheet:
    title = "KW4326"

    def __init__(self, cells):
        self.cells = cells


class FakeSheets(sheets_client.SheetsClient):
    """SheetsClient ohne Google: Zellen liegen in einem dict."""

    def __init__(self, cells):
        self.ws = FakeWorksheet(cells)

    def week_worksheet(self, date):
        return self.ws

    def _read(self, worksheet, cells):
        return {c: worksheet.cells.get(c) for c in cells}

    def _write(self, worksheet, updates):
        worksheet.cells.update(updates)


class RunTexts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_ledger = sheets_client.LEDGER_FILE
        sheets_client.LEDGER_FILE = os.path.join(self.tmp.name, "ledger.json")

    def tearDown(self):
        sheets_client.LEDGER_FILE = self.old_ledger
        self.tmp.cleanup()

    def test_replace_own_text_keep_foreign(self):
        sheets = FakeSheets({"J5": "Maurten 320."})
        sheets.set_run_texts("2026-10-22T06:16:55", "TEST", "erste Version")
        self.assertEqual(sheets.ws.cells["J4"], "TEST")
        self.assertEqual(sheets.ws.cells["J5"], "Maurten 320.\nerste Version")
        # Korrektur ersetzt nur den eigenen Text
        sheets.set_run_texts("2026-10-22T06:16:55", "70min easy", "zweite Version")
        self.assertEqual(sheets.ws.cells["J4"], "70min easy")
        self.assertEqual(sheets.ws.cells["J5"], "Maurten 320.\nzweite Version")

    def test_same_text_not_appended_twice(self):
        sheets = FakeSheets({"D4": "70min easy"})
        sheets.set_run_texts("2026-10-19T06:03:59", "70min easy")
        self.assertEqual(sheets.ws.cells["D4"], "70min easy")

    def test_empty_fields_untouched(self):
        sheets = FakeSheets({"J4": "70min easy", "J5": "Notiz"})
        sheets.set_run_texts("2026-10-22T06:16:55", None, "  ")
        self.assertEqual(sheets.ws.cells, {"J4": "70min easy", "J5": "Notiz"})

    def test_no_texts_reads_nothing(self):
        # Nur Schuh geaendert: Google darf nicht mit einer leeren Zellenliste gefragt werden
        sheets = FakeSheets({})
        sheets._read = lambda worksheet, cells: self.fail("read with no cells") if not cells else {}
        self.assertEqual(sheets.set_run_texts("2026-10-22T06:16:55", None, None)["cells"], [])


class FakeGarmin:
    def __init__(self, shoes_list):
        self.list, self.created = shoes_list, []

    def get_shoes(self):
        return self.list

    def create_shoe(self, brand, model, name):
        self.created.append((brand, model, name))
        return {"uuid": "new-garmin-uuid", "name": name}


class FakeStrava:
    def __init__(self, shoes_list):
        self.list = shoes_list

    def get_shoes(self):
        return self.list


class AddShoe(unittest.TestCase):
    def setUp(self):
        import main_app
        self.main_app = main_app
        self.tmp = tempfile.TemporaryDirectory()
        self.old_file = shoes.DATA_FILE
        shoes.DATA_FILE = os.path.join(self.tmp.name, "shoes.json")
        shoes.save_shoes([{"name": "Nike Zoom Fly 6", "garmin": "zf6", "strava": None},
                          {"name": "Nike Pegasus 40 Black", "garmin": "p40", "strava": "g1"}])

    def tearDown(self):
        shoes.DATA_FILE = self.old_file
        self.tmp.cleanup()

    def test_new_shoe_created_on_garmin_strava_missing(self):
        garmin = FakeGarmin([{"uuid": "p40", "name": "Pegasus 40 Black"}])
        result = self.main_app.add_shoe(FakeStrava([{"id": "g1", "name": "Nike Pegasus 40 black"}]), garmin, "Nike Pegasus 41 Black")
        self.assertEqual((result["garmin"], result["strava"]), ("created", "missing"))
        self.assertEqual(garmin.created, [("Nike", "Pegasus 41 Black", "Nike Pegasus 41 Black")])
        self.assertEqual(shoes.resolve("Pegasus 41")[0]["garmin"], "new-garmin-uuid")

    def test_complete_strava_side_after_creating_in_app(self):
        strava = FakeStrava([{"id": "g1", "name": "Nike Pegasus 40 black"}, {"id": "g9", "name": "Nike Zoom Fly 6 orange"}])
        result = self.main_app.add_shoe(strava, FakeGarmin([]), "Nike Zoom Fly 6")
        self.assertEqual((result["garmin"], result["strava"]), ("already", "linked to 'Nike Zoom Fly 6 orange'"))
        self.assertEqual(shoes.resolve("Zoom Fly")[0]["strava"], "g9")

    def test_links_existing_garmin_shoe_instead_of_creating(self):
        garmin = FakeGarmin([{"uuid": "p40", "name": "Pegasus 40 Black"}, {"uuid": "b13", "name": "adidas Adizero Boston 13"}])
        result = self.main_app.add_shoe(FakeStrava([]), garmin, "Adidas Boston 13")
        self.assertEqual(result["garmin"], "linked to 'adidas Adizero Boston 13'")
        self.assertEqual(garmin.created, [])


if __name__ == "__main__":
    unittest.main()

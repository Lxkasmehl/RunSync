"""Google Sheets: the training diary.

Layout of a week worksheet (KW{week}{year}, Sunday to Saturday):
- Columns B-O: two columns per day (text, number), Sunday = B/C
- Morning (start before 1 pm) rows 3-5, afternoon rows 6-8
- 1st row of a block: other activities (name, minutes)
- 2nd row: runs (main cell, e.g. "70min easy", and kilometers)
- 3rd row: notes (thoughts)

Everything RunSync writes is recorded in ledger.json. That way no activity ends up in the sheet twice, and a
corrected text replaces the previous one instead of being appended.
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta

import gspread
from dotenv import load_dotenv
from gspread.exceptions import APIError
from gspread.utils import Dimension

load_dotenv()

LEDGER_FILE = os.path.join(os.getenv("DATA_DIR", "."), "ledger.json")
ledger_lock = threading.Lock()


def open_spreadsheet():
    file_path = os.getenv("FILE_PATH")
    if file_path and os.path.exists(file_path):
        sa = gspread.service_account(filename=file_path)
    elif os.getenv("SERVICE_ACCOUNT_JSON"):
        sa = gspread.service_account_from_dict(json.loads(os.getenv("SERVICE_ACCOUNT_JSON")))
    else:
        raise ValueError("Either FILE_PATH (file path) or SERVICE_ACCOUNT_JSON (JSON content) must be provided")
    return sa.open(os.getenv("DOCUMENT_NAME"))


def parse_number(value):
    try:
        return float(str(value).replace(",", ".")) if value not in (None, "", "None") else 0.0
    except ValueError:
        return 0.0


def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"activities": {}, "texts": {}}


def save_ledger(ledger):
    tmp = LEDGER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER_FILE)


def slot_cells(date):
    """Cells for the day and time of day of an activity."""
    day_of_week = (date.weekday() + 1) % 7  # Sunday = 0
    text_col = chr(ord("B") + day_of_week * 2)
    value_col = chr(ord(text_col) + 1)
    first = 3 if date.hour < 13 else 6
    return {
        "other_text": f"{text_col}{first}", "other_value": f"{value_col}{first}",
        "run_text": f"{text_col}{first + 1}", "run_value": f"{value_col}{first + 1}",
        "notes": f"{text_col}{first + 2}",
    }


def week_title(date):
    """Name of the week worksheet (weeks run from Sunday to Saturday)."""
    days_since_sunday = (date.weekday() + 1) % 7
    week_start = date - timedelta(days=days_since_sunday)
    week_number = date.isocalendar()[1]
    if date.weekday() == 6:  # Sunday already belongs to the next week
        week_number += 1
    return f"KW{week_number}{week_start.strftime('%y')}", week_number, week_start


def activity_date(activity):
    return datetime.fromisoformat(activity["start_date_local"].replace("Z", ""))


class SheetsClient:
    def __init__(self):
        self.sh = open_spreadsheet()
        self._worksheets_cache = None
        self._worksheets_cache_timestamp = None
        self._cache_validity_minutes = 5

    def get_first_not_completed_day(self):
        """First day in the newest week worksheet without any entry."""
        print("Getting first not completed day...")
        latest = self.sh.worksheets()[2]
        week_start = datetime.strptime(latest.acell("B1").value.split()[3], "%d.%m.%Y")
        data_range = latest.get(range_name="B3:O8", major_dimension=Dimension.cols)
        while data_range and all(x in ["", "0", None] for x in data_range[-1]):
            data_range.pop()
        first_not_completed_day = week_start + timedelta(days=len(data_range) / 2)
        print("First not completed day:", first_not_completed_day)
        return first_not_completed_day

    def _get_worksheets_cached(self):
        now = datetime.now()
        if (self._worksheets_cache is not None
                and (now - self._worksheets_cache_timestamp).total_seconds() < self._cache_validity_minutes * 60):
            return self._worksheets_cache
        for attempt in range(2):
            try:
                self._worksheets_cache = self.sh.worksheets()
                self._worksheets_cache_timestamp = now
                return self._worksheets_cache
            except APIError as e:
                if e.code != 429 or attempt:
                    raise
                print("Rate limit exceeded while fetching worksheets list. Waiting 60 seconds...")
                time.sleep(60)

    def _clear_worksheets_cache(self):
        self._worksheets_cache = None
        self._worksheets_cache_timestamp = None

    def week_worksheet(self, date):
        """Week worksheet for a date; created from the "leer" (empty) template if needed."""
        title, week_number, week_start = week_title(date)
        existing = next((ws for ws in self._get_worksheets_cached() if ws.title == title), None)
        if existing:
            return existing

        print("Creating new worksheet:", title)
        self._clear_worksheets_cache()
        try:
            template = self.sh.worksheet("leer")
            worksheet = self.sh.duplicate_sheet(source_sheet_id=template.id, insert_sheet_index=2, new_sheet_name=title)
        except APIError as e:
            if "already exists" not in str(e):
                raise
            return self.sh.worksheet(title)

        # Overview ("Übersicht"): name in column A, link in column K
        overview = self.sh.worksheet("Übersicht")
        col_a = overview.col_values(1)
        col_k = overview.col_values(11)
        if title not in col_a:
            overview.update_acell(f"A{len(col_a) + 1}", title)
        if not any("HYPERLINK(" in str(v) and title in str(v) for v in col_k):
            url = f"https://docs.google.com/spreadsheets/d/{self.sh.id}/edit#gid={worksheet.id}"
            overview.update_acell(f"K{len(col_k) + 1}", f'=HYPERLINK("{url}";"{title}")')

        week_end = week_start + timedelta(days=6)
        worksheet.update_acell("B1", f"KW {week_number}{week_start.strftime('%y')} - {week_start:%d.%m.%Y} - {week_end:%d.%m.%Y}")
        return worksheet

    def _read(self, worksheet, cells):
        result = worksheet.batch_get(cells)
        return {cell: (r[0][0] if r and r[0] else None) for cell, r in zip(cells, result)}

    def _write(self, worksheet, updates):
        """updates: {cell: value}. Numbers are stored as numbers, texts as they are."""
        if not updates:
            return
        data = [{"range": cell, "values": [[value]]} for cell, value in updates.items()]
        for attempt in range(2):
            try:
                worksheet.batch_update(data)
                return
            except APIError as e:
                if e.code != 429 or attempt:
                    raise
                print("Rate limit exceeded during batch update. Waiting 60 seconds...")
                time.sleep(60)

    def set_new_entry_from_json(self, activity, with_run_texts=True):
        """Write a Strava activity into the sheet.

        Runs: kilometers (2 decimals, added to the cell); with with_run_texts also the description as main cell and
        the private note as notes. Others: description or name, minutes, private note.
        Returns False if the activity is already in the ledger.
        """
        activity_id = str(activity["id"])
        with ledger_lock:
            if activity_id in load_ledger()["activities"]:
                print(f"Activity {activity_id} already in sheet, skipping")
                return False

        date = activity_date(activity)
        worksheet = self.week_worksheet(date)
        cells = slot_cells(date)
        is_run = activity["sport_type"] in ("Run", "TrailRun", "VirtualRun")
        value_cell = cells["run_value"] if is_run else cells["other_value"]
        text_cell = cells["run_text"] if is_run else cells["other_text"]
        current = self._read(worksheet, [value_cell, text_cell, cells["notes"]])

        if is_run:
            value = round(activity["distance"] / 1000, 2)
            texts = {text_cell: activity.get("description"), cells["notes"]: activity.get("private_note")} if with_run_texts else {}
        else:
            value = round(activity["moving_time"] / 60)
            texts = {text_cell: activity.get("description") or activity.get("name"), cells["notes"]: activity.get("private_note")}

        updates = {value_cell: round(parse_number(current[value_cell]) + value, 2)}
        for cell, text in texts.items():
            if text:
                updates[cell] = f"{current[cell]}\n{text}" if current[cell] else text
        self._write(worksheet, updates)

        with ledger_lock:
            ledger = load_ledger()
            ledger["activities"][activity_id] = {"sheet": worksheet.title, "cell": value_cell, "value": value,
                                                 "at": datetime.now().isoformat(timespec="seconds")}
            save_ledger(ledger)
        print(f"Activity {activity_id} -> {worksheet.title} {value_cell} (+{value})")
        return True

    def read_run_cells(self, start_local):
        """Current main cell, kilometers and notes of the run block."""
        date = datetime.fromisoformat(start_local)
        cells = slot_cells(date)
        keys = ("run_text", "run_value", "notes")
        values = self._read(self.week_worksheet(date), [cells[k] for k in keys])
        return {k: values[cells[k]] for k in keys}

    def set_run_texts(self, start_local, main_text=None, notes=None):
        """Set main cell and notes of the run block (morning or afternoon of that day).

        Text RunSync wrote before is replaced; other text stays and the new text goes below it.
        """
        date = datetime.fromisoformat(start_local)
        worksheet = self.week_worksheet(date)
        cells = slot_cells(date)
        wanted = {cells["run_text"]: main_text, cells["notes"]: notes}
        wanted = {cell: text.strip() for cell, text in wanted.items() if text and text.strip()}
        if not wanted:
            return {"sheet": worksheet.title, "cells": []}
        current = self._read(worksheet, list(wanted))

        with ledger_lock:
            ledger = load_ledger()
            updates = {}
            for cell, text in wanted.items():
                key = f"{worksheet.title}!{cell}"
                old = current[cell] or ""
                previous = ledger["texts"].get(key)
                if text in old:
                    pass
                elif previous and previous in old:
                    updates[cell] = old.replace(previous, text)
                elif old.strip():
                    updates[cell] = f"{old}\n{text}"
                else:
                    updates[cell] = text
                ledger["texts"][key] = text
            self._write(worksheet, updates)
            save_ledger(ledger)
        return {"sheet": worksheet.title, "cells": list(updates)}

    def get_empty_p4_p7_worksheets(self):
        """Week worksheets without P4/P7 values, from the newest down to the first filled one."""
        print("Getting empty P4/P7 worksheets...")
        worksheets = [ws for ws in self._get_worksheets_cached() if ws.title not in ["Übersicht", "leer"]]
        empty = []
        for i, ws in enumerate(worksheets):
            if i:
                time.sleep(0.3)  # Google rate limit
            for attempt in range(2):
                try:
                    values = ws.batch_get(["P4", "P7"])
                    break
                except APIError as e:
                    if e.code != 429 or attempt:
                        raise
                    time.sleep(60)
            p4 = values[0][0][0] if values[0] and values[0][0] else None
            p7 = values[1][0][0] if values[1] and values[1][0] else None
            if p4 in (None, "", "0") and p7 in (None, "", "0"):
                empty.append(ws)
            else:
                print(f"Found non-empty P4/P7 in worksheet {ws.title} (P4: {p4}, P7: {p7})")
                break
        print(f"Found {len(empty)} empty P4/P7 worksheets.")
        return empty

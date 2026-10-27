"""Google Sheets: the lactate log (worksheet RawData, one row per lactate measurement).

The sheet is analysed by a separate project, which finds the columns by their header. RunSync only writes the
input columns and leaves the formula columns (Rep Time (s), Speed, ...) alone. Rows are found by the Strava ID
column, so a corrected workout replaces its rows instead of adding new ones.

Values are written raw in the sheet's own units: dates as day numbers, times as fractions of a day, and paces
like the athlete types them (3:27 min/km is stored as 3:27 hours, format h:mm).
"""
import os
from datetime import date

import gspread

from sheets_client import open_spreadsheet

WORKSHEET = "RawData"
COLUMNS = {
    "date": "Date", "session": "Session", "workout_type": "Workout Type", "rep_dist_m": "Rep Dist (m)",
    "rep_time_s": "Rep Time", "surface": "Surface", "incline": "Incline",
    "lactate": "Lactate (mmol/L)", "rep_no": "Rep #", "rest_type": "Rest Type", "rest_s": "Rest (s)", "hr": "HR avg",
    "temp_c": "Temp (°C)", "humidity": "Humidity (%)", "shoes": "Shoes",
    "prev_avg": "Prev Avg Pace", "prev_fastest": "Prev Fastest Pace", "prev_slowest": "Prev Slowest Pace",
    "strava_id": "Strava ID",
}
# Pace (min/km) is left empty like in the athlete's recent rows; the analysis computes it from distance and time.
# Added by RunSync if missing: pace statistics of the reps before the test, and the activity the row belongs to
NEW_COLUMNS = ["prev_avg", "prev_fastest", "prev_slowest", "strava_id"]
PACE_KEYS = ("pace_s_per_km", "prev_avg", "prev_fastest", "prev_slowest")
EXCEL_EPOCH = date(1899, 12, 30)


def cell_value(key, value):
    if value is None:
        return ""
    if key == "date":
        return (date.fromisoformat(value) - EXCEL_EPOCH).days
    if key == "rep_time_s":
        return value / 86400
    if key in PACE_KEYS:
        return value / 1440  # m:ss per km written as h:mm
    return value


def column_letter(index):
    return gspread.utils.rowcol_to_a1(1, index + 1)[:-1]


class LactateClient:
    def __init__(self, sheet_id=None):
        self.sheet_id = sheet_id or os.getenv("LACTATE_SHEET_ID")
        if not self.sheet_id:
            raise ValueError("LACTATE_SHEET_ID is not set")
        self.ws = open_spreadsheet(self.sheet_id).worksheet(WORKSHEET)

    def header(self):
        """Column index per key; adds the RunSync columns at the end if they are missing."""
        header = self.ws.row_values(1)
        missing = [k for k in NEW_COLUMNS if COLUMNS[k] not in header]
        if missing:
            start = len(header)
            if start + len(missing) > self.ws.col_count:
                self.ws.add_cols(start + len(missing) - self.ws.col_count)
            self.ws.update(range_name=f"{column_letter(start)}1", values=[[COLUMNS[k] for k in missing]])
            for i, key in enumerate(missing):
                col = column_letter(start + i)
                fmt = {"numberFormat": {"type": "TEXT"}} if key == "strava_id" else {"numberFormat": {"type": "TIME", "pattern": "h:mm"}}
                self.ws.format(f"{col}2:{col}", fmt)
            header = self.ws.row_values(1)
        lookup = {name: i for i, name in enumerate(header)}
        absent = [name for name in COLUMNS.values() if name not in lookup]
        if absent:
            raise RuntimeError(f"Lactate sheet has no column {', '.join(absent)}")
        return {key: lookup[name] for key, name in COLUMNS.items()}

    def write_rows(self, strava_id, rows):
        """Replace the rows of this activity (Strava ID) with the given rows. Returns the sheet row numbers."""
        cols = self.header()
        dates = self.ws.col_values(cols["date"] + 1)
        ids = self.ws.col_values(cols["strava_id"] + 1)
        mine = [i + 1 for i, v in enumerate(ids) if i and str(v) == str(strava_id)]
        # New rows go below the last row with a date (the rows below are prepared with formulas and formats)
        free = len(dates) + 1
        targets = mine[:len(rows)]
        while len(targets) < len(rows):
            targets.append(free)
            free += 1
        if max(targets, default=0) > self.ws.row_count:
            raise RuntimeError("Lactate sheet is full, add rows at the bottom")

        data = []
        for number, row in zip(targets, rows):
            for key, col in cols.items():
                data.append({"range": f"{column_letter(col)}{number}", "values": [[cell_value(key, row.get(key))]]})
        # Rows of an earlier version of this workout that are no longer needed
        cleared = mine[len(rows):]
        for number in cleared:
            for key, col in cols.items():
                data.append({"range": f"{column_letter(col)}{number}", "values": [[""]]})
        if data:
            self.ws.batch_update(data, value_input_option="RAW")
        return {"rows": targets, "cleared": cleared}

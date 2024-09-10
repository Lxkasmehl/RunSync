import locale
import os
import time
from datetime import datetime, timedelta

import gspread
import math

from dotenv import load_dotenv
from gspread.exceptions import APIError
from gspread.utils import Dimension

# Load environment variables from .env file
load_dotenv()

# Create a Google Sheets client using the service account credentials
sa = gspread.service_account(filename=os.getenv('FILE_PATH'))
sh = sa.open(os.getenv('DOCUMENT_NAME'))

# Set the locale to German for date formatting
locale.setlocale(locale.LC_ALL, 'de_DE')

class SheetsClient:
    """
    A class to interact with Google Sheets
    """
    def get_first_not_completed_day(self):
        """
        Get the first not completed day in the latest week worksheet
        """
        print("Getting first not completed day...")

        # Get the latest week worksheet
        latestWeekWorksheet = sh.worksheets()[2]

        # Extract the week and timeframe from cell B1
        weekAndTimeframe = latestWeekWorksheet.acell("B1").value.split()

        # Parse the week start date from the extracted timeframe
        weekStartDate = datetime.strptime(weekAndTimeframe[3], '%d.%m.%Y')

        # Get the data range from B3:O8, column-major
        data_range = latestWeekWorksheet.get(range_name='B3:O8', major_dimension=Dimension.cols)

        # Remove empty rows from the data range
        while data_range:
            if all(x in ['', '0', None] for x in data_range[-1]):
                data_range.pop()
            else:
                break

        # Calculate the first not completed day
        first_not_completed_day = weekStartDate + timedelta(days=len(data_range) / 2)
        print("First not completed day:", first_not_completed_day)
        return first_not_completed_day

    def set_new_entry_from_json(self, activityDetails):
        """
        Set a new entry in the Google Sheets from a JSON object
        """
        print("Setting new entry from JSON...")

        # Extract the date from the activity details
        date_str = activityDetails['start_date_local']
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

        # Calculate the week number and worksheet title
        week_number = date.isocalendar()[1]
        worksheet_title = f"KW{week_number}{date.strftime('%y')}"

        # Get the list of existing worksheets
        worksheets = sh.worksheets()

        # Check if the worksheet already exists
        existing_worksheet = next((ws for ws in worksheets if ws.title == worksheet_title), None)

        if existing_worksheet is None:
            print("Creating new worksheet:", worksheet_title)
            # Create a new worksheet from a template
            template_worksheet = sh.worksheet("leer")
            new_worksheet = sh.duplicate_sheet(source_sheet_id=template_worksheet.id, insert_sheet_index=2,
                                               new_sheet_name=worksheet_title)

            # Update the overview worksheet with the new worksheet title
            overview_ws = sh.worksheet("Übersicht")
            cell_list_A = overview_ws.col_values(1)
            cell_list_J = overview_ws.col_values(10)

            if worksheet_title not in cell_list_A:
                next_available_row_A = len(cell_list_A) + 1
                overview_ws.update_acell(f"A{next_available_row_A}", worksheet_title)

            if worksheet_title not in cell_list_J:
                next_available_row_J = len(cell_list_J) + 1
                worksheet_url = f"https://docs.google.com/spreadsheets/d/{sh.id}/edit#gid={sh.worksheet(worksheet_title).id}"
                overview_ws.update_acell(f"J{next_available_row_J}",
                                         f'=HYPERLINK("{worksheet_url}";"{worksheet_title}")')

            # Set the header row in the new worksheet
            new_worksheet.update_acell("B1:O1",
                                       f"KW {week_number}{date.strftime('%y')} - {date - timedelta(days=date.weekday()):%d.%m.%Y} - {date + timedelta(days=6 - date.weekday()):%d.%m.%Y}")
        else:
            print("Using existing worksheet:", worksheet_title)
            new_worksheet = existing_worksheet

        # Calculate the day of the week and column offset
        day_of_week = date.weekday()
        column_offset = day_of_week * 2
        column_range = chr(ord('B') + column_offset) + ":" + chr(ord('B') + column_offset + 1)

        # Calculate the row range based on the time of day
        row_range = "3:5" if date.hour < 12 else "6:8"

        # Define a helper function to update a cell with a text value
        def update_cell(cell, text):
            """
            Update a cell with a text value, retrying on API errors
            """
            print(f"Updating cell {cell} with text '{text}'...")
            retry_count = 0
            max_retries = 8
            backoff_time = 1

            while retry_count < max_retries:
                try:
                    existing_value = new_worksheet.acell(cell).value
                    if existing_value:
                        new_worksheet.update_acell(cell, f"{existing_value}\n{text}")
                    else:
                        new_worksheet.update_acell(cell, text)
                    break
                except APIError as e:
                    if e.code == 429:
                        print(f"Rate limit exceeded. Waiting for {backoff_time} seconds...")
                        time.sleep(backoff_time)
                        retry_count += 1
                        backoff_time *= 2
                    else:
                        raise

        # Define a helper function to update a cell with a numeric value
        def update_cell_additive(cell, value):
            """
            Update a cell with a numeric value, retrying on API errors
            """
            print(f"Updating cell {cell} with value {value}...")
            retry_count = 0
            max_retries = 8
            backoff_time = 1

            while retry_count < max_retries:
                try:
                    existing_value = new_worksheet.acell(cell).value
                    if existing_value:
                        try:
                            existing_value = float(existing_value.replace(',', '.'))
                        except ValueError:
                            existing_value = 0
                        new_value = existing_value + value
                        new_worksheet.update_acell(cell, locale.format_string("%.2f", new_value))
                    else:
                        new_worksheet.update_acell(cell, locale.format_string("%.2f", value))
                    break
                except APIError as e:
                    if e.code == 429:
                        print(f"Rate limit exceeded. Waiting for {backoff_time} seconds...")
                        time.sleep(backoff_time)
                        retry_count += 1
                        backoff_time *= 2
                    else:
                        raise

        # Process the activity details based on the sport type
        if activityDetails['sport_type'] == 'Run':
            print("Processing Run activity...")
            # Update cells for Run activity
            if 'description' in activityDetails:
                update_cell(column_range[0] + str(int(row_range.split(":")[0]) + 1), activityDetails['description'])
            if 'private_note' in activityDetails:
                update_cell(column_range[0] + row_range.split(":")[1], activityDetails['private_note'])
            distance_km = activityDetails['distance'] / 1000
            rounded_distance = math.floor(distance_km * 2 + 0.5) / 2
            update_cell_additive(column_range[2] + str(int(row_range.split(":")[0]) + 1), rounded_distance)
        else:
            print("Processing other activity...")
            # Update cells for other activities
            if activityDetails['description'] is not None and activityDetails['description'] != '':
                update_cell(column_range[0] + row_range.split(":")[0], activityDetails['description'])
            elif 'name' in activityDetails:
                update_cell(column_range[0] + row_range.split(":")[0], activityDetails['name'])
            if 'private_note' in activityDetails:
                update_cell(column_range[0] + row_range.split(":")[1], activityDetails['private_note'])
            if 'moving_time' in activityDetails:
                moving_time_minutes = round(activityDetails['moving_time'] / 60)
                update_cell_additive(column_range[2] + row_range.split(":")[0], moving_time_minutes)

    def get_empty_p4_p7_worksheets(self):
        print("Getting empty P4/P7 worksheets...")
        worksheets = [ws for ws in sh.worksheets() if ws.title not in ["Übersicht", "leer"]]
        for i, ws in enumerate(worksheets):
            p4_value = ws.acell("P4").value
            p7_value = ws.acell("P7").value
            if p4_value and p7_value:
                print("Found non-empty P4/P7 worksheets:", worksheets[0:i])
                return worksheets[0:i]
        print("No non-empty P4/P7 worksheets found.")
        return None
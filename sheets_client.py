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

    def __init__(self):
        # Cache for worksheets to avoid repeated API calls
        self._worksheets_cache = None
        self._worksheets_cache_timestamp = None
        self._cache_validity_minutes = 5  # Cache is valid for 5 minutes
    
    def _get_worksheets_cached(self):
        """
        Get worksheets with caching to reduce API calls
        """
        current_time = datetime.now()
        
        # Check if cache is still valid
        if (self._worksheets_cache is not None and 
            self._worksheets_cache_timestamp is not None and
            (current_time - self._worksheets_cache_timestamp).total_seconds() < self._cache_validity_minutes * 60):
            return self._worksheets_cache
        
        # Cache expired or doesn't exist, fetch fresh data
        print("Fetching fresh worksheets list...")
        try:
            self._worksheets_cache = sh.worksheets()
            self._worksheets_cache_timestamp = current_time
            return self._worksheets_cache
        except APIError as e:
            if e.code == 429:  # Rate limit exceeded
                print("Rate limit exceeded while fetching worksheets list. Waiting 60 seconds...")
                time.sleep(60)
                # Retry once
                try:
                    self._worksheets_cache = sh.worksheets()
                    self._worksheets_cache_timestamp = current_time
                    return self._worksheets_cache
                except Exception as retry_e:
                    print(f"Failed to fetch worksheets after retry: {retry_e}")
                    raise
            else:
                raise
    
    def _clear_worksheets_cache(self):
        """
        Clear the worksheets cache (call this when creating new worksheets)
        """
        self._worksheets_cache = None
        self._worksheets_cache_timestamp = None

    def set_new_entry_from_json(self, activityDetails):
        """
        Set a new entry in the Google Sheets from a JSON object
        """
        print("Setting new entry from JSON...")

        # Extract the date from the activity details
        date_str = activityDetails['start_date_local']
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

        # Calculate the week number and worksheet title for Sunday-Saturday weeks
        # Get the start of the week (Sunday) for the given date
        days_since_sunday = (date.weekday() + 1) % 7  # Convert Monday=0 to Sunday=0
        week_start = date - timedelta(days=days_since_sunday)
        
        # Calculate week number based on Sunday-Saturday weeks
        # Use the year of the week start date
        year = week_start.year
        # Calculate week number: week of year starting from first Sunday
        first_sunday_of_year = datetime(year, 1, 1)
        days_to_first_sunday = (6 - first_sunday_of_year.weekday()) % 7
        if days_to_first_sunday == 0 and first_sunday_of_year.weekday() != 6:
            days_to_first_sunday = 7
        first_sunday_of_year += timedelta(days=days_to_first_sunday)

                # Calculate the week number and worksheet title
        week_number = date.isocalendar()[1]
        
        # If the weekday is Sunday, increment the week number by 1
        if date.weekday() == 6:  # Sunday is 6 in Python's weekday() (Monday=0, Sunday=6)
            week_number += 1

        worksheet_title = f"KW{week_number}{week_start.strftime('%y')}"

        # Get the list of existing worksheets from cache
        worksheets = self._get_worksheets_cached()

        # Check if the worksheet already exists
        existing_worksheet = next((ws for ws in worksheets if ws.title == worksheet_title), None)
        
        # If worksheet doesn't exist, clear cache immediately to prevent race conditions
        if existing_worksheet is None:
            self._clear_worksheets_cache()

        if existing_worksheet is None:
            print("Creating new worksheet:", worksheet_title)
            
            # Try to create the worksheet, handle race conditions
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Create a new worksheet from a template
                    template_worksheet = sh.worksheet("leer")
                    new_worksheet = sh.duplicate_sheet(source_sheet_id=template_worksheet.id, insert_sheet_index=2,
                                                       new_sheet_name=worksheet_title)
                    break  # Success, exit retry loop
                except APIError as e:
                    if "already exists" in str(e) and attempt < max_retries - 1:
                        print(f"Worksheet {worksheet_title} already exists, retrying... (attempt {attempt + 1})")
                        # Clear cache and try to get the existing worksheet
                        self._clear_worksheets_cache()
                        worksheets = self._get_worksheets_cached()
                        existing_worksheet = next((ws for ws in worksheets if ws.title == worksheet_title), None)
                        if existing_worksheet:
                            print(f"Found existing worksheet {worksheet_title}, using it instead")
                            new_worksheet = existing_worksheet
                            break
                        time.sleep(0.5)  # Small delay before retry
                    else:
                        raise  # Re-raise if it's not a duplicate error or we're out of retries

            # Update the overview worksheet with the new worksheet title
            overview_ws = sh.worksheet("Übersicht")
            cell_list_A = overview_ws.col_values(1)
            cell_list_J = overview_ws.col_values(10)

            # Collect overview updates to do them in batch
            overview_updates = []
            
            if worksheet_title not in cell_list_A:
                next_available_row_A = len(cell_list_A) + 1
                overview_updates.append((f"A{next_available_row_A}", worksheet_title))

            # Check if hyperlink already exists in column J
            hyperlink_exists = False
            for i, cell_value in enumerate(cell_list_J):
                if cell_value and ('=HYPERLINK(' in str(cell_value) or 'HYPERLINK(' in str(cell_value)) and worksheet_title in str(cell_value):
                    hyperlink_exists = True
                    break
            
            if not hyperlink_exists:
                next_available_row_J = len(cell_list_J) + 1
                # Use the new_worksheet object directly instead of looking it up again
                worksheet_url = f"https://docs.google.com/spreadsheets/d/{sh.id}/edit#gid={new_worksheet.id}"
                # Use proper HYPERLINK formula syntax with semicolon separator
                hyperlink_formula = f'=HYPERLINK("{worksheet_url}";"{worksheet_title}")'
                overview_updates.append((f"J{next_available_row_J}", hyperlink_formula))

            # Update regular cells in batch
            if overview_updates:
                batch_data = [{'range': cell, 'values': [[value]]} for cell, value in overview_updates]
                overview_ws.batch_update(batch_data)
                print(f"Updated {len(overview_updates)} regular cells in batch")
            
            # Update hyperlink separately using update_acell to ensure it's treated as a formula
            if not hyperlink_exists:
                overview_ws.update_acell(f"J{next_available_row_J}", hyperlink_formula)
                print(f"Updated hyperlink in J{next_available_row_J}")

            # Set the header row in the new worksheet with Sunday-Saturday week range
            week_start_sunday = week_start
            week_end_saturday = week_start_sunday + timedelta(days=6)
            new_worksheet.update_acell("B1:O1",
                                       f"KW {week_number}{week_start_sunday.strftime('%y')} - {week_start_sunday:%d.%m.%Y} - {week_end_saturday:%d.%m.%Y}")
        else:
            print("Using existing worksheet:", worksheet_title)
            new_worksheet = existing_worksheet

        # Calculate the day of the week and column offset for Sunday-Saturday format
        # Convert to Sunday=0, Monday=1, ..., Saturday=6
        day_of_week = (date.weekday() + 1) % 7
        column_offset = day_of_week * 2
        column_range = chr(ord('B') + column_offset) + ":" + chr(ord('B') + column_offset + 1)

        # Calculate the row range based on the time of day
        row_range = "3:5" if date.hour < 13 else "6:8"

        # Collect all updates to do them in batches
        updates = []
        
        # Define a helper function to collect cell updates
        def collect_update(cell, text, is_additive=False, existing_value=None):
            """
            Collect a cell update for batch processing
            """
            if is_additive:
                try:
                    # Handle both None and 'None' string cases
                    if existing_value and existing_value != 'None' and str(existing_value).strip():
                        # Convert to string first, then replace comma with dot, then convert to float
                        existing_val = float(str(existing_value).replace(',', '.'))
                    else:
                        existing_val = 0
                except (ValueError, TypeError) as e:
                    existing_val = 0
                
                new_val = existing_val + text
                formatted_val = locale.format_string("%.2f", new_val)
                updates.append((cell, formatted_val))
            else:
                if existing_value:
                    updates.append((cell, f"{existing_value}\n{text}"))
                else:
                    updates.append((cell, text))
        
        # Define a helper function to get existing values in batch
        def get_existing_values_batch(cells):
            """
            Get multiple cell values in one API call
            """
            try:
                # Use batch_get to get multiple cells at once
                cell_list = [f"{cell}" for cell in cells]
                result = new_worksheet.batch_get(cell_list)
                
                # batch_get returns a list of lists, where each inner list contains values for one range
                # For individual cells, each cell gets its own list in the result
                result_dict = {}
                for i, cell in enumerate(cells):
                    if i < len(result) and result[i] and len(result[i]) > 0:
                        # Get the first (and only) value from the cell's result list
                        cell_value = result[i][0] if result[i][0] else None
                        # If the cell_value is still a list (shouldn't happen but just in case), get the first element
                        if isinstance(cell_value, list) and len(cell_value) > 0:
                            cell_value = cell_value[0]
                        result_dict[cell] = cell_value
                    else:
                        result_dict[cell] = None
                
                return result_dict
            except Exception as e:
                print(f"Error getting batch values: {e}")
                return {cell: None for cell in cells}

        # Get all existing values we need in one batch call
        cells_to_check = []
        if activityDetails['sport_type'] == 'Run':
            cells_to_check.extend([
                column_range[0] + str(int(row_range.split(":")[0]) + 1),  # Description cell
                column_range[0] + row_range.split(":")[1],                 # Private note cell
                column_range[2] + str(int(row_range.split(":")[0]) + 1)   # Distance cell
            ])
        else:
            cells_to_check.extend([
                column_range[0] + row_range.split(":")[0],                # Description/name cell
                column_range[0] + row_range.split(":")[1],                # Private note cell
                column_range[2] + row_range.split(":")[0]                 # Moving time cell
            ])
        
        # Add a small delay to ensure any previous updates are processed
        time.sleep(0.2)
        
        existing_values = get_existing_values_batch(cells_to_check)
        
        # Process the activity details based on the sport type
        if activityDetails['sport_type'] == 'Run':
            print("Processing Run activity...")
            # Update cells for Run activity
            if 'description' in activityDetails:
                collect_update(
                    column_range[0] + str(int(row_range.split(":")[0]) + 1), 
                    activityDetails['description'],
                    existing_value=existing_values[column_range[0] + str(int(row_range.split(":")[0]) + 1)]
                )
            if 'private_note' in activityDetails:
                collect_update(
                    column_range[0] + row_range.split(":")[1], 
                    activityDetails['private_note'],
                    existing_value=existing_values[column_range[0] + row_range.split(":")[1]]
                )
            distance_km = activityDetails['distance'] / 1000
            rounded_distance = math.floor(distance_km * 2 + 0.5) / 2
            collect_update(
                column_range[2] + str(int(row_range.split(":")[0]) + 1), 
                rounded_distance,
                is_additive=True,
                existing_value=existing_values[column_range[2] + str(int(row_range.split(":")[0]) + 1)]
            )
        else:
            print("Processing other activity...")
            # Update cells for other activities
            if activityDetails['description'] is not None and activityDetails['description'] != '':
                collect_update(
                    column_range[0] + row_range.split(":")[0], 
                    activityDetails['description'],
                    existing_value=existing_values[column_range[0] + row_range.split(":")[0]]
                )
            elif 'name' in activityDetails:
                collect_update(
                    column_range[0] + row_range.split(":")[0], 
                    activityDetails['name'],
                    existing_value=existing_values[column_range[0] + row_range.split(":")[0]]
                )
            if 'private_note' in activityDetails:
                collect_update(
                    column_range[0] + row_range.split(":")[1], 
                    activityDetails['private_note'],
                    existing_value=existing_values[column_range[0] + row_range.split(":")[1]]
                )
            if 'moving_time' in activityDetails:
                moving_time_minutes = round(activityDetails['moving_time'] / 60)
                collect_update(
                    column_range[2] + row_range.split(":")[0], 
                    moving_time_minutes,
                    is_additive=True,
                    existing_value=existing_values[column_range[2] + row_range.split(":")[0]]
                )
        
        # Execute all updates in one batch call
        if updates:
            print(f"Executing {len(updates)} updates in batch...")
            try:
                # Use batch_update with proper format: list of dicts with 'range' and 'values'
                batch_data = [{'range': cell, 'values': [[value]]} for cell, value in updates]
                new_worksheet.batch_update(batch_data)
                print("Batch update completed successfully!")
                
                # Add small delay after successful batch update to respect rate limits
                time.sleep(0.2)
                
            except APIError as e:
                if e.code == 429:
                    print("Rate limit exceeded during batch update. Waiting 60 seconds...")
                    time.sleep(60)
                    # Retry the batch update
                    try:
                        new_worksheet.batch_update(batch_data)
                        print("Batch update retry completed successfully!")
                        time.sleep(0.2)  # Small delay after retry
                    except Exception as retry_e:
                        print(f"Batch update retry failed: {retry_e}")
                        # Fallback to individual updates if batch fails
                        for cell, value in updates:
                            try:
                                new_worksheet.update_acell(cell, value)
                                time.sleep(0.5)  # Longer delay for individual updates
                            except Exception as fallback_e:
                                print(f"Failed to update {cell}: {fallback_e}")
                else:
                    print(f"Batch update failed: {e}")
                    # Fallback to individual updates
                    for cell, value in updates:
                        try:
                            new_worksheet.update_acell(cell, value)
                            time.sleep(0.5)  # Longer delay for individual updates
                        except Exception as fallback_e:
                            print(f"Failed to update {cell}: {fallback_e}")

    def get_empty_p4_p7_worksheets(self):
        print("Getting empty P4/P7 worksheets...")
        # Use cached worksheets to avoid repeated API calls
        worksheets = [ws for ws in self._get_worksheets_cached() if ws.title not in ["Übersicht", "leer"]]
        
        if not worksheets:
            print("No worksheets found.")
            return None
        
        print(f"Checking {len(worksheets)} worksheets with rate limiting...")
        
        # Get all P4 and P7 values in one batch call per worksheet
        empty_worksheets = []
        for i, ws in enumerate(worksheets):
            try:
                # Add rate limiting - wait 0.3 seconds between API calls to avoid 429 errors
                if i > 0:  # Don't wait before the first call
                    time.sleep(0.3)
                
                # Progress indicator every 10 worksheets
                if i % 10 == 0:
                    print(f"Progress: {i}/{len(worksheets)} worksheets checked...")
                
                # Get both P4 and P7 values in one API call
                p4_p7_values = ws.batch_get(["P4", "P7"])
                p4_value = p4_p7_values[0][0] if p4_p7_values[0] else None
                p7_value = p4_p7_values[0][1] if len(p4_p7_values[0]) > 1 else None
                
                # Check if both P4 and P7 are empty (None, empty string, or "0")
                p4_empty = not p4_value or p4_value == "" or p4_value == "0"
                p7_empty = not p7_value or p7_value == "" or p7_value == "0"
                
                if p4_empty and p7_empty:
                    empty_worksheets.append(ws)
                else:
                    print(f"Found non-empty P4/P7 in worksheet {ws.title} (P4: {p4_value}, P7: {p7_value})")
                    # Stop when we find the first non-empty worksheet
                    break
                    
            except APIError as e:
                if e.code == 429:  # Rate limit exceeded
                    print(f"Rate limit exceeded while checking worksheet {ws.title}. Waiting 60 seconds...")
                    time.sleep(60)  # Wait 60 seconds for rate limit to reset
                    # Retry the same worksheet
                    try:
                        p4_p7_values = ws.batch_get(["P4", "P7"])
                        p4_value = p4_p7_values[0][0] if p4_p7_values[0] else None
                        p7_value = p4_p7_values[0][1] if len(p4_p7_values[0]) > 1 else None
                        
                        p4_empty = not p4_value or p4_value == "" or p4_value == "0"
                        p7_empty = not p7_value or p7_value == "" or p7_value == "0"
                        
                        if p4_empty and p7_empty:
                            empty_worksheets.append(ws)
                        else:
                            print(f"Found non-empty P4/P7 in worksheet {ws.title} after retry (P4: {p4_value}, P7: {p7_value})")
                            break
                    except Exception as retry_e:
                        print(f"Error retrying worksheet {ws.title}: {retry_e}")
                        continue
                else:
                    print(f"Error checking worksheet {ws.title}: {e}")
                    continue
            except Exception as e:
                print(f"Error checking worksheet {ws.title}: {e}")
                continue
        
        print(f"Found {len(empty_worksheets)} empty P4/P7 worksheets.")
        return empty_worksheets
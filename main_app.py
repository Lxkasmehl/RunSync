import time
from datetime import datetime, timedelta

from garmin_client import GarminClient
from strava_client import StravaClient
from sheets_client import SheetsClient
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc

def get_first_not_completed_day(sheets_client):
    """
    Retrieves the first not completed day from the sheets client.

    Args:
        sheets_client (SheetsClient): An instance of the SheetsClient class.

    Returns:
        datetime: The first not completed day.
    """
    # Get the first not completed day from the sheets client
    return sheets_client.get_first_not_completed_day()

def get_activities_in_timeframe(strava_client, start_date, end_date):
    """
    Retrieves all activities in a given timeframe from the Strava client.

    Args:
        strava_client (StravaClient): An instance of the StravaClient class.
        start_date (datetime): The start date of the timeframe.
        end_date (datetime): The end date of the timeframe.

    Returns:
        list: A list of activities in the given timeframe.
    """
    # Format the start and end dates as strings
    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

    # Get all activities in the given timeframe from the Strava client
    return strava_client.get_all_activities_in_timeframe(start_date_str, end_date_str)

def filter_out_yoga_activities(activities):
    """
    Filters out yoga activities from a list of activities.

    Args:
        activities (list): A list of activities.

    Returns:
        list: A list of activities with yoga activities filtered out.
    """
    # Use a list comprehension to filter out yoga activities
    return [activity for activity in activities if activity['sport_type'] != 'Yoga']

def update_sheets_with_activity_details(sheets_client, strava_client, activities):
    """
    Updates the sheets with activity details.

    Args:
        sheets_client (SheetsClient): An instance of the SheetsClient class.
        strava_client (StravaClient): An instance of the StravaClient class.
        activities (list): A list of activities.
    """
    # Iterate over the activities in reverse order
    for i, activity in enumerate(reversed(activities)):
        # Get the Strava data for the activity
        activity_details = strava_client.get_strava_data_for_activity_with_specific_ID(
            activity_id=activity['id'],
            include_efforts=False
        )

        # Update the sheets with the activity details
        sheets_client.set_new_entry_from_json(activity_details)

def update_p4_p7_worksheets(sheets_client, strava_client):
    """
    Updates the P4 and P7 worksheets.

    Args:
        sheets_client (SheetsClient): An instance of the SheetsClient class.
        strava_client (StravaClient): An instance of the StravaClient class.
    """
    # Get the empty P4 and P7 worksheets
    empty_p4_p7_worksheets = sheets_client.get_empty_p4_p7_worksheets()

    # Iterate over the worksheets
    for ws in empty_p4_p7_worksheets:
        # Get the cell value of the worksheet
        cell_value = ws.acell('B1').value

        # Split the cell value into separate values
        split_values = cell_value.split()

        # Parse the start and end dates from the split values
        start_date = datetime.strptime(split_values[3], "%d.%m.%Y")
        end_date = datetime.strptime(split_values[5], "%d.%m.%Y")

        # Check if the end date is less than or equal to the current date
        if end_date <= datetime.now():
            # Get all activities in the given timeframe
            all_activities = get_activities_in_timeframe(strava_client, start_date, end_date)

            # Filter out yoga activities
            yoga_activities = [activity for activity in all_activities if activity['sport_type'] == "Yoga"]
            yoga_count = len(yoga_activities)

            # Update the P7 cell with the yoga count
            ws.update_acell('P7', yoga_count)

            # Filter out workout activities
            workout_activities = [activity for activity in all_activities if activity['sport_type'] == "Workout"]
            workout_count = len(workout_activities)

            # Update the P4 cell with the workout count
            ws.update_acell('P4', workout_count)

def update_activities_since_first_not_completed_day(sheets_client, strava_client):
    # Get the first not completed day
    first_not_completed_day = get_first_not_completed_day(sheets_client)

    # Get the current date
    today = datetime.now()

    # Get all activities in the timeframe from the first not completed day to the current date
    activities = get_activities_in_timeframe(strava_client, first_not_completed_day, today)

    # Filter out yoga activities
    activities = filter_out_yoga_activities(activities)

    # Update the sheets with activity details
    update_sheets_with_activity_details(sheets_client, strava_client, activities)

def transfer_all_activities_not_yet_transferred_from_Strava_to_Garmin_without_stop(strava_client, garmin_client, driver, wait):
    garmin_client.login(driver, wait)
    garmin_client.open_activity_overview(driver, wait)
    garmin_client.click_first_activity_in_overview(driver, wait)

    while True:
        date = garmin_client.get_date_time_from_activity(driver, wait)
        print(date)

        start_date = (date - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        end_date = (date + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        correspondingStravaActivityWoDetails = strava_client.get_all_activities_in_timeframe(start_date, end_date)[0]
        correspondingStravaActivity = strava_client.get_strava_data_for_activity_with_specific_ID(correspondingStravaActivityWoDetails['id'], False)

        print(correspondingStravaActivity)

        if (correspondingStravaActivity['name'] not in ['Afternoon Workout', 'Morning Workout', 'Evening Workout',
                                                        'Lunch Workout', 'Night Workout']) and (
                garmin_client.get_name_from_activity(driver, wait) != correspondingStravaActivity['name']):
            garmin_client.edit_current_garmin_activity(driver, wait, correspondingStravaActivity)

        garmin_client.click_previous_button(driver, wait)
        time.sleep(3)

def main():
    """
    The main function of the script.
    """
    # Create instances of the StravaClient and SheetsClient classes
    strava_client = StravaClient()
    sheets_client = SheetsClient()
    garmin_client = GarminClient()

    driver = uc.Chrome(headless=False, use_subprocess=False)
    wait = WebDriverWait(driver, 20)

    #update_activities_since_first_not_completed_day(sheets_client, strava_client)

    #update_p4_p7_worksheets(sheets_client, strava_client)

    transfer_all_activities_not_yet_transferred_from_Strava_to_Garmin_without_stop(strava_client, garmin_client, driver, wait)


if __name__ == "__main__":
    main()
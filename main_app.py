from datetime import datetime
from strava_client import StravaClient
from sheets_client import SheetsClient

def get_first_not_completed_day(sheets_client):
    """Get the first not completed day from the sheets client."""
    return sheets_client.get_first_not_completed_day()

def get_activities_in_timeframe(strava_client, start_date, end_date):
    """Get all activities in a given timeframe from the Strava client."""
    return strava_client.get_all_activities_in_timeframe(
        start_date.strftime('%Y-%m-%d %H:%M:%S'),
        end_date.strftime('%Y-%m-%d %H:%M:%S')
    )

def filter_out_yoga_activities(activities):
    """Filter out yoga activities from a list of activities."""
    return [activity for activity in activities if activity['sport_type'] != 'Yoga']

def update_sheets_with_activity_details(sheets_client, strava_client, activities):
    """Update the sheets with activity details."""
    for i, activity in enumerate(reversed(activities)):
        activity_details = strava_client.get_strava_data_for_activity_with_specific_ID(
            activity_id=activity['id'],
            include_efforts=False
        )
        sheets_client.set_new_entry_from_json(activity_details)

def update_p4_p7_worksheets(sheets_client, strava_client):
    """Update the P4 and P7 worksheets."""
    empty_p4_p7_worksheets = sheets_client.get_empty_p4_p7_worksheets()

    for ws in empty_p4_p7_worksheets:
        cell_value = ws.acell('B1').value
        split_values = cell_value.split()

        start_date = datetime.strptime(split_values[3], "%d.%m.%Y")
        end_date = datetime.strptime(split_values[5], "%d.%m.%Y")

        if end_date <= datetime.now():
            all_activities = get_activities_in_timeframe(strava_client, start_date, end_date)

            yoga_activities = [activity for activity in all_activities if activity['sport_type'] == "Yoga"]
            yoga_count = len(yoga_activities)
            ws.update_acell('P7', yoga_count)

            workout_activities = [activity for activity in all_activities if activity['sport_type'] == "Workout"]
            workout_count = len(workout_activities)
            ws.update_acell('P4', workout_count)

def main():
    strava_client = StravaClient()
    sheets_client = SheetsClient()

    first_not_completed_day = get_first_not_completed_day(sheets_client)
    print(f"Erster nicht ausgefüllter Tag: {first_not_completed_day.strftime('%Y-%m-%d')}")

    today = datetime.now()
    activities = get_activities_in_timeframe(strava_client, first_not_completed_day, today)
    activities = filter_out_yoga_activities(activities)

    update_sheets_with_activity_details(sheets_client, strava_client, activities)
    update_p4_p7_worksheets(sheets_client, strava_client)

if __name__ == "__main__":
    main()
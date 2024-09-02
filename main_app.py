from datetime import datetime
from strava_client import StravaClient
from sheets_client import SheetsClient

def main():
    strava_client = StravaClient()
    sheets_client = SheetsClient()

    first_not_completed_day = sheets_client.get_first_not_completed_day()
    print(f"Erster nicht abgeschlossener Tag: {first_not_completed_day.strftime('%Y-%m-%d')}")

    today = datetime.now()
    activities = strava_client.get_all_activities_in_timeframe(
        first_not_completed_day.strftime('%Y-%m-%d %H:%M:%S'),
        today.strftime('%Y-%m-%d %H:%M:%S')
    )

    activities = [activity for activity in activities if activity['sport_type'] != 'Yoga']

    for i, activity in enumerate(activities):
        print(f"Aktivität {i + 1}: {activity['sport_type']}")

    for i, activity in enumerate(reversed(activities)):
        activityDetails = strava_client.get_strava_data_for_activity_with_specific_ID(activity_id=activity['id'],
                                                                                      include_efforts=False)

        sheets_client.set_new_Entry("description", activityDetails['start_date_local'], activityDetails['description'])

if __name__ == "__main__":
    main()
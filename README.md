Overview

This project is a Python script that integrates with Strava, Garmin, and Google Sheets to automate the process of tracking and logging workouts. The script uses the Strava API to retrieve activity details, transfers these activities to Garmin using Selenium, and updates a Google Sheets spreadsheet with the collected data.

Components

The project consists of three main components:

* Strava Client: A Python class that interacts with the Strava API to retrieve activity details.
* Garmin Client: A Python class that uses Selenium to interact with the Garmin website and transfer activities.
* Sheets Client: A Python class that interacts with the Google Sheets API to update a spreadsheet with the collected data.

Functionality

The script performs the following tasks:

Retrieves activity details from Strava
Transfers activities from Strava to Garmin using Selenium
Updates a Google Sheets spreadsheet with the collected data

Usage

To use this project, follow these steps:

1. Create a .env file with the necessary environment variables (e.g., Strava client ID and secret, Garmin email and password, Google Sheets document name and file path).
2. Install the required dependencies using pip install -r requirements.txt.
3. Run the script using python main.py.
   
Note

This project assumes that you have already set up the necessary APIs and have the required credentials. Additionally, the script is designed to run in a specific environment, so you may need to modify the code to fit your specific use case.

import os
import json
from datetime import datetime

# Import necessary libraries for OAuth2 and environment variables
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class StravaClient:
    def __init__(self):
        # Initialize Strava client with necessary variables
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_url = "https://localhost:8080"
        self.token_file = "strava_tokens.json"
        self.activities_url = "https://www.strava.com/api/v3/activities/"
        self.athlete_activities_url = "https://www.strava.com/api/v3/athlete/activities/"
        self.token_url = "https://www.strava.com/api/v3/oauth/token"
        self.auth_base_url = "https://www.strava.com/oauth/authorize"

    def load_tokens(self):
        # Load tokens from file if it exists, otherwise return empty dictionary
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                return json.load(f)
        else:
            return {}

    def save_tokens(self, tokens):
        # Save tokens to file
        with open(self.token_file, "w") as f:
            json.dump(tokens, f)

    def get_token(self):
        # Get access token from loaded tokens
        tokens = self.load_tokens()
        return tokens.get("access_token")

    def save_token(self, token):
        # Save new token to file
        tokens = self.load_tokens()
        tokens["access_token"] = token["access_token"]
        tokens["refresh_token"] = token["refresh_token"]
        self.save_tokens(tokens)

    def refresh_token(self):
        # Refresh access token using refresh token
        tokens = self.load_tokens()
        refresh_token = tokens["refresh_token"]
        session = OAuth2Session(client_id=self.client_id, redirect_uri=self.redirect_url)
        token = session.refresh_token(self.token_url, refresh_token=refresh_token, client_id=self.client_id,
                                      client_secret=self.client_secret)
        self.save_token(token)
        return token["access_token"]

    def authenticate(self):
        # Authenticate user and get access token
        session = OAuth2Session(client_id=self.client_id, redirect_uri=self.redirect_url)
        session.scope = ["activity:read_all"]
        auth_link = session.authorization_url(self.auth_base_url)
        print(f"Click here! {auth_link[0]}")
        redirect_response = input(f"Paste redirect url here: ")
        token = session.fetch_token(self.token_url, client_id=self.client_id, client_secret=self.client_secret,
                                    authorization_response=redirect_response, include_client_id=True)
        self.save_token(token)
        return token["access_token"]

    def get_strava_data_for_activity_with_specific_ID(self, activity_id, include_efforts):
        # Get Strava data for specific activity ID
        access_token = self.get_token()
        if access_token is None:
            access_token = self.authenticate()
        else:
            try:
                # Try to make a request with the current access token
                session = OAuth2Session(client_id=self.client_id, token={"access_token": access_token})
                response = session.get(f"{self.activities_url}{activity_id}?include_all_efforts={str(include_efforts).lower()}")
                response.raise_for_status()
            except Exception as e:
                # If the request fails, refresh the token and try again
                print(f"Request failed with error: {e}")
                access_token = self.refresh_token()
                session = OAuth2Session(client_id=self.client_id, token={"access_token": access_token})
                response = session.get(
                    f"{self.activities_url}{activity_id}?include_all_efforts={str(include_efforts).lower()}")
                response.raise_for_status()
            return response.json()

    def get_all_activities_in_timeframe(self, start_date, end_date):
        # Get all activities in a specific timeframe
        start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").timestamp())
        end_timestamp = int(datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").timestamp())
        access_token = self.get_token()
        if access_token is None:
            access_token = self.authenticate()
        else:
            try:
                # Try to make a request with the current access token
                session = OAuth2Session(client_id=self.client_id, token={"access_token": access_token})
                response = session.get(
                    f"{self.athlete_activities_url}?before={end_timestamp}&after={start_timestamp}&page=1&per_page=200")
                response.raise_for_status()
            except Exception as e:
                # If the request fails, refresh the token and try again
                print(f"Request failed with error: {e}")
                access_token = self.refresh_token()
                session = OAuth2Session(client_id=self.client_id, token={"access_token": access_token})
                response = session.get(
                    f"{self.athlete_activities_url}?before={end_timestamp}&after={start_timestamp}&page=1&per_page=200")
                response.raise_for_status()
        return response.json()
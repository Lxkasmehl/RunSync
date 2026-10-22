import os

import requests
from dotenv import load_dotenv

load_dotenv()


class GarminError(Exception):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type


class GarminClient:
    """Garmin Connect through a small Garmin service (python-garminconnect, no web scraping).

    The service holds the only Garmin login and protects the account from too many login attempts.
    On the server it runs at http://garmin:8000; set GARMIN_SERVICE_URL to use another address.
    """

    def __init__(self):
        self.base_url = os.getenv("GARMIN_SERVICE_URL", "http://garmin:8000")

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(method, f"{self.base_url}{path}", timeout=120, **kwargs)
        except requests.RequestException as e:
            raise GarminError("unreachable", f"Garmin service not reachable: {e}") from e
        try:
            body = response.json()
        except ValueError:
            raise GarminError("unexpected", f"HTTP {response.status_code}: {response.text[:200]}")
        if not body.get("ok"):
            raise GarminError(body.get("error_type", "unexpected"), body.get("message", str(body)))
        return body

    def get_activities(self, date, end=None):
        params = {"date": date} | ({"end": end} if end else {})
        return self.request("GET", "/activities", params=params)["activities"]

    def get_shoes(self):
        return self.request("GET", "/gear")["shoes"]

    def create_shoe(self, brand, model, name):
        return self.request("POST", "/gear", json={"brand": brand, "model": model, "name": name})

    def update_activity(self, start_local, name=None, description=None, gear_uuid=None):
        """Finds the activity by its start time (local time, same as on Strava) and sets the given fields."""
        body = {"start_local": start_local, "name": name, "description": description, "gear_uuid": gear_uuid}
        return self.request("POST", "/activity", json={k: v for k, v in body.items() if v is not None})

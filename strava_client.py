import json
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/api/v3/oauth/token"
SCOPES = "read,activity:read_all,activity:write,profile:read_all"

# RunSync aendert auf Strava nur, was niemand ausser Lukas sieht
WRITABLE_FIELDS = {"gear_id", "private_note"}


class StravaClient:
    def __init__(self):
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.token_file = os.getenv("STRAVA_TOKENS_FILE", "strava_tokens.json")

    def load_tokens(self):
        if os.path.exists(self.token_file):
            with open(self.token_file) as f:
                return json.load(f)
        raise RuntimeError(f"{self.token_file} fehlt. Einmal lokal 'python strava_client.py auth' ausfuehren.")

    def save_tokens(self, token):
        tokens = {k: token[k] for k in ("access_token", "refresh_token", "expires_at")}
        with open(self.token_file, "w") as f:
            json.dump(tokens, f)
        return tokens

    def refresh(self, tokens):
        response = requests.post(TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        }, timeout=30)
        response.raise_for_status()
        return self.save_tokens(response.json())

    def access_token(self, force_refresh=False):
        tokens = self.load_tokens()
        if force_refresh or tokens.get("expires_at", 0) < time.time() + 120:
            tokens = self.refresh(tokens)
        return tokens["access_token"]

    def request(self, method, path, **kwargs):
        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self.access_token(force_refresh=attempt > 0)}"}
            response = requests.request(method, f"{API}{path}", headers=headers, timeout=30, **kwargs)
            if response.status_code != 401:
                break
        response.raise_for_status()
        return response.json()

    def get_activity(self, activity_id):
        return self.request("GET", f"/activities/{activity_id}")

    # Alter Name, wird noch von main_app benutzt
    def get_strava_data_for_activity_with_specific_ID(self, activity_id, include_efforts=False):
        return self.request("GET", f"/activities/{activity_id}", params={"include_all_efforts": str(include_efforts).lower()})

    def get_all_activities_in_timeframe(self, start_date, end_date):
        """Alle Aktivitaeten zwischen zwei Zeitpunkten ("YYYY-MM-DD HH:MM:SS"), neueste zuerst."""
        after = int(datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").timestamp())
        before = int(datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").timestamp())
        activities, page = [], 1
        while True:
            batch = self.request("GET", "/athlete/activities", params={"before": before, "after": after, "page": page, "per_page": 200})
            activities.extend(batch)
            if len(batch) < 200:
                break
            page += 1
        return sorted(activities, key=lambda a: a["start_date"], reverse=True)

    def update_activity(self, activity_id, **fields):
        """Setzt nur Schuhe (gear_id) und private Notiz (private_note), nie oeffentlich sichtbare Felder."""
        forbidden = set(fields) - WRITABLE_FIELDS
        if forbidden:
            raise ValueError(f"RunSync darf auf Strava nur {sorted(WRITABLE_FIELDS)} aendern, nicht {sorted(forbidden)}")
        updated = self.request("PUT", f"/activities/{activity_id}", json=fields)
        for key, value in fields.items():
            if (updated.get(key) or "") != (value or ""):
                raise RuntimeError(f"Strava hat {key} nicht uebernommen (ist {updated.get(key)!r})")
        return updated

    def get_shoes(self):
        return [{"id": s["id"], "name": s["name"], "retired": s.get("retired")} for s in self.request("GET", "/athlete").get("shoes", [])]

    def authenticate(self):
        """Einmalige Freigabe im Browser. Strava leitet auf localhost weiter, die Adresse dann hier einfuegen."""
        print("Im Browser oeffnen und autorisieren:")
        print(f"https://www.strava.com/oauth/authorize?client_id={self.client_id}&response_type=code"
              f"&redirect_uri=http://localhost&approval_prompt=force&scope={SCOPES}")
        redirect = input("Adresse nach der Weiterleitung (http://localhost/?...code=...): ")
        code = redirect.split("code=")[1].split("&")[0]
        response = requests.post(TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }, timeout=30)
        response.raise_for_status()
        self.save_tokens(response.json())
        print(f"Gespeichert in {self.token_file}")


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["auth"]:
        StravaClient().authenticate()
    else:
        print("Aufruf: python strava_client.py auth")

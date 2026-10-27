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

# RunSync changes shoes and the private note, and the description only where it is empty or written by RunSync
# (checked in main_app.set_strava_description). Never the title.
WRITABLE_FIELDS = {"gear_id", "private_note", "description"}


class StravaClient:
    def __init__(self):
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.token_file = os.getenv("STRAVA_TOKENS_FILE", "strava_tokens.json")

    def load_tokens(self):
        if os.path.exists(self.token_file):
            with open(self.token_file) as f:
                return json.load(f)
        raise RuntimeError(f"{self.token_file} is missing. Run 'python strava_client.py auth' once locally.")

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

    def get_all_activities_in_timeframe(self, start_date, end_date):
        """All activities between two points in time ("YYYY-MM-DD HH:MM:SS"), newest first."""
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
        """Only sets shoes (gear_id), the private note (private_note) and the description, never the title."""
        forbidden = set(fields) - WRITABLE_FIELDS
        if forbidden:
            raise ValueError(f"RunSync may only change {sorted(WRITABLE_FIELDS)} on Strava, not {sorted(forbidden)}")
        updated = self.request("PUT", f"/activities/{activity_id}", json=fields)
        same = lambda a, b: " ".join(str(a or "").split()) == " ".join(str(b or "").split())
        for key, value in fields.items():
            if not same(updated.get(key), value):
                raise RuntimeError(f"Strava did not accept {key} (it is {updated.get(key)!r})")
        return updated

    def get_shoes(self):
        return [{"id": s["id"], "name": s["name"], "retired": s.get("retired")} for s in self.request("GET", "/athlete").get("shoes", [])]

    def authenticate(self):
        """One-off authorization in the browser. Strava redirects to localhost; paste that address here."""
        print("Open in the browser and authorize:")
        print(f"https://www.strava.com/oauth/authorize?client_id={self.client_id}&response_type=code"
              f"&redirect_uri=http://localhost&approval_prompt=force&scope={SCOPES}")
        redirect = input("Address after the redirect (http://localhost/?...code=...): ")
        code = redirect.split("code=")[1].split("&")[0]
        response = requests.post(TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }, timeout=30)
        response.raise_for_status()
        self.save_tokens(response.json())
        print(f"Saved to {self.token_file}")

    # Webhook: Strava reports new activities to a callback URL (one subscription per Strava app)
    def subscriptions(self):
        response = requests.get(f"{API}/push_subscriptions", params={"client_id": self.client_id, "client_secret": self.client_secret}, timeout=30)
        response.raise_for_status()
        return response.json()

    def subscribe(self, callback_url, verify_token):
        response = requests.post(f"{API}/push_subscriptions", data={
            "client_id": self.client_id, "client_secret": self.client_secret,
            "callback_url": callback_url, "verify_token": verify_token,
        }, timeout=30)
        response.raise_for_status()
        return response.json()

    def unsubscribe(self, subscription_id):
        response = requests.delete(f"{API}/push_subscriptions/{subscription_id}",
                                   params={"client_id": self.client_id, "client_secret": self.client_secret}, timeout=30)
        response.raise_for_status()


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    client = StravaClient()
    if args == ["auth"]:
        client.authenticate()
    elif args == ["subscriptions"]:
        print(client.subscriptions())
    elif len(args) == 3 and args[0] == "subscribe":
        print(client.subscribe(args[1], args[2]))
    elif len(args) == 2 and args[0] == "unsubscribe":
        client.unsubscribe(args[1])
    else:
        print("Usage: python strava_client.py auth | subscriptions | subscribe <callback_url> <verify_token> | unsubscribe <id>")

import os
import json
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
redirect_url = "https://localhost:8080"
token_file = "strava_tokens.json"

def load_tokens():
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_tokens(tokens):
    with open(token_file, "w") as f:
        json.dump(tokens, f)

def get_token():
    tokens = load_tokens()
    return tokens.get("access_token")

def save_token(token):
    tokens = load_tokens()
    tokens["access_token"] = token["access_token"]
    tokens["refresh_token"] = token["refresh_token"]
    save_tokens(tokens)

def refresh_token():
    tokens = load_tokens()
    refresh_token = tokens["refresh_token"]
    token_url = "https://www.strava.com/api/v3/oauth/token"
    session = OAuth2Session(client_id=client_id, redirect_uri=redirect_url)
    token = session.refresh_token(token_url, refresh_token=refresh_token, client_id=client_id, client_secret=client_secret)
    save_token(token)
    return token["access_token"]

def authenticate():
    session = OAuth2Session(client_id=client_id, redirect_uri=redirect_url)
    auth_base_url = "https://www.strava.com/oauth/authorize"
    session.scope = ["activity:read_all"]
    auth_link = session.authorization_url(auth_base_url)
    print(f"CLick here! {auth_link[0]}")
    redirect_response = input(f"Paste redirect url here: ")
    token_url = "https://www.strava.com/api/v3/oauth/token"
    token = session.fetch_token(token_url, client_id=client_id, client_secret=client_secret, authorization_response=redirect_response, include_client_id=True)
    save_token(token)
    return token["access_token"]

def get_strava_data():
    access_token = get_token()
    if access_token is None:
        access_token = authenticate()
    session = OAuth2Session(client_id=client_id, token={"access_token": access_token})
    response = session.get("https://www.strava.com/api/v3/activities/12283718987?include_all_efforts=false")
    response_text = response.text
    data = json.loads(response_text)
    return data

data = get_strava_data()
print(f"Private Notes: {data["private_note"]}")
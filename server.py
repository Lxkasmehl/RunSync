"""RunSync als Dienst fuer n8n (nur im Docker-Netz erreichbar: http://runsync:8001).

GET  /ping                      lebt der Dienst
GET  /shoes                     Schuhliste (shoes.json)
POST /activity/new  {"id": 123} neue Strava-Aktivitaet: Zahl ins Sheet, Infos zurueck (is_run, start_local, distance_km)
POST /run/log       {"date": "2026-10-20", "daytime": "morning", "strava_ids": [...], "what": ..., "shoe": ..., "thoughts": ...}
POST /runs/undocumented {"days": 14}   Laeufe, bei denen im Sheet Hauptzelle oder Notiz fehlt
POST /classic/sheets            Strava -> Sheet ab dem ersten leeren Tag
POST /classic/garmin {"days": 14, "stop_at_transferred": true}   Strava -> Garmin
POST /classic/p4p7              Yoga/Workout-Anzahl der abgeschlossenen Wochen

Fehler: {"ok": false, "error_type": ..., "message": ..., ...}
  ambiguous_shoe (options), run_not_found / ambiguous_run (runs_that_day), bad_request, strava_error, unexpected
"""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

import main_app
import shoes
from garmin_client import GarminClient, GarminError
from main_app import RunSyncError
from sheets_client import SheetsClient
from strava_client import StravaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("runsync")

# Ein Auftrag nach dem anderen: Sheet-Zellen werden gelesen und dann geschrieben
lock = threading.Lock()
strava = StravaClient()
garmin = GarminClient()
_sheets = None


def sheets():
    global _sheets
    if _sheets is None:
        _sheets = SheetsClient()
    return _sheets


def run_log(body):
    return main_app.log_run(sheets(), strava, garmin, date=body.get("date") or None, daytime=body.get("daytime") or None,
                            strava_ids=body.get("strava_ids") or None, what=body.get("what"), shoe=body.get("shoe"),
                            thoughts=body.get("thoughts"))


ROUTES = {
    ("GET", "/ping"): lambda body: {},
    ("GET", "/shoes"): lambda body: {"shoes": [s["name"] for s in shoes.load_shoes()]},
    ("POST", "/activity/new"): lambda body: main_app.new_activity(sheets(), strava, body["id"]),
    ("POST", "/run/log"): run_log,
    ("POST", "/runs/undocumented"): lambda body: main_app.undocumented_runs(sheets(), strava, days=int(body.get("days") or 14)),
    ("POST", "/classic/sheets"): lambda body: main_app.update_sheets_data(sheets(), strava),
    ("POST", "/classic/garmin"): lambda body: main_app.transfer_to_garmin(
        strava, garmin, days=int(body.get("days") or 14), stop_at_transferred=body.get("stop_at_transferred", True)),
    ("POST", "/classic/p4p7"): lambda body: main_app.update_p4_p7(sheets(), strava),
}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_route(self, method):
        route = ROUTES.get((method, self.path))
        if route is None:
            return self.send(404, {"ok": False, "error_type": "bad_request", "message": "unbekannter Pfad"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or "{}")
        except ValueError:
            return self.send(400, {"ok": False, "error_type": "bad_request", "message": "kein gueltiges JSON"})
        global _sheets
        try:
            with lock:
                result = route(body)
            self.send(200, {"ok": True, **result} if "ok" not in result else result)
        except RunSyncError as e:
            self.send(400, {"ok": False, "error_type": e.error_type, "message": str(e), **e.details})
        except GarminError as e:
            self.send(502, {"ok": False, "error_type": f"garmin_{e.error_type}", "message": str(e)[:300]})
        except requests.HTTPError as e:
            self.send(502, {"ok": False, "error_type": "strava_error", "message": f"{e} {e.response.text[:200]}"})
        except Exception as e:
            log.exception("Unerwarteter Fehler")
            _sheets = None  # z.B. abgelaufene Google-Verbindung: beim naechsten Mal neu oeffnen
            self.send(502, {"ok": False, "error_type": "unexpected", "message": f"{type(e).__name__}: {e}"[:300]})

    def do_GET(self):
        self.handle_route("GET")

    def do_POST(self):
        self.handle_route("POST")

    def log_message(self, fmt, *args):
        if self.path != "/ping":
            log.info("%s %s", self.command, self.path)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()

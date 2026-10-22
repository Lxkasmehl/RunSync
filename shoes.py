"""Schuhe: Zuordnung Garmin <-> Strava (shoes.json) und Suche nach freier Beschreibung ("der blaue Invincible 3")."""
import json
import os
import re

SHOES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shoes.json")

# Deutsche Farben (auch gebeugt: "blauen", "weisse") auf die englischen Namen abbilden
COLORS = {"blau": "blue", "weiss": "white", "weiß": "white", "rot": "red", "grau": "grey", "gray": "grey",
          "grün": "green", "gruen": "green", "schwarz": "black", "silber": "silver", "hellgrün": "light green"}
FILLER = {"der", "die", "das", "den", "dem", "in", "im", "mit", "meinen", "meine", "meinem", "mein", "the", "my",
          "schuh", "schuhe", "schuhen", "paar", "neuen", "alten", "gelaufen", "and", "und"}


def load_shoes():
    with open(SHOES_FILE, encoding="utf-8") as f:
        return json.load(f)


def words(text):
    result = []
    for word in re.sub(r"[()/%,.\-]", " ", text.lower()).split():
        for german, english in COLORS.items():
            if word.startswith(german):
                word = english
                break
        if word in FILLER:
            continue
        # Mehrzahl ignorieren: "structures" findet "structure"
        result.extend(part[:-1] if len(part) > 4 and part.endswith("s") else part for part in word.split())
    return result


def tokens(text):
    found = words(text)
    # Getrennt gesprochene Namen zusammensetzen: "Cloud Surfer" findet "Cloudsurfer"
    joined = {a + b for a, b in zip(found, found[1:])}
    return set(found) | joined


def resolve(text):
    """Gibt (schuh, None) zurueck, oder (None, [Kandidaten]) wenn unklar oder nichts passt."""
    shoes = load_shoes()
    exact = [s for s in shoes if s["name"].lower() == text.strip().lower()]
    if exact:
        return exact[0], None
    wanted = tokens(text)
    if not wanted:
        return None, [s["name"] for s in shoes]
    scored = [(len(wanted & tokens(s["name"])), s) for s in shoes]
    best = max(score for score, _ in scored)
    if best == 0:
        return None, [s["name"] for s in shoes]
    candidates = [s for score, s in scored if score == best]
    if len(candidates) == 1:
        return candidates[0], None
    return None, [s["name"] for s in candidates]


def by_strava_id(gear_id):
    return next((s for s in load_shoes() if gear_id and s["strava"] == gear_id), None)

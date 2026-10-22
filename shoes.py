"""Schuhe: Zuordnung Garmin <-> Strava und Suche nach freier Beschreibung ("der blaue Invincible 3").

Die Liste liegt auf dem Server in DATA_DIR/shoes.json, damit neu angelegte Schuhe erhalten bleiben. Beim ersten Start
wird sie aus der shoes.json im Repo uebernommen (die Repo-Datei ist nur der Startstand).
"""
import json
import os
import re
import shutil

REPO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shoes.json")
DATA_FILE = os.path.join(os.environ["DATA_DIR"], "shoes.json") if os.getenv("DATA_DIR") else REPO_FILE

# Deutsche Farben (auch gebeugt: "blauen", "weisse") auf die englischen Namen abbilden
COLORS = {"blau": "blue", "weiss": "white", "weiß": "white", "rot": "red", "grau": "grey", "gray": "grey",
          "grün": "green", "gruen": "green", "schwarz": "black", "silber": "silver", "hellgrün": "light green"}
FILLER = {"der", "die", "das", "den", "dem", "in", "im", "mit", "meinen", "meine", "meinem", "mein", "the", "my",
          "schuh", "schuhe", "schuhen", "paar", "neuen", "alten", "gelaufen", "and", "und"}


def load_shoes():
    if not os.path.exists(DATA_FILE):
        shutil.copy(REPO_FILE, DATA_FILE)
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_shoes(shoes):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join("  " + json.dumps(s, ensure_ascii=False) for s in sorted(shoes, key=lambda s: s["name"])) + "\n]\n")
    os.replace(tmp, DATA_FILE)


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


def score(query, name):
    """Gemeinsame Woerter. Modellnummern muessen passen: "Pegasus 41" ist nicht der Pegasus 40."""
    wanted, have = tokens(query), tokens(name)
    numbers = {w for w in words(query) if any(ch.isdigit() for ch in w)}
    if not numbers <= have:
        return 0
    return len(wanted & have)


def best(query, names, minimum=1):
    """Eindeutig bester Name (oder None) und alle gleich guten Kandidaten."""
    scored = [(score(query, n), n) for n in names]
    top = max((s for s, _ in scored), default=0)
    if top < minimum:
        return None, []
    candidates = [n for s, n in scored if s == top]
    return (candidates[0] if len(candidates) == 1 else None), candidates


def resolve(text):
    """(schuh, None) wenn eindeutig, (None, [Kandidaten]) wenn mehrdeutig, (None, []) wenn unbekannt."""
    shoes = load_shoes()
    exact = [s for s in shoes if s["name"].lower() == text.strip().lower()]
    if exact:
        return exact[0], None
    name, candidates = best(text, [s["name"] for s in shoes])
    if name:
        return next(s for s in shoes if s["name"] == name), None
    return None, candidates


def by_strava_id(gear_id):
    return next((s for s in load_shoes() if gear_id and s["strava"] == gear_id), None)

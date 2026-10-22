"""Shoes: mapping Garmin <-> Strava and lookup by a free description ("der blaue Invincible 3").

On the server the list lives in DATA_DIR/shoes.json so newly added shoes survive deployments. On first start it is
copied from shoes.json in the repo (the repo file is only the initial state).
Descriptions are usually German (spoken to a Telegram bot), hence the German color and filler words below.
"""
import json
import os
import re
import shutil

REPO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shoes.json")
DATA_FILE = os.path.join(os.environ["DATA_DIR"], "shoes.json") if os.getenv("DATA_DIR") else REPO_FILE

# Map German colors (also inflected: "blauen", "weisse") to the English names used in the shoe list
COLORS = {"blau": "blue", "weiss": "white", "weiß": "white", "rot": "red", "grau": "grey", "gray": "grey",
          "grün": "green", "gruen": "green", "schwarz": "black", "silber": "silver", "hellgrün": "light green"}
# Where a pair was bought ("die ich in den USA habe", "die deutschen") maps to the (US)/(DE) suffix
ORIGINS = {"usa": "us", "amerika": "us", "deutsch": "de"}
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
        for german, english in (COLORS | ORIGINS).items():
            if word.startswith(german):
                word = english
                break
        if word in FILLER:
            continue
        # Ignore plurals: "structures" finds "structure"
        result.extend(part[:-1] if len(part) > 4 and part.endswith("s") else part for part in word.split())
    return result


def tokens(text):
    found = words(text)
    # Join names spoken as separate words: "Cloud Surfer" finds "Cloudsurfer"
    joined = {a + b for a, b in zip(found, found[1:])}
    return set(found) | joined


def score(query, name):
    """Number of shared words. Model numbers must match: "Pegasus 41" is not the Pegasus 40."""
    wanted, have = tokens(query), tokens(name)
    numbers = {w for w in words(query) if any(ch.isdigit() for ch in w)}
    if not numbers <= have:
        return 0
    return len(wanted & have)


def best(query, names, minimum=1):
    """The unique best name (or None) and all equally good candidates."""
    scored = [(score(query, n), n) for n in names]
    top = max((s for s, _ in scored), default=0)
    if top < minimum:
        return None, []
    candidates = [n for s, n in scored if s == top]
    return (candidates[0] if len(candidates) == 1 else None), candidates


def resolve(text):
    """(shoe, None) if unique, (None, [candidates]) if ambiguous, (None, []) if unknown."""
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

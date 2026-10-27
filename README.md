# RunSync

Keeps my training diary (a Google Sheet), Garmin Connect and Strava in sync. Runs as a small Docker service next to
my self-hosted n8n and is driven by n8n workflows and a Telegram bot.

## Two workflows

**1. Telegram (current):** training is documented in the sheet and on Garmin.
- New activity on Strava → Strava webhook → kilometers (or minutes for other sports) go into the sheet right away.
- For runs the bot asks: what did you do, which shoes, how did it go?
- The answer (text or voice message) is written to:
  - **Sheet:** main cell ("70min easy") and notes (thoughts, word for word)
  - **Garmin:** description and shoes
  - **Strava:** shoes, private note and the description in language-neutral words ("70 min easy",
    "20×400 /30s"), but only if the description is empty or was written by RunSync. The title is never changed.
- Works for older runs too: "Monday morning: 70 min easy in the Structures, ..."
- Replying to the bot's question (Telegram quote) ties the answer to exactly that run. Without a quote the bot asks
  when several runs are waiting.
- "Which runs are still missing?" lists the half days of the last 14 days whose description or thoughts are empty
  in the sheet.

**Workouts** (intervals, lactate): the bot also extracts the structure ("20×400 /30s", lactate 3.1 after rep 7).
RunSync finds the reps in the Garmin laps (lap button: one lap per rep and per rest; warm-up, strides and cool-down
are skipped), and the bot sends a preview. The athlete's distances win (indoors the watch may measure 330 m for a
400), only times come from the watch. After "passt":
- **Strava description:** title plus splits. Up to 15 reps every time, above that the average per block between
  lactate tests (`1-7: Ø 68.4 → 3.1 mmol`). Times under 1:30 as seconds, single reps of a ladder on one line.
- **Lactate sheet** (worksheet `RawData`, one row per test): date, session, rep distance and time, surface, rest,
  heart rate, weather (outdoors), shoe, and the pace of all reps before the test (`Prev Avg/Fastest/Slowest Pace`).
  Rows carry the `Strava ID`, so a correction replaces them.

**2. Classic:** everything is maintained on Strava (title, description, private note, shoes), then "Sync Strava" to
the bot. Strava → sheet from the first empty day, Strava → Garmin (title, description, shoes).
To switch, set `RUN_MODE` to `'strava'` in the n8n workflow code; otherwise the webhook writes new activities into the
sheet without texts. Don't use the classic Garmin sync in Telegram mode, it would overwrite the Garmin description
with the one from Strava.

Every Sunday n8n fills in the number of yoga sessions (P7) and workouts (P4) of finished weeks.

## Sheet

Week worksheets `KW{week}{year}` (Sunday to Saturday); new weeks are created from the `leer` template.
Two columns per day (text, number), Sunday = B/C. Morning (start before 1 pm) rows 3-5, afternoon rows 6-8:
1st row other activities (name, minutes), 2nd row runs (main cell, km with 2 decimals), 3rd row notes.
Several runs in the same block (warm-up, race, cool-down) are added up and share main cell and notes.

`ledger.json` records which activities are already in the sheet and which texts RunSync wrote. Nothing is counted
twice. Texts are recorded per run: a correction for the same run replaces its old text, while texts for another
run in the same block (documented separately) are added below.

Runs with breaks of at most 20 minutes in the same half day count as one training (e.g. warm-up on the treadmill,
then outside). `/activity/new` returns `same_training` (the other runs) and `first_of_training`, so a bot can ask
only once per training.

## Files

| File | Purpose |
|---|---|
| `main_app.py` | Both workflows, also usable from the command line |
| `server.py` | HTTP service for n8n (`http://runsync:8001`, Docker network only) |
| `strava_client.py` | Strava API; only writes `gear_id`, `private_note` and `description` (never the title) |
| `workout.py` | Workouts: reps ↔ laps, Strava description, lactate rows, preview text |
| `lactate_client.py` | Lactate sheet (`LACTATE_SHEET_ID`), finds columns by header |
| `garmin_client.py` | Garmin via a small Garmin service ([python-garminconnect](https://github.com/cyberjunky/python-garminconnect), no web scraping) |
| `sheets_client.py` | Google Sheet (gspread, service account) |
| `shoes.json`, `shoes.py` | Shoe mapping Garmin ↔ Strava and lookup by description ("Invincible 3 blau") |
| `tests/` | Offline tests |

## Shoes

The shoe list maps every shoe to its Garmin uuid and Strava gear id (`null` if it doesn't exist there).
On the server it lives in `/data/shoes.json`; `shoes.json` in the repo is only the initial state.

- If a description is ambiguous (e.g. two blue Invincible), the bot asks which one.
- Model numbers must match: "Pegasus 41" never ends up as the Pegasus 40.
- Unknown shoe: the bot asks for its name ("Nike Pegasus 41 Black") and calls `add_shoe`. On Garmin it links a
  matching shoe that isn't mapped yet or creates a new one. Strava doesn't let apps create gear: add the shoe in the
  Strava app, tell the bot, and it links it.
- Same for shoes that exist on only one side.

## Operations

- Deploy: commit, then `sh deploy.sh` (copies HEAD to the server and rebuilds the container; the host is
  `DEPLOY_HOST` in `.env`)
- Data in the `runsync_data` volume (`/data`): `strava_tokens.json`, `service-account.json`, `ledger.json`, `shoes.json`
- Credentials in the server's compose `.env`: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `SHEET_DOCUMENT_NAME`
- Re-authorize Strava (e.g. after a revoked token): run `python strava_client.py auth` locally, then copy the new
  `strava_tokens.json` into the container:
  `cat strava_tokens.json | ssh $DEPLOY_HOST 'cd /opt/n8n && docker compose exec -T runsync sh -c "cat > /data/strava_tokens.json"'`
- Strava webhook: `python strava_client.py subscriptions | subscribe <url> <verify_token> | unsubscribe <id>`
  (one subscription per Strava app)
- Logs: `docker compose logs runsync`

## Local

`.env` with `FILE_PATH` (service account JSON), `DOCUMENT_NAME`, `CLIENT_ID`, `CLIENT_SECRET`, `DEPLOY_HOST`, plus
`strava_tokens.json`. The Garmin service is only reachable inside the Docker network, so run Garmin tasks on the
server: `docker compose exec runsync python main_app.py transfer_to_garmin 14`.
Note: a local `ledger.json` is not the server's one, so run sheet tasks on the server as well.

```
pip install -r requirements.txt
python main_app.py update_sheets_data | update_p4_p7 | transfer_to_garmin [days] | seed_ledger
python -m unittest discover tests     # offline tests (week sheet, cells, shoe lookup, text replacement)
```

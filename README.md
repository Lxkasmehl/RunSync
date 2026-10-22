# RunSync

Hält mein Trainingstagebuch (Google Sheet), Garmin Connect und Strava in Sync. Läuft als Docker-Dienst auf meinem
n8n-Server (Repo `Lxkasmehl/n8n-server`) und wird über n8n und meinen Telegram-Bot gesteuert.

## Zwei Wege

**1. Telegram (aktuell):** Das Training wird im Sheet und auf Garmin dokumentiert.
- Neue Aktivität auf Strava → Strava-Webhook → Kilometer (bzw. Minuten bei anderen Sportarten) sofort ins Sheet.
- Bei Läufen fragt der Bot: Was hast du gemacht, welche Schuhe, wie war es?
- Die Antwort (Text oder Sprachnachricht) landet hier:
  - **Sheet:** Hauptzelle ("70 Minuten Dauerlauf") und Notiz (Gedanken, wörtlich)
  - **Garmin:** Beschreibung und Schuhe
  - **Strava:** Schuhe und private Notiz. Nichts öffentlich Sichtbares (Titel, Beschreibung) wird geändert.
- Nachträglich geht auch: "Montagmorgen: 70 min locker in den Structures, ..."
- Antwortest du per Zitat auf die Frage, gehört die Antwort genau zu diesem Lauf. Ohne Zitat fragt der Bot nach,
  wenn mehrere Läufe offen sind.
- "Welche Läufe fehlen noch?" listet die Halbtage der letzten 14 Tage, bei denen im Sheet Training oder Gedanken fehlen.

**2. Klassisch:** Alles wird auf Strava gepflegt (Titel, Beschreibung, private Notiz, Schuhe), dann "Sync Strava" an
den Bot schicken. Strava → Sheet ab dem ersten leeren Tag, Strava → Garmin (Titel, Beschreibung, Schuhe).
Umschalten: `RUN_MODE` in `build/runs.mjs` im n8n-Server-Repo auf `'strava'` setzen und ausrollen, sonst trägt der
Webhook neue Aktivitäten ohne Texte ins Sheet ein. Den klassischen Garmin-Sync nicht im Telegram-Modus nutzen, er
überschreibt die Garmin-Beschreibung mit der von Strava.

Wöchentlich (sonntags) trägt n8n die Anzahl Yoga (P7) und Workouts (P4) der abgeschlossenen Wochen ein.

## Sheet

Wochenblätter `KW{woche}{jahr}` (Sonntag bis Samstag), neue Wochen werden aus der Vorlage `leer` angelegt.
Je Tag zwei Spalten (Text, Zahl), Sonntag = B/C. Vormittag (Start vor 13 Uhr) Zeilen 3-5, Nachmittag 6-8:
1. Zeile andere Aktivitäten (Name, Minuten), 2. Zeile Läufe (Hauptzelle, km mit 2 Nachkommastellen), 3. Zeile Notizen.
Mehrere Läufe im selben Block (Einlaufen, Rennen, Auslaufen) werden addiert und teilen sich Hauptzelle und Notiz.

`ledger.json` merkt sich, welche Aktivitäten schon im Sheet stehen und welche Texte RunSync geschrieben hat. So zählt
nichts doppelt, und eine Korrektur ersetzt den alten Text statt ihn anzuhängen.

## Dateien

| Datei | Inhalt |
|---|---|
| `main_app.py` | Ablauf beider Wege, auch lokal per Kommandozeile |
| `server.py` | HTTP-Dienst für n8n (`http://runsync:8001`, nur im Docker-Netz) |
| `strava_client.py` | Strava-API, schreibt nur `gear_id` und `private_note` |
| `garmin_client.py` | Garmin über den Garmin-Dienst des n8n-Servers (`garminconnect`, kein Web-Scraping) |
| `sheets_client.py` | Google Sheet (gspread, Service-Account) |
| `shoes.json`, `shoes.py` | Schuh-Zuordnung Garmin ↔ Strava und Suche nach Beschreibung ("Invincible 3 blau") |

## Schuhe

Die Schuhliste ordnet jedem Schuh die Garmin-uuid und die Strava-gear-id zu (`null`, wenn es ihn dort nicht gibt).
Sie liegt auf dem Server in `/data/shoes.json`; `shoes.json` im Repo ist nur der Startstand.

- Ist eine Beschreibung nicht eindeutig (z.B. zwei blaue Invincible), fragt der Bot nach.
- Modellnummern müssen passen: "Pegasus 41" landet nie beim Pegasus 40.
- Unbekannter Schuh: Der Bot fragt nach dem Namen ("Nike Pegasus 41 Black") und ruft `add_shoe` auf. Auf Garmin
  wird ein passender, noch nicht zugeordneter Schuh verknüpft oder ein neuer angelegt. Auf Strava kann eine App keine
  Schuhe anlegen: Den Schuh in der Strava-App anlegen, dem Bot Bescheid sagen, dann verknüpft er ihn.
- Genauso für Schuhe, die es nur auf einer Seite gibt.

## Betrieb

- Ausrollen: committen, dann `sh deploy.sh` (kopiert HEAD nach `/opt/n8n/runsync` und baut den Container neu)
- Daten im Volume `runsync_data` (`/data`): `strava_tokens.json`, `service-account.json`, `ledger.json`, `shoes.json`
- Zugangsdaten in `/opt/n8n/.env`: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `SHEET_DOCUMENT_NAME`
- Strava neu freigeben (z.B. bei abgelaufenem Token): lokal `python strava_client.py auth`, dann die neue
  `strava_tokens.json` in den Container kopieren:
  `cat strava_tokens.json | ssh root@2.31.61.2 'cd /opt/n8n && docker compose exec -T runsync sh -c "cat > /data/strava_tokens.json"'`
- Strava-Webhook: `python strava_client.py subscriptions | subscribe <url> <verify_token> | unsubscribe <id>`
  (pro Strava-App nur einer; Adresse und Prüfwert stehen in `build/lib.mjs` des n8n-Server-Repos)
- Logs: `docker compose logs runsync`

## Lokal

`.env` mit `FILE_PATH` (Service-Account-JSON), `DOCUMENT_NAME`, `CLIENT_ID`, `CLIENT_SECRET`, dazu
`strava_tokens.json`. Der Garmin-Dienst ist nur im Docker-Netz erreichbar, Garmin-Aufgaben deshalb auf dem Server:
`docker compose exec runsync python main_app.py transfer_to_garmin 14`.
Achtung: Lokal ein anderes `ledger.json` als auf dem Server, also Sheet-Aufgaben besser auch dort ausführen.

```
pip install -r requirements.txt
python main_app.py update_sheets_data | update_p4_p7 | transfer_to_garmin [tage] | seed_ledger
python -m unittest discover tests     # Tests ohne Netz (Wochenblatt, Zellen, Schuhsuche, Texte ersetzen)
```

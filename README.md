# 🏃‍♂️ RunSync - GitHub Actions

Eine automatisierte Lösung für deine RunSync Python-Funktionen, die über GitHub Actions ausgeführt werden.

## 🎯 **Was ist das?**

RunSync ist ein Tool, das deine Aktivitäten zwischen verschiedenen Plattformen synchronisiert:

- **Strava** → **Google Sheets** (Aktivitäten aktualisieren)
- **Google Sheets** → **P4/P7 Worksheets** (Daten verarbeiten)
- **Strava** → **Garmin** (Aktivitäten übertragen)

## 🚀 **GitHub Actions**

Deine RunSync-Funktionen werden über GitHub Actions ausgeführt:

```
https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions
```

## 🚀 **Schnellstart**

### **1. Repository auf GitHub erstellen**

```bash
# Lokales Repository initialisieren
git init
git add .
git commit -m "Initial commit"

# GitHub Repository erstellen und verbinden
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### **2. Repository Secrets konfigurieren**

Gehe zu **Settings** → **Secrets and variables** → **Actions** und füge hinzu:

- `ADMIN_PASSWORD`: Dein sicheres Passwort für die Authentifizierung

### **3. GitHub Actions testen**

1. Gehe zu **Actions** in deinem Repository
2. Wähle **RunSync Tasks**
3. Klicke **Run workflow**
4. Wähle Task-Typ und gib Passwort ein
5. Klicke **Run workflow**

## 📁 **Projektstruktur**

```
RunSync/
├── .github/
│   └── workflows/
│       └── runsync.yml          # GitHub Actions Workflow
├── main_app.py                 # Deine Python-Funktionen
├── strava_client.py
├── garmin_client.py
├── sheets_client.py
├── requirements.txt            # Python Dependencies
└── README.md                   # Diese Datei
```

## 🔧 **Wie es funktioniert**

### **GitHub Actions Workflow**

- **Workflow-Dispatch** triggert Python-Skripte
- **Ubuntu-Runner** mit Python 3.11
- **Chrome + Selenium** für Garmin-Integration
- **Alle Dependencies** automatisch installiert
- **Passwort-Verifikation** über Repository Secrets

## 🎮 **Verwendung**

### **Manuell über GitHub Actions**

1. Gehe zu **Actions** in deinem Repository
2. Wähle **RunSync Tasks**
3. Klicke **Run workflow**
4. Wähle Task-Typ und gib Passwort ein
5. Klicke **Run workflow**

### **Verfügbare Tasks:**

- **update_activities**: Aktualisiert alle Aktivitäten seit dem ersten nicht abgeschlossenen Tag
- **update_p4_p7**: Aktualisiert die P4 und P7 Worksheets mit den neuesten Daten
- **transfer_garmin_stop**: Überträgt Aktivitäten von Strava zu Garmin und stoppt bei bereits übertragenen
- **transfer_garmin_no_stop**: Überträgt alle Aktivitäten von Strava zu Garmin ohne automatischen Stop

## 🔒 **Sicherheit**

### **Passwort-Schutz**

- **Repository Secret** `ADMIN_PASSWORD` für Authentifizierung
- **Workflow-Verifikation** vor jeder Ausführung

### **Repository Secrets**

```bash
# Sichere Passwörter generieren
ADMIN_PASSWORD=$(openssl rand -base64 32)
echo "ADMIN_PASSWORD=$ADMIN_PASSWORD"
```

## 🛠️ **Anpassungen**

### **Passwort ändern**

1. **GitHub Repository** → **Settings** → **Secrets and variables** → **Actions**
2. **ADMIN_PASSWORD** bearbeiten oder neu erstellen

### **Neue Funktionen hinzufügen**

1. **Python-Funktion** in `main_app.py` erstellen
2. **Workflow-Step** in `.github/workflows/runsync.yml` hinzufügen
3. **Task-Option** in `workflow_dispatch` inputs hinzufügen

## 📊 **Monitoring**

### **GitHub Actions Logs**

- **Real-time Logs**: In GitHub Actions Tab
- **Fehler-Debugging**: Detaillierte Python-Stack-Traces
- **Performance**: Laufzeit-Statistiken

## 🔄 **Updates**

### **Code aktualisieren**

```bash
# Änderungen committen
git add .
git commit -m "Update description"
git push origin main

# GitHub Actions Workflows werden automatisch aktualisiert
```

### **Dependencies aktualisieren**

```bash
# requirements.txt bearbeiten
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
git push origin main
```

## 🚨 **Troubleshooting**

### **Häufige Probleme**

1. **Workflow schlägt fehl**

   - Überprüfe Repository Secrets
   - Schaue in GitHub Actions Logs
   - Teste Python-Code lokal

2. **Chrome/Selenium Fehler**

   - Workflow installiert automatisch Chrome
   - Headless-Mode ist aktiviert
   - Überprüfe Chrome-Version in Logs

3. **Credentials nicht gefunden**

   - Überprüfe, ob alle Credential-Dateien committed sind
   - Oder verwende Environment Variables

4. **Passwort-Fehler**
   - Überprüfe Repository Secret `ADMIN_PASSWORD`
   - Stelle sicher, dass das Passwort korrekt eingegeben wird

### **Debug-Modus**

```bash
# Lokal testen
python main_app.py

# Workflow manuell triggern
# GitHub → Actions → RunSync Tasks → Run workflow
```

## 📈 **Erweiterte Features**

### **Automatische Ausführung**

```yaml
# In .github/workflows/runsync.yml
on:
  schedule:
    - cron: '0 6 * * *' # Täglich um 6 Uhr
```

### **Benachrichtigungen**

```yaml
# Slack/Discord/Email Benachrichtigungen
- name: Notify on completion
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## 🎉 **Fertig!**

Deine RunSync-Funktionen laufen jetzt über GitHub Actions. Das ist eine kostenlose, skalierbare und sichere Lösung!

**Actions URL**: `https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions`

## 📞 **Support**

Bei Problemen:

1. Überprüfe die Logs in GitHub Actions
2. Teste lokal zuerst
3. Überprüfe Repository Secrets
4. Stelle sicher, dass alle Dependencies installiert sind

## 🔗 **Links**

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python Setup Action](https://github.com/actions/setup-python)
- [Chrome Setup for Selenium](https://github.com/actions/setup-chrome)

---

**Viel Erfolg mit deinem RunSync-Projekt!** 🏃‍♂️✨

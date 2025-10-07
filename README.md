# 🏃‍♂️ RunSync - GitHub Pages + GitHub Actions

Eine sichere Web-Interface-Lösung für deine RunSync Python-Funktionen, die über GitHub Pages läuft und GitHub Actions für die Ausführung verwendet.

## 🎯 **Was ist das?**

RunSync ist ein Tool, das deine Aktivitäten zwischen verschiedenen Plattformen synchronisiert:

- **Strava** → **Google Sheets** (Aktivitäten aktualisieren)
- **Google Sheets** → **P4/P7 Worksheets** (Daten verarbeiten)
- **Strava** → **Garmin** (Aktivitäten übertragen)

## 🌐 **Live Demo**

Nach dem Setup ist deine Website verfügbar unter:

```
https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/
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

### **2. GitHub Pages aktivieren**

1. Gehe zu deinem Repository auf GitHub
2. Klicke auf **Settings** → **Pages**
3. Unter **Source** wähle **GitHub Actions**
4. Speichere die Einstellungen

### **3. Repository Secrets konfigurieren**

Gehe zu **Settings** → **Secrets and variables** → **Actions** und füge hinzu:

- `ADMIN_PASSWORD`: Dein sicheres Passwort für die Web-Interface

### **4. Website anpassen**

Bearbeite `docs/secure-workflow-trigger.js` und ersetze:

```javascript
this.owner = 'YOUR_GITHUB_USERNAME'; // Dein GitHub Username
this.repo = 'YOUR_REPO_NAME'; // Dein Repository Name
```

## 📁 **Projektstruktur**

```
RunSync/
├── .github/
│   └── workflows/
│       ├── runsync.yml          # Hauptworkflow für Python-Funktionen
│       └── deploy-pages.yml     # GitHub Pages Deployment
├── docs/
│   ├── index.html              # Hauptwebsite
│   ├── secure-workflow-trigger.js  # Sichere Workflow-Integration
│   └── github-api.js           # GitHub API Integration (nicht verwendet)
├── main_app.py                 # Deine Python-Funktionen
├── strava_client.py
├── garmin_client.py
├── sheets_client.py
├── requirements.txt            # Python Dependencies
├── setup_github_pages.py       # Setup-Skript
└── README.md                   # Diese Datei
```

## 🔧 **Wie es funktioniert**

### **Website (GitHub Pages)**

- **Statische HTML-Website** in `docs/index.html`
- **Passwort-Schutz** für Sicherheit
- **4 Buttons** für deine Hauptfunktionen
- **Real-time Status-Updates** (simuliert)

### **Python-Funktionen (GitHub Actions)**

- **Workflow-Dispatch** triggert Python-Skripte
- **Ubuntu-Runner** mit Python 3.11
- **Chrome + Selenium** für Garmin-Integration
- **Alle Dependencies** automatisch installiert

## 🎮 **Verwendung**

### **1. Website öffnen**

Nach dem Deployment ist deine Website verfügbar unter:

```
https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/
```

### **2. Tasks ausführen**

1. **Passwort eingeben** (Standard: `admin123`)
2. **Button klicken** für gewünschte Funktion
3. **Anleitung wird angezeigt** mit allen Details
4. **GitHub Actions Link** öffnet sich automatisch
5. **Manuell ausführen** mit den angezeigten Parametern

### **3. Manuell über GitHub Actions**

Du kannst Tasks auch direkt über GitHub Actions starten:

1. Gehe zu **Actions** in deinem Repository
2. Wähle **RunSync Tasks**
3. Klicke **Run workflow**
4. Wähle Task-Typ und gib Passwort ein

## 🔒 **Sicherheit**

### **Passwort-Schutz**

- **Web-Interface**: Einfaches Passwort (in `docs/index.html`)
- **GitHub Actions**: Repository Secret `ADMIN_PASSWORD`
- **Beide müssen übereinstimmen**

### **Tokenlose Lösung**

- **Kein GitHub Token nötig** - 100% sicher
- **Manuelle Ausführung** über GitHub Actions
- **Keine API-Calls** von der Website

### **Repository Secrets**

```bash
# Sichere Passwörter generieren
ADMIN_PASSWORD=$(openssl rand -base64 32)
echo "ADMIN_PASSWORD=$ADMIN_PASSWORD"
```

## 🛠️ **Anpassungen**

### **Passwort ändern**

1. **Web-Interface**: Bearbeite `docs/index.html` Zeile 241
2. **GitHub Actions**: Aktualisiere Repository Secret `ADMIN_PASSWORD`

### **Neue Funktionen hinzufügen**

1. **Python-Funktion** in `main_app.py` erstellen
2. **Button** in `docs/index.html` hinzufügen
3. **Workflow-Step** in `.github/workflows/runsync.yml` hinzufügen

### **Website-Design anpassen**

- **CSS**: Bearbeite `<style>` in `docs/index.html`
- **Bootstrap**: Aktualisiere CDN-Links
- **Icons**: Font Awesome Icons verwenden

## 📊 **Monitoring**

### **GitHub Actions Logs**

- **Real-time Logs**: In GitHub Actions Tab
- **Fehler-Debugging**: Detaillierte Python-Stack-Traces
- **Performance**: Laufzeit-Statistiken

### **Website Analytics**

- **GitHub Pages**: Automatische Statistiken
- **Custom Analytics**: Google Analytics hinzufügen

## 🔄 **Updates**

### **Code aktualisieren**

```bash
# Änderungen committen
git add .
git commit -m "Update description"
git push origin main

# GitHub Pages wird automatisch aktualisiert
# GitHub Actions Workflows bleiben unverändert
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

1. **Website lädt nicht**

   - Überprüfe GitHub Pages Settings
   - Warte 5-10 Minuten nach dem ersten Push
   - Überprüfe Repository Secrets

2. **Workflow schlägt fehl**

   - Überprüfe Repository Secrets
   - Schaue in GitHub Actions Logs
   - Teste Python-Code lokal

3. **Chrome/Selenium Fehler**

   - Workflow installiert automatisch Chrome
   - Headless-Mode ist aktiviert
   - Überprüfe Chrome-Version in Logs

4. **Credentials nicht gefunden**
   - Überprüfe, ob alle Credential-Dateien committed sind
   - Oder verwende Environment Variables

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

### **Mehrere Umgebungen**

```yaml
# Staging und Production
strategy:
  matrix:
    environment: [staging, production]
```

## 🎉 **Fertig!**

Deine RunSync-Website läuft jetzt auf GitHub Pages und die Python-Funktionen werden über GitHub Actions ausgeführt. Das ist eine kostenlose, skalierbare und sichere Lösung!

**Website URL**: `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/`
**Actions URL**: `https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions`

## 📞 **Support**

Bei Problemen:

1. Überprüfe die Logs in GitHub Actions
2. Teste lokal zuerst
3. Überprüfe Repository Secrets
4. Stelle sicher, dass alle Dependencies installiert sind

## 🔗 **Links**

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Bootstrap Documentation](https://getbootstrap.com/docs/5.1/)
- [Font Awesome Icons](https://fontawesome.com/icons)

---

**Viel Erfolg mit deinem RunSync-Projekt!** 🏃‍♂️✨

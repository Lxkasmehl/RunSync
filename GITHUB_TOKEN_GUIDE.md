# 🔑 GitHub Token Setup Guide

## 🎯 **Problem gelöst!**

Die Website führt jetzt **automatisch** GitHub Actions aus und verwendet das **korrekte Passwort** aus deinen Repository Secrets.

## 🔧 **Was wurde geändert:**

### **✅ Automatische Workflow-Ausführung:**

- **Keine manuellen Anleitungen** mehr
- **Direkte API-Calls** zu GitHub Actions
- **Real-time Status-Updates**

### **✅ Passwort-Synchronisation:**

- **Website verwendet dein eingegebenes Passwort**
- **Wird an GitHub Actions weitergegeben**
- **Muss mit Repository Secret übereinstimmen**

### **✅ Token-Verwaltung:**

- **Sichere Token-Speicherung** im Browser
- **Token-Button** in der Website
- **Automatische Token-Abfrage** bei Bedarf

## 🚀 **So funktioniert es jetzt:**

### **1. GitHub Token erstellen:**

1. Gehe zu: **GitHub** → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Klicke **"Generate new token"** → **"Generate new token (classic)"**
3. **Name**: `RunSync Web Interface`
4. **Expiration**: Wähle eine passende Zeit (z.B. 1 Jahr)
5. **Scopes**: Aktiviere nur:
   - ✅ `repo` (für private Repos)
   - ✅ `workflow` (für GitHub Actions)
6. Klicke **"Generate token"**
7. **⚠️ WICHTIG**: Kopiere den Token sofort!

### **2. Token in der Website eingeben:**

1. **Website öffnen**: `https://lxkasmehl.github.io/RunSync/`
2. **Passwort eingeben**: Dein ADMIN_PASSWORD aus Repository Secrets
3. **Token-Button klicken**: Oben rechts in der Website
4. **Token eingeben**: Den Token aus Schritt 1
5. **Fertig!** Token wird gespeichert

### **3. Tasks ausführen:**

1. **Button klicken**: z.B. "Aktivitäten aktualisieren"
2. **Automatische Ausführung**: Workflow startet sofort
3. **Status-Updates**: Real-time Anzeige
4. **GitHub Actions Link**: Öffnet sich automatisch

## 🔒 **Sicherheit:**

### **Token-Sicherheit:**

- **Token wird nur im Browser gespeichert** (LocalStorage)
- **Niemals im Code** oder auf GitHub
- **Kann jederzeit gelöscht werden**

### **Passwort-Sicherheit:**

- **Website verwendet dein eingegebenes Passwort**
- **Muss mit Repository Secret übereinstimmen**
- **Wird sicher an GitHub Actions übertragen**

## 🛠️ **Token verwalten:**

### **Token anzeigen/ändern:**

- **Token-Button** in der Website klicken
- **Neuen Token eingeben** oder **aktuellen löschen**

### **Token löschen:**

- **Token-Button** → **"Löschen"** wählen
- **Oder Browser-Daten löschen**

## 🚨 **Troubleshooting:**

### **"Token nicht verfügbar" Fehler:**

1. **Token-Button klicken**
2. **Gültigen Token eingeben**
3. **Task erneut starten**

### **"Ungültiger Token" Fehler:**

1. **Neuen Token erstellen** (siehe Schritt 1)
2. **Korrekte Scopes setzen** (`repo` + `workflow`)
3. **Token in Website eingeben**

### **"Workflow schlägt fehl" Fehler:**

1. **Passwort überprüfen** (muss mit Repository Secret übereinstimmen)
2. **GitHub Actions Logs** anschauen
3. **Token-Berechtigung** überprüfen

## 📋 **Zusammenfassung:**

**Jetzt funktioniert es richtig:**

- ✅ **Automatische Ausführung** - keine manuellen Schritte
- ✅ **Korrektes Passwort** - aus Repository Secrets
- ✅ **Sichere Token-Verwaltung** - nur im Browser
- ✅ **Real-time Updates** - Status wird angezeigt

**Du musst nur einmal:**

1. **GitHub Token erstellen**
2. **Token in Website eingeben**
3. **Fertig!** Alles läuft automatisch

## 🎉 **Fertig!**

Deine RunSync-Website führt jetzt automatisch GitHub Actions aus und verwendet das korrekte Passwort. Das ist genau das, was du wolltest! 🚀

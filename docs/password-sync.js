// Passwort-Synchronisation zwischen Website und GitHub Secrets
class PasswordSync {
  constructor() {
    this.owner = 'Lxkasmehl';
    this.repo = 'RunSync';
  }

  // Passwort vom GitHub Secret abrufen (nur mit Token möglich)
  async getPasswordFromGitHub() {
    try {
      const token = await this.getGitHubToken();
      if (!token) {
        return null;
      }

      // GitHub Secrets können nicht über API abgerufen werden
      // Daher verwenden wir eine alternative Lösung
      return await this.getPasswordFromWorkflow();
    } catch (error) {
      console.error('Fehler beim Abrufen des Passworts:', error);
      return null;
    }
  }

  // Passwort über Workflow-Status abrufen
  async getPasswordFromWorkflow() {
    // Da GitHub Secrets nicht über API abgerufen werden können,
    // verwenden wir eine Workaround-Lösung
    return await this.getPasswordFromLocalStorage();
  }

  // Passwort aus LocalStorage abrufen
  async getPasswordFromLocalStorage() {
    const storedPassword = localStorage.getItem('runsync_password');
    if (storedPassword) {
      return storedPassword;
    }

    // Passwort vom User abfragen
    return await this.promptForPassword();
  }

  // Passwort vom User abfragen
  async promptForPassword() {
    return new Promise((resolve) => {
      const password = prompt(
        'Bitte geben Sie das RunSync-Passwort ein:\n\n' +
          'Dieses sollte mit dem ADMIN_PASSWORD Secret in GitHub übereinstimmen.'
      );
      resolve(password);
    });
  }

  // Passwort speichern
  savePassword(password) {
    if (password) {
      localStorage.setItem('runsync_password', password);
      return true;
    }
    return false;
  }

  // Passwort löschen
  clearPassword() {
    localStorage.removeItem('runsync_password');
  }

  // GitHub Token abrufen
  async getGitHubToken() {
    return localStorage.getItem('github_token');
  }

  // Passwort validieren
  async validatePassword(inputPassword) {
    const storedPassword = await this.getPasswordFromLocalStorage();
    return inputPassword === storedPassword;
  }
}

// Export für Verwendung in der HTML-Datei
window.PasswordSync = PasswordSync;

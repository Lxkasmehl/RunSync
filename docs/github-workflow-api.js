// GitHub Workflow API Integration mit automatischer Ausführung
class GitHubWorkflowAPI {
  constructor() {
    this.owner = 'Lxkasmehl';
    this.repo = 'RunSync';
    this.workflowFileName = 'runsync.yml';
  }

  // Automatische Workflow-Ausführung über GitHub API
  async triggerWorkflow(taskType, password) {
    try {
      // GitHub API Token aus Environment oder User Input
      const token = await this.getGitHubToken();

      if (!token) {
        return {
          success: false,
          error: 'GitHub Token nicht verfügbar. Bitte Token eingeben.',
          needsToken: true,
        };
      }

      const response = await fetch(
        `https://api.github.com/repos/${this.owner}/${this.repo}/actions/workflows/${this.workflowFileName}/dispatches`,
        {
          method: 'POST',
          headers: {
            Authorization: `token ${token}`,
            Accept: 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'RunSync-Web-Interface',
          },
          body: JSON.stringify({
            ref: 'main',
            inputs: {
              task_type: taskType,
              password: password,
            },
          }),
        }
      );

      if (response.ok) {
        return {
          success: true,
          message: `Workflow "${taskType}" wurde erfolgreich gestartet!`,
          workflowUrl: `https://github.com/${this.owner}/${this.repo}/actions`,
        };
      } else {
        const errorText = await response.text();
        return {
          success: false,
          error: `Fehler beim Starten des Workflows: ${response.status} - ${errorText}`,
        };
      }
    } catch (error) {
      return {
        success: false,
        error: `Netzwerk-Fehler: ${error.message}`,
      };
    }
  }

  // GitHub Token abrufen
  async getGitHubToken() {
    // Versuche Token aus verschiedenen Quellen zu bekommen
    const tokenSources = [
      () => localStorage.getItem('github_token'),
      () => sessionStorage.getItem('github_token'),
      () => this.promptForToken(),
    ];

    for (const source of tokenSources) {
      try {
        const token = await source();
        if (token && token.startsWith('ghp_')) {
          return token;
        }
      } catch (e) {
        continue;
      }
    }

    return null;
  }

  // Token vom User abfragen
  async promptForToken() {
    return new Promise((resolve) => {
      const token = prompt(
        'GitHub Personal Access Token eingeben:\n\n' +
          '1. Gehe zu: https://github.com/settings/tokens\n' +
          '2. Erstelle einen neuen Token mit "repo" und "workflow" Berechtigung\n' +
          '3. Kopiere den Token hier ein:'
      );
      resolve(token);
    });
  }

  // Token sicher speichern
  saveToken(token) {
    if (token && token.startsWith('ghp_')) {
      localStorage.setItem('github_token', token);
      return true;
    }
    return false;
  }

  // Token löschen
  clearToken() {
    localStorage.removeItem('github_token');
    sessionStorage.removeItem('github_token');
  }

  // Workflow Status abrufen
  async getWorkflowRuns() {
    try {
      const token = await this.getGitHubToken();
      if (!token) return { success: false, error: 'Kein Token verfügbar' };

      const response = await fetch(
        `https://api.github.com/repos/${this.owner}/${this.repo}/actions/runs?per_page=5`,
        {
          headers: {
            Authorization: `token ${token}`,
            Accept: 'application/vnd.github.v3+json',
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        return { success: true, runs: data.workflow_runs };
      } else {
        return { success: false, error: 'Fehler beim Abrufen der Workflow-Runs' };
      }
    } catch (error) {
      return { success: false, error: `Netzwerk-Fehler: ${error.message}` };
    }
  }

  // Workflow URL
  getWorkflowURL() {
    return `https://github.com/${this.owner}/${this.repo}/actions`;
  }
}

// Export für Verwendung in der HTML-Datei
window.GitHubWorkflowAPI = GitHubWorkflowAPI;

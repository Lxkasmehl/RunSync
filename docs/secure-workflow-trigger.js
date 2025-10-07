// Sichere GitHub Workflow Trigger ohne Token im Code
class SecureWorkflowTrigger {
  constructor() {
    this.owner = 'Lxkasmehl';
    this.repo = 'RunSync';
  }

  // Methode 1: Direkter Link zu GitHub Actions (Empfohlen)
  triggerWorkflowViaLink(taskType, password) {
    // Erstelle einen direkten Link zu GitHub Actions
    const workflowUrl = `https://github.com/${this.owner}/${this.repo}/actions/workflows/runsync.yml`;

    // Öffne GitHub Actions in neuem Tab
    window.open(workflowUrl, '_blank');

    return {
      success: true,
      message: 'GitHub Actions geöffnet. Bitte manuell ausführen.',
      url: workflowUrl,
    };
  }

  // Methode 2: Form-basierter Ansatz (funktioniert nicht ohne Token)
  triggerWorkflowViaForm(taskType, password) {
    // Erstelle eine Anleitung für manuelle Ausführung
    const instructions = `
      Manuelle Ausführung:
      1. Gehe zu: https://github.com/${this.owner}/${this.repo}/actions
      2. Klicke auf "RunSync Tasks"
      3. Klicke "Run workflow"
      4. Wähle Task: ${taskType}
      5. Passwort: ${password}
      6. Klicke "Run workflow"
    `;

    alert(instructions);

    return {
      success: true,
      message: 'Anleitung angezeigt',
      instructions: instructions,
    };
  }

  // Methode 3: GitHub CLI Command (für lokale Entwicklung)
  getGitHubCLICommand(taskType, password) {
    return `gh workflow run runsync.yml -f task_type=${taskType} -f password=${password}`;
  }

  getWorkflowURL() {
    return `https://github.com/${this.owner}/${this.repo}/actions`;
  }

  getSpecificWorkflowURL() {
    return `https://github.com/${this.owner}/${this.repo}/actions/workflows/runsync.yml`;
  }
}

// Export für Verwendung in der HTML-Datei
window.SecureWorkflowTrigger = SecureWorkflowTrigger;

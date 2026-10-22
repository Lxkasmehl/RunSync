#!/bin/sh
# Spielt den committeten Stand (HEAD) auf den n8n-Server und baut den Container neu.
# Nur mit dem Windows-SSH-Client, der Key ist im Windows-SSH-Agent entsperrt.
set -e
SSH=/c/Windows/System32/OpenSSH/ssh.exe
git archive HEAD | "$SSH" root@2.31.61.2 'rm -rf /opt/n8n/runsync && mkdir -p /opt/n8n/runsync && tar -x -C /opt/n8n/runsync && cd /opt/n8n && docker compose up -d --build runsync'

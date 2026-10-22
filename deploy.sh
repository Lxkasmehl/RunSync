#!/bin/sh
# Copies the committed state (HEAD) to the server and rebuilds the container.
# The server is set in .env as DEPLOY_HOST (e.g. root@203.0.113.10), next to the compose stack in /opt/n8n.
# SSH defaults to the Windows client (its agent holds the key); override with SSH=ssh.
set -e
HOST=${DEPLOY_HOST:-$(grep '^DEPLOY_HOST=' .env 2>/dev/null | cut -d= -f2-)}
[ -n "$HOST" ] || { echo "Set DEPLOY_HOST in .env (e.g. DEPLOY_HOST=root@203.0.113.10)"; exit 1; }
SSH=${SSH:-/c/Windows/System32/OpenSSH/ssh.exe}
git archive HEAD | "$SSH" "$HOST" 'rm -rf /opt/n8n/runsync && mkdir -p /opt/n8n/runsync && tar -x -C /opt/n8n/runsync && cd /opt/n8n && docker compose up -d --build runsync'

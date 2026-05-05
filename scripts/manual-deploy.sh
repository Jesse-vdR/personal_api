#!/usr/bin/env bash
# One-shot manual deploy from a workstation. Use when you can't push to main
# (no internet, debugging the GH Actions pipeline itself, etc.).

set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${HOST:-deploy@84.235.161.26}"
KEY="${KEY:-$HOME/.ssh/id_ed25519_jesse_deploy}"

git rev-parse --short HEAD > app/version.txt

tar czf - \
    --exclude '.git' \
    --exclude '.github' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    --exclude 'venv' \
    . | ssh -i "$KEY" "$HOST" 'cd /srv/jesse-api/repo && tar xzf - && bash scripts/deploy.sh'

rm -f app/version.txt

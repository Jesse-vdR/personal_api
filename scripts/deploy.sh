#!/usr/bin/env bash
# Runs on jesse-prod as the `deploy` user. Invoked over SSH by GitHub Actions
# after the runner has rsync'd the working tree to /srv/jesse-api/repo/.
#
# Idempotent: safe to re-run by hand for debugging.

set -euo pipefail

APP_DIR=/srv/jesse-api/repo
VENV=/srv/jesse-api/venv
SERVICE=jesse-api.service
WORKER=jesse-agent-worker.service
HEALTH_URL=http://127.0.0.1:8000/v1/health

cd "$APP_DIR"

# 1. Ensure venv exists and deps are current.
if [ ! -x "$VENV/bin/pip" ]; then
    rm -rf "$VENV"
    python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

# 2. Run DB migrations. Requires DATABASE_URL — sourced from the same env file
#    systemd uses for the service, so prod and migrations agree on the target.
set -a; . /etc/jesse/api.env; set +a
"$VENV/bin/alembic" upgrade head

# 3. Sync systemd units if they changed.
unit_changed=0
if ! sudo cmp -s systemd/jesse-api.service /etc/systemd/system/jesse-api.service; then
    sudo cp systemd/jesse-api.service /etc/systemd/system/jesse-api.service
    unit_changed=1
fi
if ! sudo cmp -s systemd/jesse-agent-worker.service /etc/systemd/system/jesse-agent-worker.service; then
    sudo cp systemd/jesse-agent-worker.service /etc/systemd/system/jesse-agent-worker.service
    unit_changed=1
fi
if [ "$unit_changed" = 1 ]; then
    sudo systemctl daemon-reload
fi

# 4. Sync nginx site if it changed.
if ! sudo cmp -s nginx/api.jesselab.space.conf /etc/nginx/sites-available/api.jesselab.space; then
    sudo cp nginx/api.jesselab.space.conf /etc/nginx/sites-available/api.jesselab.space
    sudo ln -sf /etc/nginx/sites-available/api.jesselab.space /etc/nginx/sites-enabled/api.jesselab.space
    sudo nginx -t
    sudo systemctl reload nginx
fi

# 5. Restart app + worker.
sudo systemctl enable --quiet "$SERVICE" "$WORKER"
sudo systemctl restart "$SERVICE" "$WORKER"

# 6. Health check (retry a few times for startup).
for i in 1 2 3 4 5; do
    if curl -fsS "$HEALTH_URL" > /dev/null; then
        echo "deploy ok"
        exit 0
    fi
    sleep 1
done

echo "health check failed" >&2
sudo journalctl -u "$SERVICE" --no-pager -n 30 >&2 || true
exit 1

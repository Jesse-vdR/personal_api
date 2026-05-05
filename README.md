# personal-api

FastAPI service backing the personal hub on `jesse-prod`. Roadmap: [Jesse-vdR/Jesse#9](https://github.com/Jesse-vdR/Jesse/issues/9). Architecture: [`docs/website-architecture.md`](https://github.com/Jesse-vdR/Jesse/blob/main/docs/website-architecture.md).

Status: v0 — health check only. Domain endpoints land in subsequent commits.

## Local dev

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
# → http://127.0.0.1:8000/v1/health
```

DB-backed work later: run Postgres in Docker.

```bash
docker run -d --name jesse-pg -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:15
```

## Deploy

`git push origin main` → GitHub Actions → SSH → `scripts/deploy.sh` on `jesse-prod`. Live target: `https://api.jesselab.space/v1/health`.

Manual deploy from a workstation (debug / first deploy):

```bash
rsync -az --delete --exclude '.git' --exclude '.github' --exclude 'venv' \
    -e "ssh -i ~/.ssh/id_ed25519_jesse_deploy" \
    ./ deploy@84.235.161.26:/srv/jesse-api/repo/
ssh -i ~/.ssh/id_ed25519_jesse_deploy deploy@84.235.161.26 \
    bash /srv/jesse-api/repo/scripts/deploy.sh
```

## Layout

```
app/main.py                       FastAPI app
requirements.txt                  pinned deps (pip)
systemd/jesse-api.service         systemd unit (synced to /etc/systemd/system/)
nginx/api.jesselab.space.conf     nginx site (synced to /etc/nginx/sites-available/)
scripts/deploy.sh                 invoked over SSH after rsync
.github/workflows/deploy.yml      push-to-main pipeline
```

## VM contract  _(one-time setup, see Jesse-vdR/Jesse#8 for the full backlog ticket)_

- `deploy` user exists, shell `/bin/bash`
- `/home/deploy/.ssh/authorized_keys` contains the public key whose private half is in GH secret `SSH_PRIVATE_KEY`
- `/srv/jesse-api/` owned by `deploy:deploy`
- Sudoers: `deploy ALL=NOPASSWD: /bin/cp, /bin/cmp, /bin/systemctl, /usr/bin/journalctl, /usr/sbin/nginx, /bin/ln`
  _(narrow set: only what `deploy.sh` calls under sudo)_
- nginx + Postgres + Let's Encrypt cert for `*.jesselab.space` already in place

## GH Actions secrets

| Name | Value |
|---|---|
| `SSH_PRIVATE_KEY` | private half of the deploy key (full PEM) |
| `SSH_HOST` | `84.235.161.26` |
| `SSH_USER` | `deploy` |

# personal-api

FastAPI service backing the personal hub on `jesse-prod`. Roadmap: [Jesse-vdR/Jesse#9](https://github.com/Jesse-vdR/Jesse/issues/9). Architecture: [`docs/website-architecture.md`](https://github.com/Jesse-vdR/Jesse/blob/main/docs/website-architecture.md).

Status: v0 — health, root, bearer-auth scaffold. DB-backed endpoints land in Phase 3.

Live: https://api.jesselab.space/v1/health

## Local dev

```bash
cp .env.example .env          # then edit BEARER_TOKEN to anything
make install                  # creates .venv, installs deps
make dev                      # uvicorn --reload at 127.0.0.1:8000
```

Smoke:

```bash
curl localhost:8000/v1/health
curl localhost:8000/v1/whoami                                      # 401
curl -H "Authorization: Bearer $YOUR_TOKEN" localhost:8000/v1/whoami  # 200
```

DB work (Phase 3+) needs Postgres. Don't dev against the prod DB. Cheapest local options:

```bash
# Docker (clean, ephemeral):
docker run -d --name jesse-pg -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:14
# Then in .env:
DATABASE_URL=postgresql://postgres:dev@localhost:5432/postgres
```

## Deploy

`git push origin main` → GitHub Actions → SSH → `scripts/deploy.sh` on `jesse-prod`. Live target: https://api.jesselab.space/v1/health. The deployed git short SHA appears in every response so you can confirm what's running.

Manual one-shot from a workstation: `make deploy`.

## Layout

```
app/
  main.py                       FastAPI app: routes, auth dep, logging setup
  config.py                     env-driven settings (loads .env in dev)
  version.txt                   short SHA, written by CI before rsync (gitignored)
requirements.txt                pinned deps
Makefile                        install / dev / deploy / clean
.env.example                    template for local dev env
systemd/jesse-api.service       systemd unit (synced to /etc/systemd/system/)
nginx/api.jesselab.space.conf   nginx site (synced to /etc/nginx/sites-available/)
scripts/deploy.sh               runs on VM after rsync
scripts/manual-deploy.sh        tar+ssh path for `make deploy`
.github/workflows/deploy.yml    push-to-main pipeline
```

## VM contract

- `deploy` user, `/srv/jesse-api/{repo,venv}` owned by `deploy:deploy`
- Sudoers: `deploy ALL=NOPASSWD: /bin/cp, /bin/cmp, /bin/systemctl, /usr/bin/journalctl, /usr/sbin/nginx, /bin/ln`
- Service env: `/etc/jesse/api.env` (mode 600, owner root). Contains at least `BEARER_TOKEN=...`. Loaded via `EnvironmentFile=-` in the systemd unit (`-` = optional, but auth-required endpoints return 503 until it exists).
- nginx + Postgres + Let's Encrypt cert for `*.jesselab.space` already in place

## GH Actions secrets

| Name | Value |
|---|---|
| `SSH_PRIVATE_KEY` | private half of the deploy key (`~/.ssh/id_ed25519_jesse_deploy`) |
| `SSH_HOST` | `84.235.161.26` |
| `SSH_USER` | `deploy` |

## Endpoints (v0)

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/` | public | `{service, version, sha}` |
| GET | `/v1/health` | public | `{ok, ts, sha}` |
| GET | `/v1/whoami` | bearer | `{authenticated: true}` |

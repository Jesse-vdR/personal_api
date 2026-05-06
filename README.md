# personal-api

FastAPI service backing the personal hub on `jesse-prod`. Roadmap: [Jesse-vdR/Jesse#9](https://github.com/Jesse-vdR/Jesse/issues/9). Architecture: [`docs/website-architecture.md`](https://github.com/Jesse-vdR/Jesse/blob/main/docs/website-architecture.md).

Status: multi-user. Google OAuth signup (open — no whitelist), `users` + `training_events` (per-user). DB-backed endpoints landed in Phase 3; auth landed in Jesse#11.

Live: https://api.jesselab.space/v1/health

## Local dev

```bash
cp .env.example .env
docker run -d --name jesse-pg -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:14
# In .env: DATABASE_URL=postgresql+psycopg2://postgres:dev@localhost:5432/postgres

# Generate a session signing secret:
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste the output into .env as SESSION_SECRET=...

make install                  # .venv + deps
make migrate                  # alembic upgrade head — creates users, seeds id=1
make dev                      # uvicorn --reload at 127.0.0.1:8000
```

### Google OAuth setup (one-time)

1. [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials) → Create OAuth client ID → **Web application**.
2. Add **Authorized redirect URIs**:
   - `http://localhost:8000/v1/auth/google/callback` (dev)
   - `https://api.jesselab.space/v1/auth/google/callback` (prod)
3. Copy `Client ID` + `Client secret` → `.env` (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`). For prod they go in `/etc/jesse/api.env`.

The first time Jesse signs in with `jesse.vanderiet@gmail.com`, the migration-seeded `user_id=1` row is claimed (its `google_sub` is overwritten with the real one), so all backfilled `training_events` stay attached to him. Anyone else who signs in becomes `user_id=2, 3, …` automatically.

### Smoke

```bash
curl localhost:8000/v1/health                                # public, 200
curl localhost:8000/v1/me                                    # 401 (no session)
open 'http://localhost:8000/v1/auth/google/login?next=http://localhost:8001/'
# → Google consent → callback sets jesse_session cookie → redirects to next
curl -b jesse_session=<copy-cookie> localhost:8000/v1/me     # 200, user JSON
curl -b jesse_session=<copy-cookie> -X POST localhost:8000/v1/auth/logout
```

Frontend talking to the API in dev:
- include the session cookie: `fetch(url, { credentials: 'include' })`
- the frontend origin must be in `ALLOWED_REDIRECT_ORIGINS` (CORS allowlist + `?next=` allowlist)

New schema change: `make revision m="add foo table"` → review the file in `alembic/versions/` → `make migrate`.

## Deploy

`git push origin main` → GitHub Actions → SSH → `scripts/deploy.sh` on `jesse-prod`. Live target: https://api.jesselab.space/v1/health. The deployed git short SHA appears in every response so you can confirm what's running. `deploy.sh` runs `alembic upgrade head` before restarting the service.

Manual one-shot from a workstation: `make deploy`.

## Layout

```
app/
  main.py                       FastAPI app: middleware, routers, health/root
  config.py                     env-driven settings (loads .env in dev)
  db.py                         SQLAlchemy engine + session + DeclarativeBase
  auth.py                       OAuth client + require_session dep
  models/                       ORM models (registered for Alembic autogen)
  routers/auth.py               /v1/auth/google/{login,callback}, /v1/auth/logout, /v1/me
  routers/training.py           /v1/training/events (per-user)
  schemas/                      Pydantic request/response models
  version.txt                   short SHA, written by CI before rsync (gitignored)
alembic/                        migration scripts
alembic.ini                     alembic config
requirements.txt                pinned deps
Makefile                        install / dev / migrate / revision / deploy / clean
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
- Service env: `/etc/jesse/api.env` (mode 640, root:deploy). Must contain `DATABASE_URL`, `SESSION_SECRET`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `ALLOWED_REDIRECT_ORIGINS`, `COOKIE_DOMAIN=.jesselab.space`, `COOKIE_SECURE=true`, `DEFAULT_POST_LOGIN_URL`. Loaded by both the systemd unit (`EnvironmentFile=-`) and `deploy.sh` (sourced unconditionally — alembic fails loudly if DATABASE_URL is missing).
- Postgres role `jesse_api` owns DB `jesse_api` on `127.0.0.1:5432`.
- nginx + Postgres + Let's Encrypt cert for `*.jesselab.space` already in place.

## GH Actions secrets

| Name | Value |
|---|---|
| `SSH_PRIVATE_KEY` | private half of the deploy key (`~/.ssh/id_ed25519_jesse_deploy`) |
| `SSH_HOST` | `84.235.161.26` |
| `SSH_USER` | `deploy` |

## Endpoints

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/` | public | `{service, version, sha}` |
| GET | `/v1/health` | public | `{ok, ts, sha}` |
| GET | `/v1/auth/google/login?next=<url>` | public | 302 → Google consent screen |
| GET | `/v1/auth/google/callback` | public | 302 → `next` (or `DEFAULT_POST_LOGIN_URL`); sets `jesse_session` cookie |
| POST | `/v1/auth/logout` | public | clears the session cookie |
| GET | `/v1/me` | session | `{id, email, name, avatar_url}` |
| POST | `/v1/training/events` | session | creates an event for the current user |
| GET | `/v1/training/events?since=YYYY-MM-DD` | session | events for the current user |

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers.agents import preview_router as agents_preview_router
from app.routers.agents import router as agents_router
from app.routers.auth import router as auth_router
from app.routers.goals import router as goals_router
from app.routers.intake import router as intake_router
from app.routers.journal import router as journal_router
from app.routers.long_term import router as long_term_router
from app.routers.plans import router as plans_router
from app.routers.profile import router as profile_router
from app.routers.projects import router as projects_router
from app.routers.tracks import router as tracks_router
from app.routers.training import router as training_router

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("jesse-api")

_version_file = Path(__file__).parent / "version.txt"
SHA = _version_file.read_text().strip() if _version_file.exists() else "dev"

app = FastAPI(title="jesse-api", version="0.0.1")

session_secret = settings.session_secret or "DEV_PLACEHOLDER_DO_NOT_USE_IN_PRODUCTION"
if not settings.session_secret:
    log.warning("SESSION_SECRET not set — using insecure placeholder")
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="jesse_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.cookie_secure,
    domain=settings.cookie_domain or None,
)

cors_origins = [o.strip() for o in settings.allowed_redirect_origins.split(",") if o.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(training_router)
app.include_router(tracks_router)
app.include_router(goals_router)
app.include_router(plans_router)
app.include_router(profile_router)
app.include_router(long_term_router)
app.include_router(agents_router)
app.include_router(agents_preview_router)
app.include_router(journal_router)
app.include_router(intake_router)
app.include_router(projects_router)
log.info("jesse-api starting sha=%s log_level=%s", SHA, settings.log_level)


@app.get("/")
def root() -> dict:
    return {"service": "jesse-api", "version": app.version, "sha": SHA}


@app.get("/v1/health")
def health() -> dict:
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat(), "sha": SHA}

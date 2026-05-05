import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("jesse-api")

_version_file = Path(__file__).parent / "version.txt"
SHA = _version_file.read_text().strip() if _version_file.exists() else "dev"

app = FastAPI(title="jesse-api", version="0.0.1")
log.info("jesse-api starting sha=%s log_level=%s", SHA, settings.log_level)

bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    if not settings.bearer_token:
        log.error("BEARER_TOKEN not configured — refusing auth-required request")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "auth not configured")
    if credentials is None or credentials.credentials != settings.bearer_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing bearer token")


@app.get("/")
def root() -> dict:
    return {"service": "jesse-api", "version": app.version, "sha": SHA}


@app.get("/v1/health")
def health() -> dict:
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat(), "sha": SHA}


@app.get("/v1/whoami")
def whoami(_: Annotated[None, Depends(require_bearer)]) -> dict:
    return {"authenticated": True}

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

log = logging.getLogger("jesse-api.auth")

bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    if not settings.bearer_token:
        log.error("BEARER_TOKEN not configured — refusing auth-required request")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "auth not configured")
    if credentials is None or credentials.credentials != settings.bearer_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing bearer token")

import logging
from typing import Annotated
from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth, require_session
from app.config import settings
from app.db import get_session
from app.models.user import User

log = logging.getLogger("jesse-api.auth")
router = APIRouter(prefix="/v1", tags=["auth"])


def _allowed_origins() -> list[str]:
    return [o.strip() for o in settings.allowed_redirect_origins.split(",") if o.strip()]


def _is_allowed_redirect(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    return f"{parsed.scheme}://{parsed.netloc}" in _allowed_origins()


@router.get("/auth/google/login")
async def google_login(request: Request, next: str | None = None) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google OAuth not configured")
    if next and _is_allowed_redirect(next):
        request.session["post_login_redirect"] = next
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        log.warning("oauth callback failed: %s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "oauth callback failed") from exc

    info = token.get("userinfo") or {}
    sub, email = info.get("sub"), info.get("email")
    if not sub or not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing sub/email from Google")

    user = session.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        # First-time sign-in: claim a migration-seeded row if one matches
        # this email, otherwise create a fresh user row.
        seed_sub = f"migration-seed:{email}"
        user = session.scalar(select(User).where(User.google_sub == seed_sub))
        if user is not None:
            user.google_sub = sub
            log.info("claimed migration-seed user id=%s email=%s", user.id, email)
        else:
            user = User(google_sub=sub, email=email)
            session.add(user)
            session.flush()
            log.info("new user signup id=%s email=%s", user.id, email)

    new_name, new_avatar = info.get("name"), info.get("picture")
    if new_name and user.name != new_name:
        user.name = new_name
    if new_avatar and user.avatar_url != new_avatar:
        user.avatar_url = new_avatar
    if user.email != email:
        user.email = email
    session.commit()

    request.session["user_id"] = user.id
    target = request.session.pop("post_login_redirect", None) or settings.default_post_login_url
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


@router.post("/auth/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(user: Annotated[User, Depends(require_session)]) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
    }

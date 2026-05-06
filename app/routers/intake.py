import hashlib
import logging
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_session
from app.config import settings
from app.db import get_session
from app.models.intake import Intake
from app.models.media import Media
from app.models.user import User
from app.schemas.intake import IntakeOut

log = logging.getLogger("jesse-api.intake")
router = APIRouter(prefix="/v1/intake", tags=["intake"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SLUG_PATTERN = re.compile(r"^([a-z0-9][a-z0-9-]*)\s*:\s*(.*)$", re.DOTALL)
TG_API = "https://api.telegram.org"
TG_TIMEOUT_S = 30.0


def _check_bearer(authorization: str | None) -> None:
    if not settings.telegram_intake_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "intake not configured")
    expected = f"Bearer {settings.telegram_intake_token}"
    if authorization != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid intake token")


def _check_telegram_secret(secret: str | None) -> None:
    if not settings.telegram_intake_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "intake not configured")
    if secret != settings.telegram_intake_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid telegram secret")


def parse_caption(caption: str | None) -> tuple[str, str]:
    """Split a `<slug>: body` caption. Falls back to ('inbox', caption)."""
    if not caption:
        return ("inbox", "")
    m = SLUG_PATTERN.match(caption.strip())
    if m:
        return (m.group(1), m.group(2).strip())
    return ("inbox", caption.strip())


def _extension(filename: str | None, content_type: str | None) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        if ext:
            return ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    return ".bin"


def _store_media(
    session: Session, user_id: int, blob: bytes, mime: str, filename: str | None
) -> Media:
    sha = hashlib.sha256(blob).hexdigest()
    existing = session.scalar(
        select(Media).where(Media.user_id == user_id, Media.sha256 == sha)
    )
    if existing is not None:
        return existing
    yyyy_mm = datetime.now(timezone.utc).strftime("%Y-%m")
    ext = _extension(filename, mime)
    abs_dir = Path(settings.media_root) / str(user_id) / "inspiration" / yyyy_mm
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = abs_dir / f"{sha}{ext}"
    abs_path.write_bytes(blob)

    media = Media(
        user_id=user_id,
        sha256=sha,
        path=str(abs_path),
        mime=mime or "application/octet-stream",
        bytes=len(blob),
    )
    session.add(media)
    session.flush()
    return media


def _media_url(media_id: int | None) -> str | None:
    return f"/v1/intake/media/{media_id}" if media_id is not None else None


def _serialize(row: Intake) -> IntakeOut:
    return IntakeOut(
        id=row.id,
        ts=row.ts,
        project_slug=row.project_slug,
        body=row.body,
        media_url=_media_url(row.media_id),
        source=row.source,
    )


@router.post("", response_model=IntakeOut, status_code=status.HTTP_201_CREATED)
async def create_intake(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    text: Annotated[str | None, Form()] = None,
    caption: Annotated[str | None, Form()] = None,
    source: Annotated[str, Form()] = "external",
    media: UploadFile | None = None,
) -> IntakeOut:
    _check_bearer(authorization)
    if media is not None and media.size is not None and media.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"media exceeds {MAX_UPLOAD_BYTES} bytes",
        )

    slug, parsed_body = parse_caption(caption)
    parts = [p for p in (parsed_body, text) if p]
    body = "\n\n".join(parts) or None

    user_id = settings.telegram_owner_user_id

    media_row: Media | None = None
    if media is not None:
        blob = await media.read()
        if blob:
            media_row = _store_media(
                session,
                user_id,
                blob,
                media.content_type or "application/octet-stream",
                media.filename,
            )

    row = Intake(
        user_id=user_id,
        ts=datetime.now(timezone.utc),
        project_slug=slug,
        body=body,
        media_id=media_row.id if media_row else None,
        source=source,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log.info(
        "intake id=%s user=%s slug=%s source=%s media=%s",
        row.id, user_id, slug, source, media_row.id if media_row else None,
    )
    return _serialize(row)


@router.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    secret: Annotated[
        str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")
    ] = None,
) -> dict:
    _check_telegram_secret(secret)
    if not settings.telegram_bot_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "telegram bot not configured"
        )

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True, "ignored": "no message"}

    chat_id = message.get("chat", {}).get("id")
    raw_text = message.get("text") or message.get("caption")
    slug, parsed_body = parse_caption(raw_text)

    file_id, suggested_name, suggested_mime = _extract_file(message)

    media_row: Media | None = None
    if file_id:
        try:
            blob, mime, filename = await _telegram_download(
                file_id, suggested_name, suggested_mime
            )
            media_row = _store_media(
                session, settings.telegram_owner_user_id, blob, mime, filename
            )
        except Exception as exc:
            log.warning("telegram media fetch failed: %s", exc)

    row = Intake(
        user_id=settings.telegram_owner_user_id,
        ts=datetime.now(timezone.utc),
        project_slug=slug,
        body=parsed_body or None,
        media_id=media_row.id if media_row else None,
        source="telegram",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log.info(
        "intake id=%s telegram chat=%s slug=%s media=%s",
        row.id, chat_id, slug, media_row.id if media_row else None,
    )

    if chat_id is not None:
        try:
            await _telegram_reply(chat_id, f"got it → {slug}")
        except Exception as exc:
            log.warning("telegram reply failed: %s", exc)

    return {"ok": True, "intake_id": row.id}


@router.get("/media/{media_id}")
def get_media(
    media_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> FileResponse:
    media = session.get(Media, media_id)
    if media is None or media.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "media not found")
    path = Path(media.path)
    if not path.is_file():
        log.error("media row %s missing on disk: %s", media_id, media.path)
        raise HTTPException(status.HTTP_410_GONE, "media file missing on disk")
    return FileResponse(path, media_type=media.mime)


def _extract_file(message: dict) -> tuple[str | None, str | None, str | None]:
    """Pull the first attachment file_id out of a Telegram Message. Returns
    (file_id, suggested_filename, suggested_mime). Photos pick the largest size."""
    if photos := message.get("photo"):
        return photos[-1].get("file_id"), None, "image/jpeg"
    if doc := message.get("document"):
        return doc.get("file_id"), doc.get("file_name"), doc.get("mime_type")
    if voice := message.get("voice"):
        return voice.get("file_id"), None, voice.get("mime_type") or "audio/ogg"
    if audio := message.get("audio"):
        return audio.get("file_id"), audio.get("file_name"), audio.get("mime_type")
    if video := message.get("video"):
        return video.get("file_id"), video.get("file_name"), video.get("mime_type") or "video/mp4"
    return None, None, None


async def _telegram_download(
    file_id: str, suggested_name: str | None, suggested_mime: str | None
) -> tuple[bytes, str, str | None]:
    async with httpx.AsyncClient(timeout=TG_TIMEOUT_S) as client:
        meta = await client.get(
            f"{TG_API}/bot{settings.telegram_bot_token}/getFile",
            params={"file_id": file_id},
        )
        meta.raise_for_status()
        info = meta.json().get("result", {})
        file_path = info.get("file_path")
        if not file_path:
            raise RuntimeError("no file_path from getFile")
        dl = await client.get(
            f"{TG_API}/file/bot{settings.telegram_bot_token}/{file_path}"
        )
        dl.raise_for_status()
        filename = suggested_name or Path(file_path).name
        mime = (
            suggested_mime
            or dl.headers.get("content-type")
            or "application/octet-stream"
        )
        return dl.content, mime, filename


async def _telegram_reply(chat_id: int, text_msg: str) -> None:
    async with httpx.AsyncClient(timeout=TG_TIMEOUT_S) as client:
        resp = await client.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text_msg},
        )
        resp.raise_for_status()

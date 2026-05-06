import hashlib
import logging
import mimetypes
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_session
from app.config import settings
from app.db import get_session
from app.models.journal_entry import JournalEntry
from app.models.media import Media
from app.models.user import User
from app.schemas.journal_entry import (
    JournalDateCount,
    JournalEntryOut,
    JournalEntryPatch,
)

log = logging.getLogger("jesse-api.journal")
router = APIRouter(prefix="/v1/journal", tags=["journal"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
WHISPER_MODEL = "whisper-1"
WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_TIMEOUT_S = 120.0


def _audio_url(media_id: int | None) -> str | None:
    return f"/v1/journal/media/{media_id}" if media_id is not None else None


def _serialize(entry: JournalEntry) -> JournalEntryOut:
    return JournalEntryOut(
        id=entry.id,
        ts=entry.ts,
        local_date=entry.local_date,
        kind=entry.kind,
        body=entry.body,
        audio_url=_audio_url(entry.media_id),
    )


def _audio_extension(filename: str | None, content_type: str | None) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        if ext:
            return ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    return ".bin"


def _store_audio(
    session: Session, user_id: int, audio_bytes: bytes, audio: UploadFile
) -> Media:
    sha = hashlib.sha256(audio_bytes).hexdigest()
    existing = session.scalar(
        select(Media).where(Media.user_id == user_id, Media.sha256 == sha)
    )
    if existing is not None:
        return existing

    yyyy_mm = datetime.now(timezone.utc).strftime("%Y-%m")
    ext = _audio_extension(audio.filename, audio.content_type)
    rel_dir = Path(str(user_id)) / "journal" / yyyy_mm
    abs_dir = Path(settings.media_root) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = abs_dir / f"{sha}{ext}"
    abs_path.write_bytes(audio_bytes)

    media = Media(
        user_id=user_id,
        sha256=sha,
        path=str(abs_path),
        mime=audio.content_type or "application/octet-stream",
        bytes=len(audio_bytes),
    )
    session.add(media)
    session.flush()
    return media


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile,
    _user: Annotated[User, Depends(require_session)],
) -> dict:
    if not settings.openai_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "transcription not configured"
        )
    if audio.size is not None and audio.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"audio exceeds {MAX_UPLOAD_BYTES} bytes",
        )

    files = {
        "file": (
            audio.filename or "audio",
            audio.file,
            audio.content_type or "application/octet-stream",
        )
    }
    data = {"model": WHISPER_MODEL, "response_format": "verbose_json"}
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    async with httpx.AsyncClient(timeout=WHISPER_TIMEOUT_S) as client:
        resp = await client.post(WHISPER_URL, files=files, data=data, headers=headers)

    if resp.status_code >= 400:
        log.warning("whisper failed status=%s body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "transcription failed")

    body = resp.json()
    return {
        "transcript": body.get("text", ""),
        "duration": body.get("duration"),
        "model": WHISPER_MODEL,
    }


@router.post(
    "/entries", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED
)
async def create_entry(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
    kind: Annotated[str, Form()] = "text",
    body: Annotated[str | None, Form()] = None,
    ts: Annotated[datetime | None, Form()] = None,
    local_date: Annotated[date | None, Form()] = None,
    audio: UploadFile | None = None,
) -> JournalEntryOut:
    if audio is not None and audio.size is not None and audio.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"audio exceeds {MAX_UPLOAD_BYTES} bytes",
        )

    now = datetime.now(timezone.utc)
    entry_ts = ts or now
    entry_local_date = local_date or entry_ts.date()

    media_id: int | None = None
    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > 0:
            media = _store_audio(session, user.id, audio_bytes, audio)
            media_id = media.id

    entry = JournalEntry(
        user_id=user.id,
        ts=entry_ts,
        local_date=entry_local_date,
        kind=kind,
        body=body,
        media_id=media_id,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _serialize(entry)


@router.get("/entries", response_model=list[JournalEntryOut])
def list_entries(
    date: date,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> list[JournalEntryOut]:
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.user_id == user.id, JournalEntry.local_date == date)
        .order_by(JournalEntry.ts.asc())
    )
    return [_serialize(e) for e in session.scalars(stmt).all()]


@router.get("/dates", response_model=list[JournalDateCount])
def list_dates(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
    since: date | None = None,
) -> list[JournalDateCount]:
    stmt = (
        select(JournalEntry.local_date, func.count(JournalEntry.id))
        .where(JournalEntry.user_id == user.id)
        .group_by(JournalEntry.local_date)
        .order_by(JournalEntry.local_date.desc())
    )
    if since is not None:
        stmt = stmt.where(JournalEntry.local_date >= since)
    return [JournalDateCount(date=d, count=c) for d, c in session.execute(stmt).all()]


@router.patch("/entries/{entry_id}", response_model=JournalEntryOut)
def patch_entry(
    entry_id: int,
    payload: JournalEntryPatch,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> JournalEntryOut:
    entry = session.get(JournalEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    entry.body = payload.body
    session.commit()
    session.refresh(entry)
    return _serialize(entry)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> None:
    entry = session.get(JournalEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    session.delete(entry)
    session.commit()


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

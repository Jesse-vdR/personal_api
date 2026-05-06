import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.auth import require_session
from app.config import settings
from app.models.user import User

log = logging.getLogger("jesse-api.journal")
router = APIRouter(prefix="/v1/journal", tags=["journal"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
WHISPER_MODEL = "whisper-1"
WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_TIMEOUT_S = 120.0


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

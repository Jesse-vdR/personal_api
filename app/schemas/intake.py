from datetime import datetime

from pydantic import BaseModel


class IntakeOut(BaseModel):
    id: int
    ts: datetime
    project_slug: str
    body: str | None
    media_url: str | None
    source: str


class IntakePending(BaseModel):
    """Server-to-server view for the inspiration agent. Returns absolute disk
    paths so the agent (same VM) can read media without an extra HTTP hop."""
    id: int
    ts: datetime
    project_slug: str
    body: str | None
    source: str
    media_path: str | None
    media_mime: str | None
    media_sha256: str | None


class IntakeProcessedRequest(BaseModel):
    failure_reason: str | None = None

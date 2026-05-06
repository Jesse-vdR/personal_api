from datetime import datetime

from pydantic import BaseModel


class IntakeOut(BaseModel):
    id: int
    ts: datetime
    project_slug: str
    body: str | None
    media_url: str | None
    source: str

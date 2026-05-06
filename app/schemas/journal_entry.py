from datetime import date, datetime

from pydantic import BaseModel


class JournalEntryOut(BaseModel):
    id: int
    ts: datetime
    local_date: date
    kind: str
    body: str | None
    audio_url: str | None


class JournalEntryPatch(BaseModel):
    body: str


class JournalDateCount(BaseModel):
    date: date
    count: int

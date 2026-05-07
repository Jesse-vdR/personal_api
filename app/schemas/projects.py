from datetime import datetime

from pydantic import BaseModel


class ProjectOut(BaseModel):
    slug: str
    entry_count: int
    last_intake_at: datetime

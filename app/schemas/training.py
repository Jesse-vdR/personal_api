from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrainingEventIn(BaseModel):
    ts: datetime
    local_date: date
    kind: Literal["set", "hold", "stage_pass", "run", "session"]
    exercise: str | None = Field(default=None, min_length=1, max_length=64)
    reps: int | None = Field(default=None, ge=0)
    duration_s: int | None = Field(default=None, ge=0)
    track: str | None = Field(default=None, min_length=1, max_length=64)
    stage: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=2000)


class TrainingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    local_date: date
    kind: str
    exercise: str | None
    reps: int | None
    duration_s: int | None
    track: str | None
    stage: int | None
    note: str | None
    schema_v: int
    created_at: datetime

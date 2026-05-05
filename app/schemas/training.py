from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrainingEventIn(BaseModel):
    ts: datetime
    local_date: date
    exercise: str = Field(min_length=1, max_length=64)
    kind: Literal["set"]
    reps: int | None = Field(default=None, ge=0)


class TrainingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    local_date: date
    exercise: str
    kind: str
    reps: int | None
    schema_v: int
    created_at: datetime

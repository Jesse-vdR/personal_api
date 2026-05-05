from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanIn(BaseModel):
    week_start: date
    body: dict[str, Any]
    generated_by: str = Field(default="manual", min_length=1, max_length=64)


class PlanPatch(BaseModel):
    week_start: date | None = None
    body: dict[str, Any] | None = None
    generated_by: str | None = Field(default=None, min_length=1, max_length=64)


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    week_start: date
    body: dict[str, Any]
    generated_by: str
    created_at: datetime

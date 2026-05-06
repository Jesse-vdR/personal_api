from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GoalIn(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    display: str = Field(min_length=1, max_length=255)
    start_date: date | None = None
    deadline: date | None = None
    status: str = Field(default="active", min_length=1, max_length=32)
    tracks: list[dict[str, Any]]


class GoalPatch(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    display: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    deadline: date | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    tracks: list[dict[str, Any]] | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display: str
    start_date: date | None
    deadline: date | None
    status: str
    tracks: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

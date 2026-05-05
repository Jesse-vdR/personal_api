from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrackIn(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    display: str = Field(min_length=1, max_length=255)
    stages: list[dict[str, Any]]


class TrackPatch(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    display: str | None = Field(default=None, min_length=1, max_length=255)
    stages: list[dict[str, Any]] | None = None


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display: str
    stages: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

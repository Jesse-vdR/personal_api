from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentJobIn(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    input: dict[str, Any] = Field(default_factory=dict)


class AgentJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

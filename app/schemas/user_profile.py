from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserProfileIn(BaseModel):
    body: dict[str, Any]


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    body: dict[str, Any]
    updated_at: datetime

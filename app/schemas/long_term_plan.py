from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LongTermPlanIn(BaseModel):
    body: dict[str, Any]


class LongTermPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    body: dict[str, Any]
    updated_at: datetime

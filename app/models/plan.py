from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_plans_user_week_start"),
        Index("ix_plans_user_id", "user_id"),
        Index("ix_plans_user_week_start_desc", "user_id", text("week_start DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_by: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="manual"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

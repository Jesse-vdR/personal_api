from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AgentJob(Base):
    __tablename__ = "agent_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','succeeded','failed')",
            name="ck_agent_jobs_status",
        ),
        Index("ix_agent_jobs_user_id", "user_id"),
        Index(
            "ix_agent_jobs_user_kind_created",
            "user_id",
            "kind",
            text("created_at DESC"),
        ),
        Index(
            "ix_agent_jobs_queued",
            "created_at",
            postgresql_where=text("status = 'queued'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="queued"
    )
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

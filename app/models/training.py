from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TrainingEvent(Base):
    __tablename__ = "training_events"
    __table_args__ = (
        UniqueConstraint("user_id", "ts", "exercise", "kind", name="uq_training_events_natural"),
        Index("ix_training_events_local_date_exercise", "local_date", "exercise"),
        Index("ix_training_events_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    exercise: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    track: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stage: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_v: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

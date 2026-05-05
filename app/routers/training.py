from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.training import TrainingEvent
from app.models.user import User
from app.schemas.training import TrainingEventIn, TrainingEventOut

router = APIRouter(prefix="/v1/training", tags=["training"])


@router.post(
    "/events",
    response_model=TrainingEventOut,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: TrainingEventIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> TrainingEvent:
    event = TrainingEvent(
        user_id=user.id,
        ts=payload.ts,
        local_date=payload.local_date,
        exercise=payload.exercise,
        kind=payload.kind,
        reps=payload.reps,
        duration_s=payload.duration_s,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/events", response_model=list[TrainingEventOut])
def list_events(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
    since: date | None = None,
) -> list[TrainingEvent]:
    stmt = (
        select(TrainingEvent)
        .where(TrainingEvent.user_id == user.id)
        .order_by(TrainingEvent.ts.asc())
    )
    if since is not None:
        stmt = stmt.where(TrainingEvent.local_date >= since)
    return list(session.scalars(stmt).all())

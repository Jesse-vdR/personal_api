from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import GoalIn, GoalOut, GoalPatch

router = APIRouter(prefix="/v1/training/goals", tags=["training"])


def _get_owned(session: Session, user: User, goal_id: int) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "goal not found")
    return goal


@router.get("", response_model=list[GoalOut])
def list_goals(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> list[Goal]:
    stmt = select(Goal).where(Goal.user_id == user.id).order_by(Goal.deadline.asc())
    return list(session.scalars(stmt).all())


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Goal:
    return _get_owned(session, user, goal_id)


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Goal:
    goal = Goal(
        user_id=user.id,
        slug=payload.slug,
        display=payload.display,
        start_date=payload.start_date,
        deadline=payload.deadline,
        status=payload.status,
        tracks=payload.tracks,
    )
    session.add(goal)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"goal slug already exists: {payload.slug}"
        ) from exc
    session.refresh(goal)
    return goal


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: int,
    payload: GoalPatch,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Goal:
    goal = _get_owned(session, user, goal_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(goal, k, v)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "slug conflicts with another goal"
        ) from exc
    session.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> None:
    goal = _get_owned(session, user, goal_id)
    session.delete(goal)
    session.commit()

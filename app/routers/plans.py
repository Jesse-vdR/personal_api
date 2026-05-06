from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.plan import Plan
from app.models.user import User
from app.schemas.plan import PlanIn, PlanOut, PlanPatch

router = APIRouter(prefix="/v1/training/plans", tags=["training"])


def _get_owned(session: Session, user: User, plan_id: int) -> Plan:
    plan = session.get(Plan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    return plan


@router.get("", response_model=list[PlanOut])
def list_plans(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> list[Plan]:
    stmt = (
        select(Plan)
        .where(Plan.user_id == user.id)
        .order_by(Plan.week_start.desc())
    )
    return list(session.scalars(stmt).all())


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(
    plan_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Plan:
    return _get_owned(session, user, plan_id)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Plan:
    plan = Plan(
        user_id=user.id,
        week_start=payload.week_start,
        body=payload.body,
        generated_by=payload.generated_by,
    )
    session.add(plan)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"plan already exists for week_start={payload.week_start.isoformat()}",
        ) from exc
    session.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int,
    payload: PlanPatch,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Plan:
    plan = _get_owned(session, user, plan_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(plan, k, v)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "week_start conflicts with another plan"
        ) from exc
    session.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> None:
    plan = _get_owned(session, user, plan_id)
    session.delete(plan)
    session.commit()

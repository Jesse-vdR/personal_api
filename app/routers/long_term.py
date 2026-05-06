from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.long_term_plan import LongTermPlan
from app.models.user import User
from app.schemas.long_term_plan import LongTermPlanIn, LongTermPlanOut

router = APIRouter(prefix="/v1/training/long-term", tags=["training"])


@router.get("", response_model=LongTermPlanOut)
def get_long_term(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> LongTermPlan:
    plan = session.get(LongTermPlan, user.id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "long-term plan not set")
    return plan


@router.put("", response_model=LongTermPlanOut)
def put_long_term(
    payload: LongTermPlanIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> LongTermPlan:
    plan = session.get(LongTermPlan, user.id)
    if plan is None:
        plan = LongTermPlan(user_id=user.id, body=payload.body)
        session.add(plan)
    else:
        plan.body = payload.body
    session.commit()
    session.refresh(plan)
    return plan


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_long_term(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> None:
    plan = session.get(LongTermPlan, user.id)
    if plan is None:
        return
    session.delete(plan)
    session.commit()

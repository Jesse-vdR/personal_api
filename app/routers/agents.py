from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import skills
from app.agents.skills import generate_plan
from app.auth import require_session
from app.db import get_session
from app.models.agent_job import AgentJob
from app.models.user import User
from app.schemas.agent_job import AgentJobIn, AgentJobOut

router = APIRouter(prefix="/v1/agents/jobs", tags=["agents"])
preview_router = APIRouter(prefix="/v1/agents/generate-plan", tags=["agents"])


@router.post("", response_model=AgentJobOut, status_code=status.HTTP_201_CREATED)
def enqueue_job(
    payload: AgentJobIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> AgentJob:
    if payload.kind not in skills.known():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown agent kind: {payload.kind!r} (known: {list(skills.known())})",
        )
    job = AgentJob(user_id=user.id, kind=payload.kind, input=payload.input)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("/{job_id}", response_model=AgentJobOut)
def get_job(
    job_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> AgentJob:
    job = session.get(AgentJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return job


@router.get("", response_model=list[AgentJobOut])
def list_jobs(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
    kind: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[AgentJob]:
    stmt = (
        select(AgentJob)
        .where(AgentJob.user_id == user.id)
        .order_by(AgentJob.created_at.desc())
        .limit(limit)
    )
    if kind is not None:
        stmt = stmt.where(AgentJob.kind == kind)
    return list(session.scalars(stmt).all())


@preview_router.get("/preview")
def generate_plan_preview(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
    week_start: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        ws = generate_plan.resolve_week_start(week_start)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return generate_plan.collect_inputs(session, user, ws)

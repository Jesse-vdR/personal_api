import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.intake import Intake
from app.models.user import User
from app.schemas.projects import ProjectOut

log = logging.getLogger("jesse-api.projects")
router = APIRouter(prefix="/v1/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> list[ProjectOut]:
    rows = session.execute(
        select(
            Intake.project_slug,
            func.count().label("entry_count"),
            func.max(Intake.ts).label("last_intake_at"),
        )
        .where(Intake.user_id == user.id, Intake.processed_at.is_not(None))
        .group_by(Intake.project_slug)
        .order_by(func.max(Intake.ts).desc())
    ).all()
    return [
        ProjectOut(slug=slug, entry_count=count, last_intake_at=last)
        for slug, count, last in rows
    ]

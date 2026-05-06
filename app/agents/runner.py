"""Generic Claude agent runner.

Each skill module under `app.agents.skills.<kind>` exposes
`run(session, user, input, *, anthropic_client, job_id) -> dict`. The
runner is the glue that picks a queued `agent_jobs` row, instantiates
the Anthropic client, dispatches to the skill, and persists output /
error back to the row. Skills own their own DB writes (e.g. inserting
a plans row) and return the structured output to be stored in
`agent_jobs.output`. Transactions: the skill stages writes via
`session.add` / `session.flush`; the runner commits on success or
rolls back on failure before recording the error.

TODO(BYOK): single ANTHROPIC_API_KEY for now, billed against Jesse's
account. When more users sign up, switch to per-user keys keyed off
`users.id` (likely a `user_credentials` table or env-shaped per-user
secret store).
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.agents import skills
from app.config import settings
from app.models.agent_job import AgentJob
from app.models.user import User

log = logging.getLogger("jesse-api.agents")


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required to run agent jobs")
    return Anthropic(api_key=settings.anthropic_api_key)


def process(session: Session, job_id: int) -> None:
    """Run the skill for the (already-claimed) job and finalise its row."""
    job = session.get(AgentJob, job_id)
    if job is None:
        log.warning("process: job_id=%s vanished", job_id)
        return

    user = session.get(User, job.user_id)
    if user is None:
        _fail(session, job_id, "user no longer exists")
        return

    try:
        skill = skills.get(job.kind)
    except KeyError:
        _fail(session, job_id, f"unknown skill kind: {job.kind!r}")
        return

    try:
        client = _client()
        output = skill.run(
            session, user, job.input, anthropic_client=client, job_id=job.id
        )
    except Exception:
        _fail(session, job_id, traceback.format_exc())
        return

    job.status = "succeeded"
    job.output = output
    job.finished_at = datetime.now(timezone.utc)
    session.commit()
    log.info("agent job succeeded id=%s kind=%s", job.id, job.kind)


def _fail(session: Session, job_id: int, message: str) -> None:
    session.rollback()
    job = session.get(AgentJob, job_id)
    if job is None:
        return
    log.warning(
        "agent job failed id=%s kind=%s: %s",
        job.id,
        job.kind,
        message.strip().splitlines()[-1] if message.strip() else "(empty)",
    )
    job.status = "failed"
    job.error = message
    job.finished_at = datetime.now(timezone.utc)
    session.commit()

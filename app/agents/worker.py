"""Polling worker for agent_jobs.

Single-process, single-threaded. Polls every POLL_INTERVAL_S seconds
for `queued` rows, claims one at a time via SELECT ... FOR UPDATE
SKIP LOCKED, and dispatches to runner.process. Runs as the
`jesse-agent-worker.service` systemd unit on jesse-prod.

Concurrency story (single user): one job at a time. When a second
user shows up we'll either bump worker count or spin up per-skill
workers — concurrency knobs aren't worth designing today.
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import text

from app.agents import runner
from app.config import settings
from app.db import SessionLocal

POLL_INTERVAL_S = 2.0

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("jesse-agent-worker")

_running = True


def _stop(signum: int, frame: object) -> None:  # noqa: ARG001
    global _running
    log.info("received signal %s, draining", signum)
    _running = False


def _claim_one() -> int | None:
    """Atomically pick the oldest queued job and mark it running."""
    with SessionLocal() as session, session.begin():
        row = session.execute(
            text(
                "SELECT id FROM agent_jobs "
                "WHERE status = 'queued' "
                "ORDER BY created_at ASC "
                "LIMIT 1 "
                "FOR UPDATE SKIP LOCKED"
            )
        ).first()
        if row is None:
            return None
        session.execute(
            text(
                "UPDATE agent_jobs "
                "SET status = 'running', started_at = :now "
                "WHERE id = :id"
            ),
            {"id": row.id, "now": datetime.now(timezone.utc)},
        )
        return int(row.id)


def main() -> int:
    if not settings.anthropic_api_key:
        log.error("ANTHROPIC_API_KEY not set; refusing to start")
        return 1

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    log.info("jesse-agent-worker starting poll_interval=%.1fs", POLL_INTERVAL_S)

    while _running:
        try:
            job_id = _claim_one()
        except Exception:
            log.exception("claim failed, backing off")
            time.sleep(POLL_INTERVAL_S * 5)
            continue

        if job_id is None:
            time.sleep(POLL_INTERVAL_S)
            continue

        log.info("claimed agent job id=%s", job_id)
        with SessionLocal() as session:
            try:
                runner.process(session, job_id)
            except Exception:
                log.exception("runner crashed for job_id=%s", job_id)
                session.rollback()

    log.info("jesse-agent-worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

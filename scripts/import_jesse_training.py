#!/usr/bin/env python3
"""One-shot import: Jesse's training markdown/JSON -> Postgres tables.

Reads the data hub at <DATA_DIR> (default: /home/ubuntu/Jesse/training,
override with --data-dir) and lands rows in the user_id=1 (Jesse) slot
of:
    tracks            from tracks.json
    goals             from goals.json
    user_profile      from profile.md       -> body={"markdown": "..."}
    long_term_plan    from long_term.md     -> body={"markdown": "..."}
    plans             from plan.json        -> latest weekly plan

Idempotent: rerunning produces no duplicates and overwrites existing
rows in place (so editing a markdown file and re-importing is the
intended update path during the dual-write window). After Jesse#14 the
PWA writes here directly and this script becomes obsolete.

Notes
-----
- goals.json's `acceptance` field is dropped (the table has no column
  for it). Stored copy is the markdown long-term plan.
- The latest weekly plan is taken from the JSON form (`plan.json`),
  not parsed out of weekly markdown. `plan_to_json.py` already does
  the markdown->JSON conversion; we trust that output.

Usage
-----
    python scripts/import_jesse_training.py [--data-dir PATH] [--user-id N]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.goal import Goal  # noqa: E402
from app.models.long_term_plan import LongTermPlan  # noqa: E402
from app.models.plan import Plan  # noqa: E402
from app.models.track import Track  # noqa: E402
from app.models.user_profile import UserProfile  # noqa: E402
from app.models.user import User  # noqa: E402

DEFAULT_DATA_DIR = Path("/home/ubuntu/Jesse/training")
DEFAULT_USER_ID = 1


def _import_tracks(session, user_id: int, data_dir: Path) -> tuple[int, int]:
    path = data_dir / "tracks.json"
    raw = json.loads(path.read_text())
    inserted = updated = 0
    for entry in raw["tracks"]:
        slug = entry["id"]
        existing = session.scalar(
            select(Track).where(Track.user_id == user_id, Track.slug == slug)
        )
        if existing is None:
            session.add(
                Track(
                    user_id=user_id,
                    slug=slug,
                    display=entry["display"],
                    stages=entry["stages"],
                )
            )
            inserted += 1
        else:
            existing.display = entry["display"]
            existing.stages = entry["stages"]
            updated += 1
    return inserted, updated


def _import_goals(session, user_id: int, data_dir: Path) -> tuple[int, int]:
    path = data_dir / "goals.json"
    raw = json.loads(path.read_text())
    inserted = updated = 0
    for entry in raw["goals"]:
        slug = entry["id"]
        fields = {
            "display": entry["display"],
            "start_date": _parse_date(entry.get("start_date")),
            "deadline": _parse_date(entry.get("deadline")),
            "status": entry.get("status", "active"),
            "tracks": entry["tracks"],
        }
        existing = session.scalar(
            select(Goal).where(Goal.user_id == user_id, Goal.slug == slug)
        )
        if existing is None:
            session.add(Goal(user_id=user_id, slug=slug, **fields))
            inserted += 1
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
    return inserted, updated


def _import_profile(session, user_id: int, data_dir: Path) -> str:
    path = data_dir / "profile.md"
    body = {"markdown": path.read_text()}
    existing = session.get(UserProfile, user_id)
    if existing is None:
        session.add(UserProfile(user_id=user_id, body=body))
        return "inserted"
    existing.body = body
    return "updated"


def _import_long_term(session, user_id: int, data_dir: Path) -> str:
    path = data_dir / "long_term.md"
    body = {"markdown": path.read_text()}
    existing = session.get(LongTermPlan, user_id)
    if existing is None:
        session.add(LongTermPlan(user_id=user_id, body=body))
        return "inserted"
    existing.body = body
    return "updated"


def _import_plan(session, user_id: int, data_dir: Path) -> str:
    path = data_dir / "plan.json"
    if not path.exists():
        return "skipped (plan.json missing)"
    raw = json.loads(path.read_text())
    week_start = _parse_date(raw["week_start"])
    if week_start is None:
        return "skipped (no week_start in plan.json)"
    existing = session.scalar(
        select(Plan).where(Plan.user_id == user_id, Plan.week_start == week_start)
    )
    if existing is None:
        session.add(
            Plan(
                user_id=user_id,
                week_start=week_start,
                body=raw,
                generated_by="manual",
            )
        )
        return f"inserted (week_start={week_start.isoformat()})"
    existing.body = raw
    existing.generated_by = "manual"
    return f"updated (week_start={week_start.isoformat()})"


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--user-id", type=int, default=DEFAULT_USER_ID)
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        print(f"data dir not found: {args.data_dir}", file=sys.stderr)
        return 2

    started = datetime.now(timezone.utc)
    with SessionLocal() as session:
        if session.get(User, args.user_id) is None:
            print(f"user_id={args.user_id} not found in users table", file=sys.stderr)
            return 2

        tracks_in, tracks_up = _import_tracks(session, args.user_id, args.data_dir)
        goals_in, goals_up = _import_goals(session, args.user_id, args.data_dir)
        profile_status = _import_profile(session, args.user_id, args.data_dir)
        long_term_status = _import_long_term(session, args.user_id, args.data_dir)
        plan_status = _import_plan(session, args.user_id, args.data_dir)
        session.commit()

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(
        f"done in {elapsed:.2f}s  "
        f"tracks: +{tracks_in}/~{tracks_up}  "
        f"goals: +{goals_in}/~{goals_up}  "
        f"profile: {profile_status}  "
        f"long_term: {long_term_status}  "
        f"plan: {plan_status}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

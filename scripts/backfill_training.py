#!/usr/bin/env python3
"""One-shot backfill: events.jsonl -> training_events table.

Idempotent via uq_training_events_natural — re-runs against the same file
make no changes. After this runs successfully the GitHub jsonl mirror is
no longer the source of truth (issue #9 phase 3.4).

Usage:
    python scripts/backfill_training.py [PATH_TO_EVENTS_JSONL]

Default path: /home/ubuntu/Jesse/training/log/events.jsonl
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Run-from-anywhere: prepend repo root so `import app.*` works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.db import engine  # noqa: E402
from app.models.training import TrainingEvent  # noqa: E402

DEFAULT_PATH = Path("/home/ubuntu/Jesse/training/log/events.jsonl")


def _parse_ts(raw: str) -> datetime:
    # Source uses ISO 8601 with `Z`; fromisoformat tolerates `+00:00` only
    # on older pythons, so swap.
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2

    rows: list[dict] = []
    skipped_malformed = 0
    with path.open() as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rows.append(
                    {
                        "ts": _parse_ts(obj["ts"]),
                        "local_date": obj["local_date"],
                        "exercise": obj["exercise"],
                        "kind": obj["kind"],
                        "reps": obj.get("reps"),
                        "schema_v": obj.get("v", 1),
                    }
                )
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                skipped_malformed += 1
                print(f"  skip line {line_no}: {exc}", file=sys.stderr)

    if not rows:
        print("no rows to insert", file=sys.stderr)
        return 1

    stmt = pg_insert(TrainingEvent.__table__).values(rows)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_training_events_natural")

    with engine.begin() as conn:
        result = conn.execute(stmt)

    print(
        f"file={path}  parsed={len(rows)}  inserted={result.rowcount}  "
        f"already_present={len(rows) - result.rowcount}  malformed_skipped={skipped_malformed}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

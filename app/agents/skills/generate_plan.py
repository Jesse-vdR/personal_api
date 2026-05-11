"""generate_plan — first agent skill.

Input: {"week_start": "YYYY-MM-DD"} (defaults to next Monday in user TZ).
Reads per-user profile, long-term plan, tracks, goals, and the last 4
weeks of training_events. Calls Claude Opus 4.7 via a forced tool call
(`submit_plan`) so the response is a typed plan body matching the shape
of training/plan.json. Inserts a `plans` row stamped with
`generated_by = f'agent:{job_id}'`.

Long-lived context (profile, long_term, tracks) is cached via a single
ephemeral cache breakpoint on the system prompt. Volatile inputs
(goals, recent events, week_start) live in the user message after the
breakpoint so the cache holds across runs.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.long_term_plan import LongTermPlan
from app.models.plan import Plan
from app.models.track import Track
from app.models.training import TrainingEvent
from app.models.user import User
from app.models.user_profile import UserProfile

NAME = "generate_plan"
MODEL = "claude-opus-4-7"

_SUBMIT_PLAN_TOOL: dict[str, Any] = {
    "name": "submit_plan",
    "description": (
        "Submit the generated weekly training plan. Top-level object: "
        "`week_start` (YYYY-MM-DD, must equal the requested Monday) and "
        "`days`, an array of exactly 7 day objects in chronological order "
        "Mon..Sun. Each day has `date` (YYYY-MM-DD) and `exercises`, an "
        "ordered list of exercises with slug, display, unit "
        "('reps' | 'duration_s' | 'walks'), target_total, per_set, sets. "
        "target_total must equal per_set * sets. The runner reshapes the "
        "array into training/plan.json's date-keyed map before storage."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "week_start": {
                "type": "string",
                "description": "Monday of the planned week, YYYY-MM-DD.",
            },
            "days": {
                "type": "array",
                "description": (
                    "Exactly 7 day objects, one per day Mon..Sun, in "
                    "chronological order starting at week_start."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "YYYY-MM-DD for this day.",
                        },
                        "exercises": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "slug": {"type": "string"},
                                    "display": {"type": "string"},
                                    "unit": {
                                        "type": "string",
                                        "enum": ["reps", "duration_s", "walks"],
                                    },
                                    "target_total": {"type": "integer"},
                                    "per_set": {"type": "integer"},
                                    "sets": {"type": "integer"},
                                },
                                "required": [
                                    "slug",
                                    "display",
                                    "unit",
                                    "target_total",
                                    "per_set",
                                    "sets",
                                ],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["date", "exercises"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["week_start", "days"],
        "additionalProperties": False,
    },
}

_SYSTEM_INTRO = (
    "You are a calisthenics + handstand + running coach generating a "
    "Monday-through-Sunday training plan. Daily volume blends the user's "
    "active goals via Greasing-the-Groove style microsets. Honour every "
    "constraint in the long-term plan (elbow restrictions, inversion "
    "tolerance, A-priority of the current block, garden/work load). "
    "Recent training_events show what the user actually did — calibrate "
    "next week's volume so it nudges progression without overshooting "
    "stages. Output via the submit_plan tool; do not reply in prose."
)


def run(
    session: Session,
    user: User,
    input: dict[str, Any],
    *,
    anthropic_client: Anthropic,
    job_id: int,
) -> dict[str, Any]:
    week_start = _resolve_week_start(input.get("week_start"))

    profile = session.get(UserProfile, user.id)
    long_term = session.get(LongTermPlan, user.id)
    tracks = list(
        session.scalars(
            select(Track).where(Track.user_id == user.id).order_by(Track.slug)
        ).all()
    )
    goals = list(
        session.scalars(
            select(Goal).where(Goal.user_id == user.id).order_by(Goal.slug)
        ).all()
    )
    events = _recent_events(session, user.id, week_start)

    system_blocks = _build_system_blocks(profile, long_term, tracks)
    user_message = _build_user_message(week_start, goals, events)

    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system_blocks,
        tools=[_SUBMIT_PLAN_TOOL],
        tool_choice={"type": "tool", "name": "submit_plan"},
        messages=[{"role": "user", "content": user_message}],
    )

    body = _extract_tool_input(response)
    if body.get("week_start") != week_start.isoformat():
        raise RuntimeError(
            f"agent returned week_start={body.get('week_start')!r}, "
            f"expected {week_start.isoformat()!r}"
        )
    body["days"] = _days_array_to_map(body.get("days"), week_start)

    plan = Plan(
        user_id=user.id,
        week_start=week_start,
        body=body,
        generated_by=f"agent:{job_id}",
    )
    session.add(plan)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise RuntimeError(
            f"plan already exists for week_start={week_start.isoformat()}"
        ) from exc

    return {
        "plan_id": plan.id,
        "week_start": week_start.isoformat(),
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_creation_input_tokens": response.usage.cache_creation_input_tokens,
            "cache_read_input_tokens": response.usage.cache_read_input_tokens,
        },
    }


def _resolve_week_start(raw: Any) -> date:
    if raw:
        parsed = date.fromisoformat(str(raw))
        if parsed.weekday() != 0:
            raise ValueError(f"week_start must be a Monday, got {parsed} ({parsed.strftime('%A')})")
        return parsed
    today = datetime.now(timezone.utc).date()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def _recent_events(session: Session, user_id: int, week_start: date) -> list[dict[str, Any]]:
    since = week_start - timedelta(days=28)
    rows = session.scalars(
        select(TrainingEvent)
        .where(TrainingEvent.user_id == user_id, TrainingEvent.local_date >= since)
        .order_by(TrainingEvent.ts.asc())
    ).all()
    return [
        {
            "ts": row.ts.isoformat(),
            "local_date": row.local_date.isoformat(),
            "exercise": row.exercise,
            "kind": row.kind,
            "reps": row.reps,
            "duration_s": row.duration_s,
            "track": row.track,
            "stage": row.stage,
            "note": row.note,
        }
        for row in rows
    ]


def _build_system_blocks(
    profile: UserProfile | None,
    long_term: LongTermPlan | None,
    tracks: list[Track],
) -> list[dict[str, Any]]:
    sections: list[str] = [_SYSTEM_INTRO, ""]

    sections.append("## User profile")
    sections.append(_markdown_or_json(profile.body) if profile else "_(none on file)_")
    sections.append("")

    sections.append("## Long-term plan")
    sections.append(
        _markdown_or_json(long_term.body) if long_term else "_(none on file)_"
    )
    sections.append("")

    sections.append("## Tracks (progression ladders)")
    sections.append(
        json.dumps(
            [
                {"slug": t.slug, "display": t.display, "stages": t.stages}
                for t in tracks
            ],
            sort_keys=True,
            indent=2,
        )
    )

    text = "\n".join(sections)
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _build_user_message(
    week_start: date, goals: list[Goal], events: list[dict[str, Any]]
) -> str:
    sections: list[str] = []
    sections.append(f"Generate the weekly plan for week_start = {week_start.isoformat()} (Monday).")
    sections.append("")
    sections.append("## Active goals")
    sections.append(
        json.dumps(
            [
                {
                    "slug": g.slug,
                    "display": g.display,
                    "start_date": g.start_date.isoformat() if g.start_date else None,
                    "deadline": g.deadline.isoformat() if g.deadline else None,
                    "status": g.status,
                    "tracks": g.tracks,
                }
                for g in goals
            ],
            sort_keys=True,
            indent=2,
        )
    )
    sections.append("")
    sections.append("## Training events — last 4 weeks")
    sections.append(json.dumps(events, sort_keys=True, indent=2))
    sections.append("")
    sections.append("Now call submit_plan with the full Mon..Sun schedule.")
    return "\n".join(sections)


def _markdown_or_json(body: dict[str, Any]) -> str:
    if isinstance(body, dict) and isinstance(body.get("markdown"), str):
        return body["markdown"]
    return json.dumps(body, sort_keys=True, indent=2)


def _days_array_to_map(
    days: Any, week_start: date
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(days, list) or len(days) != 7:
        raise RuntimeError(
            f"agent returned days={type(days).__name__} len="
            f"{len(days) if isinstance(days, list) else 'n/a'}, expected list of 7"
        )
    expected = [
        (week_start + timedelta(days=i)).isoformat() for i in range(7)
    ]
    out: dict[str, list[dict[str, Any]]] = {}
    for entry, want in zip(days, expected):
        got = entry.get("date")
        if got != want:
            raise RuntimeError(
                f"agent returned day date={got!r}, expected {want!r}"
            )
        out[want] = list(entry.get("exercises") or [])
    return out


def _extract_tool_input(response: Any) -> dict[str, Any]:
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_plan":
            return dict(block.input)
    raise RuntimeError(
        f"agent did not call submit_plan (stop_reason={response.stop_reason})"
    )

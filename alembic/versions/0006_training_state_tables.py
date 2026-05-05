"""training state tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-05

Moves training subsystem state out of markdown/JSON in `Jesse-vdR/Jesse`
into Postgres so the system is standalone (Jesse#12). Adds:

  - tracks            per-user progression ladders (T1..T6 today)
  - goals             per-user anchor goals + weighted track contributions
  - plans             per-user weekly plan (week_start DATE), JSONB body
  - user_profile      per-user profile (replaces training/profile.md)
  - long_term_plan    per-user long-term plan (replaces training/long_term.md)

Also extends `training_events` for the single-table sparse approach
(see docs/website-architecture.md): adds `track`, `stage`, `note`
nullable columns so the same table can hold `set` / `hold` rows
alongside `stage_pass` / `run` / `session` rows. `exercise` becomes
nullable since `run` and `session` events have no exercise binding.

`kind` is plain text (no DB enum), so adding new kinds (`stage_pass`,
`run`, `session`) needs no schema change beyond the new sparse columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display", sa.String(length=255), nullable=False),
        sa.Column("stages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_tracks_user_id_users"),
        sa.UniqueConstraint("user_id", "slug", name="uq_tracks_user_slug"),
    )
    op.create_index("ix_tracks_user_id", "tracks", ["user_id"], unique=False)

    op.create_table(
        "goals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), server_default="active", nullable=False
        ),
        sa.Column("tracks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_goals_user_id_users"),
        sa.UniqueConstraint("user_id", "slug", name="uq_goals_user_slug"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"], unique=False)

    op.create_table(
        "plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "generated_by",
            sa.String(length=64),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_plans_user_id_users"),
        sa.UniqueConstraint("user_id", "week_start", name="uq_plans_user_week_start"),
    )
    op.create_index("ix_plans_user_id", "plans", ["user_id"], unique=False)
    op.create_index(
        "ix_plans_user_week_start_desc", "plans", ["user_id", sa.text("week_start DESC")]
    )

    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_profile_user_id_users"
        ),
    )

    op.create_table(
        "long_term_plan",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_long_term_plan_user_id_users"
        ),
    )

    op.alter_column("training_events", "exercise", existing_type=sa.String(length=64), nullable=True)
    op.add_column(
        "training_events", sa.Column("track", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "training_events", sa.Column("stage", sa.SmallInteger(), nullable=True)
    )
    op.add_column("training_events", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("training_events", "note")
    op.drop_column("training_events", "stage")
    op.drop_column("training_events", "track")
    op.execute("UPDATE training_events SET exercise = '' WHERE exercise IS NULL")
    op.alter_column(
        "training_events", "exercise", existing_type=sa.String(length=64), nullable=False
    )

    op.drop_table("long_term_plan")
    op.drop_table("user_profile")
    op.drop_index("ix_plans_user_week_start_desc", table_name="plans")
    op.drop_index("ix_plans_user_id", table_name="plans")
    op.drop_table("plans")
    op.drop_index("ix_goals_user_id", table_name="goals")
    op.drop_table("goals")
    op.drop_index("ix_tracks_user_id", table_name="tracks")
    op.drop_table("tracks")

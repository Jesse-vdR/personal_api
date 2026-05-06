"""agent_jobs queue

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-06

Generic queue that backs the per-skill Claude agent runner (Jesse#13).
API endpoints enqueue rows; a worker process claims them via
`SELECT ... FOR UPDATE SKIP LOCKED`, runs the SDK, writes results
back. status in {queued, running, succeeded, failed}.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="queued"
        ),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_jobs_user_id_users"
        ),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed')",
            name="ck_agent_jobs_status",
        ),
    )
    op.create_index("ix_agent_jobs_user_id", "agent_jobs", ["user_id"])
    op.create_index(
        "ix_agent_jobs_user_kind_created",
        "agent_jobs",
        ["user_id", "kind", sa.text("created_at DESC")],
    )
    # Partial index makes the worker's queue scan touch only pending rows.
    op.create_index(
        "ix_agent_jobs_queued",
        "agent_jobs",
        ["created_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )


def downgrade() -> None:
    op.drop_index("ix_agent_jobs_queued", table_name="agent_jobs")
    op.drop_index("ix_agent_jobs_user_kind_created", table_name="agent_jobs")
    op.drop_index("ix_agent_jobs_user_id", table_name="agent_jobs")
    op.drop_table("agent_jobs")

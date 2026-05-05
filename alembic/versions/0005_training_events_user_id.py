"""training_events.user_id

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-05

Adds user_id FK to training_events. Existing rows backfill to user_id=1
(the seed Jesse user from migration 0004). Unique constraint expands to
include user_id so two users can record identical (ts, exercise, kind)
events independently.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "training_events", sa.Column("user_id", sa.Integer(), nullable=True)
    )
    op.execute("UPDATE training_events SET user_id = 1 WHERE user_id IS NULL")
    op.alter_column("training_events", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_training_events_user_id_users",
        "training_events",
        "users",
        ["user_id"],
        ["id"],
    )
    op.drop_constraint("uq_training_events_natural", "training_events", type_="unique")
    op.create_unique_constraint(
        "uq_training_events_natural",
        "training_events",
        ["user_id", "ts", "exercise", "kind"],
    )
    op.create_index(
        "ix_training_events_user_id", "training_events", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_training_events_user_id", table_name="training_events")
    op.drop_constraint("uq_training_events_natural", "training_events", type_="unique")
    op.create_unique_constraint(
        "uq_training_events_natural",
        "training_events",
        ["ts", "exercise", "kind"],
    )
    op.drop_constraint(
        "fk_training_events_user_id_users", "training_events", type_="foreignkey"
    )
    op.drop_column("training_events", "user_id")

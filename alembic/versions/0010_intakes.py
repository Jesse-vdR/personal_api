"""intakes

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-06

Adds the intake queue table for inspiration_app (Jesse-vdR/inspiration_app#3).

Each row is one piece of incoming content — text or text+media — tagged
with a project_slug parsed from the caption. The agent runner
(inspiration_app#5) polls `WHERE processed_at IS NULL` and turns each
row into HTML edits in inspiration_app.

Media attachments reuse the existing `media` table (added in 0009).
The path namespace `<user_id>/inspiration/<yyyy-mm>/<sha>.ext` keeps
inspiration blobs separable from journal blobs on disk.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intakes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_slug", sa.Text(), server_default="inbox", nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.Text(), server_default="telegram", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_intakes_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media.id"], name="fk_intakes_media_id_media", ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_intakes_unprocessed",
        "intakes",
        ["user_id", "ts"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index(
        "ix_intakes_user_project_ts",
        "intakes",
        ["user_id", "project_slug", sa.text("ts DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_intakes_user_project_ts", table_name="intakes")
    op.drop_index("ix_intakes_unprocessed", table_name="intakes")
    op.drop_table("intakes")

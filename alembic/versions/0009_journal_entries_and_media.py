"""journal_entries + media

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-06

Adds the journal subsystem tables per docs/journal-app-spec.md (Jesse#31):

  - media             per-user file blobs on disk; unique(user_id, sha256)
  - journal_entries   per-user dated entries; one row per write, grouped
                      to a "day document" by local_date in the read path

`media` is created first so `journal_entries.media_id` can FK it. Audio
blobs are written to /var/lib/jesse/media/<user_id>/journal/<yyyy-mm>/<sha>.ext
by the CRUD endpoints (Jesse#33); this migration only creates the
metadata rows that point at them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_media_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "sha256", name="uq_media_user_sha256"),
    )
    op.create_index("ix_media_user_id", "media", ["user_id"], unique=False)

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.Text(), server_default="pwa", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_journal_entries_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media.id"], name="fk_journal_entries_media_id_media", ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_journal_entries_user_local_date_desc",
        "journal_entries",
        ["user_id", sa.text("local_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_journal_entries_user_local_date_desc", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_media_user_id", table_name="media")
    op.drop_table("media")

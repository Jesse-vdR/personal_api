"""users

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-05

Creates the users table and seeds Jesse as id=1 with a placeholder
google_sub. The placeholder is claimed (rewritten to the real google_sub)
the first time Jesse signs in via Google with the matching email — see
app/routers/auth.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_EMAIL = "jesse.vanderiet@gmail.com"
SEED_SUB = f"migration-seed:{SEED_EMAIL}"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )

    op.execute(
        sa.text(
            "INSERT INTO users (google_sub, email, name) "
            "VALUES (:sub, :email, :name)"
        )
        .bindparams(sub=SEED_SUB, email=SEED_EMAIL, name="Jesse")
    )


def downgrade() -> None:
    op.drop_table("users")

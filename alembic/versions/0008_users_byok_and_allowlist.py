"""users: display_name + byok columns + allowlist shape

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-06

Reshapes `users` to match docs/journal-app-spec.md:
- rename `name` -> `display_name`
- drop `avatar_url`
- add nullable `openai_api_key`, `anthropic_api_key` (V1 unused; future BYOK)
- make `google_sub` nullable so seeded rows can be allowlist entries with
  no Google account bound yet (callback fills it on first sign-in)
- add unique constraint on `email`
- clear placeholder `migration-seed:*` google_sub values left over from 0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "google_sub", existing_type=sa.String(length=255), nullable=True)
    op.execute("UPDATE users SET google_sub = NULL WHERE google_sub LIKE 'migration-seed:%'")

    op.alter_column("users", "name", new_column_name="display_name")
    op.drop_column("users", "avatar_url")

    op.add_column("users", sa.Column("openai_api_key", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("anthropic_api_key", sa.Text(), nullable=True))

    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "anthropic_api_key")
    op.drop_column("users", "openai_api_key")
    op.add_column("users", sa.Column("avatar_url", sa.String(length=1024), nullable=True))
    op.alter_column("users", "display_name", new_column_name="name")
    op.execute(
        "UPDATE users SET google_sub = 'migration-seed:' || email "
        "WHERE google_sub IS NULL"
    )
    op.alter_column("users", "google_sub", existing_type=sa.String(length=255), nullable=False)

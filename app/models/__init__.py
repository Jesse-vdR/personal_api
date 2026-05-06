# Import every model module here so Alembic's autogenerate sees them all.
from app.models import (  # noqa: F401
    agent_job,
    goal,
    journal_entry,
    long_term_plan,
    media,
    plan,
    track,
    training,
    user,
    user_profile,
)

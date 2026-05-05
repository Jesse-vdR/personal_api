# Import every model module here so Alembic's autogenerate sees them all.
from app.models import (  # noqa: F401
    goal,
    long_term_plan,
    plan,
    track,
    training,
    user,
    user_profile,
)

from importlib import import_module
from types import ModuleType

# Adding a skill: create app/agents/skills/<name>.py exposing `NAME` and
# `run(session, user, input, *, anthropic_client) -> dict`, then add the
# slug here.
_REGISTERED: tuple[str, ...] = ("generate_plan",)


def get(kind: str) -> ModuleType:
    if kind not in _REGISTERED:
        raise KeyError(kind)
    return import_module(f"app.agents.skills.{kind}")


def known() -> tuple[str, ...]:
    return _REGISTERED

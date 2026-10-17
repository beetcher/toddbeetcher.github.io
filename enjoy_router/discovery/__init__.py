"""Discovery: the portable AI finder core (plan claude/discovery-module-plan.md). Product-blind: standard library and jsonschema only.

The product builds a Discovery engine from its own finders and ports, and keeps the one instance with configure().
Unconfigured, every call is refused as mode_off.
"""
from __future__ import annotations

from .contract import CONTRACT_VERSION, Reply
from .modes import resolve_mode
from .pipeline import Discovery

_engine = None


def configure(engine) -> None:
    global _engine
    _engine = engine


def is_configured() -> bool:
    return _engine is not None


def engine():
    return _engine


def plan(request, by):
    return _engine.plan(request, by) if _engine else Reply(False, "mode_off", "Discovery is not set up.")

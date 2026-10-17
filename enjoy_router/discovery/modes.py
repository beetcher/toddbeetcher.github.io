"""The run mode (plan section 8.3; rule D-5). Product-blind.

off      nothing runs.
dry_run  the prompts are built and the cost is estimated; no provider is called and nothing is spent.
live     the AI is called.
The mode comes from the environment, never from the Console, so a mistake in the Console cannot turn live calls on.
"""
from __future__ import annotations

from .contract import MODES


def resolve_mode(environ, var: str = "DISCOVERY_MODE") -> str:
    """The value of `var` when it is one of the three modes, else off. Unset or unknown means off (fail closed)."""
    raw = (environ.get(var) or "").strip().lower()
    return raw if raw in MODES else "off"

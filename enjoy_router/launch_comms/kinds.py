"""The message kinds LAUNCH registers: request_received (the receipt) and placement_confirmation (you are scheduled).

The kinds come from the schemas folder (registry.json `message_kinds`); this module only loads them once.
"""
from __future__ import annotations

from comms.kinds import KindRegistry
from crud.schema_kit import find_schema_dir

_registry = None


def registry() -> KindRegistry:
    global _registry
    if _registry is None:
        _registry = KindRegistry().load(find_schema_dir())
    return _registry

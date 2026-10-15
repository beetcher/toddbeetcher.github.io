"""The CMS (Communication Management System). One door: notify and notify_many (CMS_GUIDE.md, rule R-2).

    import comms
    comms.configure(comms.Comms(kinds=..., directory=..., templates=..., log=..., settings=..., channels=[...], mode="live"))
    comms.notify("placement_confirmation", {"type": "individual", "individual_id": id}, facts, by="user:admin",
                 trigger="automatic", refs={"attendance_id": att_id}, audience="student")

Until configured (tests, local runs) the CMS behaves as mode off: every call returns skipped / cms_off and nothing is sent.
The core imports nothing from LAUNCH (R-1): the product supplies the ports (comms/ports.py) at startup.
"""
from __future__ import annotations

from typing import Optional

from .contract import CONTRACT_VERSION, Contact, Result
from .kinds import KindRegistry
from .pipeline import Comms

_instance: Optional[Comms] = None


def configure(instance: Optional[Comms]) -> None:
    global _instance
    _instance = instance


def is_configured() -> bool:
    """True when a CMS instance has been supplied (the product turns it on at startup; tests and local runs leave it off)."""
    return _instance is not None


def notify(kind, recipient, context, by, trigger, refs=None, audience=None, suppress=None, dedupe_key=None) -> Result:
    if _instance is None:
        return Result("skipped", "none", "cms_off", None)
    return _instance.notify(kind, recipient, context, by, trigger, refs, audience, suppress, dedupe_key)


def notify_many(items, time_budget_s) -> list:
    if _instance is None:
        return [Result("skipped", "none", "cms_off", None) for _ in items]
    return _instance.notify_many(items, time_budget_s)


__all__ = ["CONTRACT_VERSION", "Comms", "Contact", "KindRegistry", "Result", "configure", "is_configured", "notify", "notify_many"]

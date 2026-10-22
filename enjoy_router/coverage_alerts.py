"""Sends the urgent "no trainer" notice (P-83) after a private request is saved from a ZIP no active region holds.

    send(store, doc, event, stamp)    event: "new" (just created) or "changed" (an edit turned it urgent)

The people told come from launch_comms.coverage_recipients; one message each, the Inspector's without any private data. A message problem
never changes the caller's result (CMS rules R-3, R-4). Returns the statuses, for tests; callers ignore it.
"""
from __future__ import annotations

import logging

import comms
from launch_comms import coverage_context as CC
from launch_comms import coverage_recipients as CR

log = logging.getLogger("enjoy_router")
BUDGET_SECONDS = 25
_people_store = None   # () -> the ACCESS store (people and roles). The registration doors hold the registration store, which has no people.


def configure(provider) -> None:
    """main.py: tell this module where the people live. Tests leave it unset and the store they pass is used."""
    global _people_store
    _people_store = provider


def send(store, doc: dict, event: str, stamp: str) -> list:
    if not comms.is_configured():
        return []
    try:
        calls = [CC.alert_call(r, doc, event, stamp) for r in CR.recipients(_people_store() if _people_store else store, doc.get("coverage_state_code"))]
        results = comms.notify_many(calls, BUDGET_SECONDS)
        log.info("no_trainer_alert id=%s event=%s n=%d", doc.get("id"), event, len(results))
        return [(r.status, r.reason) for r in results]
    except Exception as exc:
        log.error("no_trainer_alert id=%s code=notify_failed exception=%s", doc.get("id"), type(exc).__name__)
        return []

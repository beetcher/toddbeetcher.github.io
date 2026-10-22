"""The daily reminder about requests still waiting for a trainer (P-83), and Send reminders now.

    run(store, now, manual=False, by="system:coverage") -> {"waiting": n, "people": n, "sent": n, "not_sent": n}

Every request that is still waiting (urgent, not handled, no active region holds its ZIP yet) is looked up once. Each person who is told about
such requests (launch_comms.coverage_recipients.people) gets ONE message listing the towns and counts in THEIR reach: a super admin, an admin and
a Global Inspector see every state; a state owner sees only their own state(s). The text holds towns, states and counts only (no names or
contacts), so one copy is safe for the Inspector too. A person with nothing waiting in their reach gets nothing. The daily job and the hand button
use the same function; the automatic send is once per person per Mountain day (a hand send always goes). A message problem never stops the rest.
"""
from __future__ import annotations

import logging
from datetime import datetime

import comms
import request_coverage
from core import TIME_ZONE
from launch_comms import coverage_context as CC
from launch_comms import coverage_recipients as CR

log = logging.getLogger("enjoy_router")
BUDGET_SECONDS = 50
MAX_REQUESTS = 2000


def waiting_requests(store) -> list:
    """The requests still waiting for a trainer, oldest first."""
    areas = store.query("discovery_areas", [], limit=1000)
    found = store.query("registration_requests", [("coverage", "==", request_coverage.OPEN)], limit=MAX_REQUESTS)
    return sorted((d for d in found if request_coverage.is_open(areas, d)), key=lambda d: d.get("created_at", ""))


def _days_since(stamp, now) -> int:
    try:
        then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return 0
    return max(0, (now - then).days)


def run(store, now: datetime, manual: bool = False, by: str = "system:coverage") -> dict:
    waiting = waiting_requests(store)
    summary = {"waiting": len(waiting), "people": 0, "sent": 0, "not_sent": 0}
    if not waiting or not comms.is_configured():
        return summary
    day = now.astimezone(TIME_ZONE).date().isoformat()
    calls = []
    for person in CR.people(store):
        mine = [d for d in waiting if person["everywhere"] or d.get("coverage_state_code") in person["states"]]
        if not mine:
            continue
        calls.append(CC.digest_call(person, [CC.place_of(d) for d in mine], _days_since(mine[0].get("created_at"), now), day, manual=manual, by=by))
    summary["people"] = len(calls)
    for r in comms.notify_many(calls, BUDGET_SECONDS):
        if r.status == "sent":
            summary["sent"] += 1
        else:
            summary["not_sent"] += 1
    log.info("coverage_digest manual=%s waiting=%d people=%d sent=%d", manual, summary["waiting"], summary["people"], summary["sent"])
    return summary

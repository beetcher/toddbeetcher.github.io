"""The facts and the calls for the no_trainer_alert and no_trainer_digest kinds (P-83): a private request from a ZIP no active region holds.

Two copies of every alert exist. The STAFF copy (super admin, admin, state owner) names the requester and gives their contacts. The INSPECTOR
copy is built without any private fact at all (no name, email, phone, ZIP or confirmation number): the town and state only. The privacy is
in what the context holds, not in the wording, so a template edited later cannot leak what was never given to it.
"""
from __future__ import annotations

from launch_discovery import zip_table

from . import invite_context as IC

CONSOLE_URL = IC.CONSOLE_URL
UNKNOWN_TOWN, UNKNOWN_STATE = "an unlisted place", "US"
WHO_MASKED = "a request"
REASONS = {"new": "A new request just came in.", "changed": "A request changed its ZIP to a place with no trainer."}


def place_of(doc) -> tuple:
    """(town, state) of a request's ZIP, from the ZIP table; the state may also come from the coverage stamp."""
    z = (doc.get("postal_code") or "")[:5]
    town = zip_table.town_of(z) if z else None
    state = doc.get("coverage_state_code") or (zip_table.state_of(z) if z else None)
    return (town or UNKNOWN_TOWN), (state or UNKNOWN_STATE)


def first_name(person) -> str:
    return IC.first_name(person) if isinstance(person, dict) else "there"


def alert_facts(doc: dict, masked: bool, event: str, name: str) -> dict:
    town, state = place_of(doc)
    out = {"name": name, "who": WHO_MASKED if masked else " ".join((doc.get("first_name", ""), doc.get("last_name", ""))).strip() or WHO_MASKED,
           "town": town, "state_code": state, "reason": REASONS.get(event, REASONS["new"]), "console_url": CONSOLE_URL}
    if not masked:
        for src, dst in (("email", "requester_email"), ("phone", "requester_phone"), ("postal_code", "postal_code"), ("confirmation_number", "confirmation_number")):
            if doc.get(src):
                out[dst] = doc[src]
        out["requester_name"] = out["who"]
    return out


def alert_call(rec: dict, doc: dict, event: str, stamp: str, by: str = "system:coverage") -> dict:
    """Arguments for comms.notify for one recipient (a row of coverage_recipients.recipients)."""
    first = (rec.get("name") or "").split()
    return dict(kind="no_trainer_alert", recipient={"type": "adhoc", "name": rec.get("name") or "", "email": rec["email"]},
                context=alert_facts(doc, rec["masked"], event, first[0] if first else "there"), by=by, trigger="automatic",
                refs={"request_id": doc["id"]}, audience="inspector" if rec["masked"] else "staff",
                dedupe_key=f"no_trainer_alert:{doc['id']}:{rec['person_id']}:{stamp}"[:300])


def places_text(items) -> str:
    """'Hayward, WI (2); Denver, CO (1)' from [(town, state), ...], most first."""
    counts = {}
    for t, s in items:
        counts[(t, s)] = counts.get((t, s), 0) + 1
    return "; ".join(f"{t}, {s} ({n})" for (t, s), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][1], kv[0][0])))


def wait_words(days: int) -> str:
    return "less than a day" if days <= 0 else "1 day" if days == 1 else f"{days} days"


def digest_call(rec: dict, items: list, oldest_days: int, day: str, manual: bool = False, by: str = "system:coverage") -> dict:
    """items: [(town, state)] for this person's territory. The text carries places and counts only, so it is safe for every recipient."""
    first = (rec.get("name") or "").split()
    ctx = {"name": first[0] if first else "there", "count": str(len(items)), "places": places_text(items)[:1000],
           "longest_wait": wait_words(oldest_days), "console_url": CONSOLE_URL}
    return dict(kind="no_trainer_digest", recipient={"type": "adhoc", "name": rec.get("name") or "", "email": rec["email"]}, context=ctx, by=by,
                trigger="manual" if manual else "automatic", refs={}, audience="staff",
                dedupe_key=f"no_trainer_digest:{rec['person_id']}:{day}")

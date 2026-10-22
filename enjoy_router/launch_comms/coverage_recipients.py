"""Who is told when a private request has NO ACTIVE REGION (P-83, Todd 2026-10-22): the urgent case.

    recipients(store, state_code)  ->  [{"person_id", "email", "name", "reasons": [...], "masked": bool, ...}]   (one request)
    people(store)                  ->  everyone who may be told, with the states they own (the daily digest)

Always told: every active super admin, every active admin, every active Global Inspector; plus every active person holding a state-level
grant for the request's state (the "state owner": almost an admin for that state). One entry per person. Only people who can sign in count:
the person is switched on, not deleted, and holds a live, switched-on role. `masked` is True for an Inspector (a role holding
inspect_everything, who is view only and never sees a requester's email, phone or ZIP): their copy carries the town and state only.
"""
from __future__ import annotations

from access.authorize import INSPECT

ADMIN_KEY = "admin"


def _live(doc) -> bool:
    return isinstance(doc, dict) and not doc.get("deleted_at")


def people(store) -> list:
    """Everyone who may be told about requests with no active trainer: [{"person_id", "email", "name", "reasons", "masked", "everywhere", "states"}].
    `everywhere` is True for a super admin, an admin and an Inspector (told about every state); `states` are the states a person holds a state-level
    grant for. One entry per person; a person with neither is not listed."""
    out = []
    for p in store.query("access_persons", [], limit=1000):
        if not _live(p) or p.get("is_active") is not True or not p.get("email"):
            continue
        role = store.get("access_roles", p.get("role_id")) if p.get("role_id") else None
        if not _live(role) or role.get("is_active") is not True:
            continue
        sup = role.get("is_super_admin") is True
        inspector = (not sup) and INSPECT in (role.get("capabilities") or ())
        reasons = []
        if sup:
            reasons.append("super_admin")
        if role.get("key") == ADMIN_KEY:
            reasons.append("admin")
        if inspector:
            reasons.append("inspector")
        states = {g.get("state_code") for g in (p.get("grants") or ()) if g.get("kind") == "state" and g.get("state_code")}
        if states:
            reasons.append("state_owner")
        if reasons:
            out.append({"person_id": p["id"], "email": p["email"].strip().lower(), "name": p.get("display_name") or "", "reasons": reasons,
                        "masked": inspector, "everywhere": bool({"super_admin", "admin", "inspector"} & set(reasons)), "states": states})
    out.sort(key=lambda r: r["email"])
    return out


def recipients(store, state_code) -> list:
    """Who is told about ONE request in `state_code` (None when the ZIP's state is unknown): everyone who is told about every state, plus the
    state owners of that state."""
    out = []
    for r in people(store):
        if r["everywhere"] or (state_code and state_code in r["states"]):
            reasons = [x for x in r["reasons"] if x != "state_owner" or (state_code and state_code in r["states"])]
            out.append({**r, "reasons": reasons})
    return out

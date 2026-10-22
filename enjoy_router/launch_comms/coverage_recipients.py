"""Who is told when a private request has NO ACTIVE REGION (P-83, Todd 2026-10-22): the urgent case.

    recipients(store, state_code)  ->  [{"person_id", "email", "name", "reasons": [...], "masked": bool}]

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


def recipients(store, state_code) -> list:
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
        if state_code and any(g.get("kind") == "state" and g.get("state_code") == state_code for g in (p.get("grants") or ())):
            reasons.append("state_owner")
        if reasons:
            out.append({"person_id": p["id"], "email": p["email"].strip().lower(), "name": p.get("display_name") or "", "reasons": reasons, "masked": inspector})
    out.sort(key=lambda r: (r["email"]))
    return out

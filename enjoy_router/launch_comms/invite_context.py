"""The facts and the call for the access_invite kind (P-64): the email an invited person gets, with the Console link and the exact
Google address to sign in with.

The recipient is ad hoc (an access person is not an individual record): the Google email on the invitation, and the name when one was given.
Nothing secret goes in: no key, no token, only the public Console address.
"""
from __future__ import annotations

CONSOLE_URL = "https://beetcher.com/console/"
KEY_INVITER = "The LAUNCH team"          # the admin key has no person behind it
ADMIN_KEY_ACTOR = "user:admin"


def inviter_of(store, actor) -> str:
    """Who sent the invitation, in words: the inviter's name, else their Google email, else (admin key or unknown) the LAUNCH team."""
    if isinstance(actor, str) and actor.startswith("user:") and actor != ADMIN_KEY_ACTOR:
        p = store.get("access_persons", actor.split(":", 1)[1])
        if p is not None and "deleted_at" not in p:
            return (p.get("display_name") or p.get("email") or KEY_INVITER)
    return KEY_INVITER


def first_name(person) -> str:
    words = (person.get("display_name") or "").split()
    return words[0] if words else "there"


def facts(store, person: dict, actor: str):
    """-> (facts, None), or (None, reason) when the invitation cannot be described (no live role)."""
    role = store.get("access_roles", person.get("role_id")) if person.get("role_id") else None
    if role is None or "deleted_at" in role:
        return None, "role_not_found"
    out = {"name": first_name(person), "inviter": inviter_of(store, actor), "role_name": role["label"],
           "email": person["email"], "console_url": CONSOLE_URL}
    if role.get("description"):
        out["role_description"] = role["description"]
    return out, None


def call_for(store, person: dict, actor: str, manual: bool):
    """-> (arguments for comms.notify, None), or (None, reason). Automatic sends are once per person; a hand send always goes."""
    ctx, reason = facts(store, person, actor)
    if ctx is None:
        return None, reason
    recipient = {"type": "adhoc", "name": person.get("display_name") or "", "email": person["email"]}
    return dict(kind="access_invite", recipient=recipient, context=ctx, by=actor, trigger="manual" if manual else "automatic",
                refs={}, audience="invitee", dedupe_key=f"access_invite:{person['id']}"), None

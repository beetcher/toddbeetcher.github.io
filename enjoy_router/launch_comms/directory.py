"""RecipientDirectory for LAUNCH: turns {"type": "individual", individual_id} or {"type": "adhoc", ...} into a Contact (R-24).

The channel rule lives here and only here (individual.prefers_email): true is email, false is a text to the phone; when absent, the one
contact given is the preference, and when both are given it is email. A preference that points at a contact that is not there is ignored.
LAUNCH has no per-person mute yet, so Contact.muted is always False.
"""
from __future__ import annotations

from typing import Optional

from comms.contract import Contact
from crud import individuals_service as IS


def preferred_channel(email: Optional[str], phone: Optional[str], prefers_email: Optional[bool]) -> Optional[str]:
    if prefers_email is True and email:
        return "email"
    if prefers_email is False and phone:
        return "text"
    if email:
        return "email"
    if phone:
        return "text"
    return None


class IndividualDirectory:
    def __init__(self, store):
        self._store = store

    def lookup(self, recipient: dict) -> Optional[Contact]:
        if recipient.get("type") == "adhoc":
            email, phone = recipient.get("email"), recipient.get("phone")
            ch = preferred_channel(email, phone, None)
            return Contact(name=recipient.get("name") or "", email=email, phone=phone, preferred_channel=ch) if ch else None
        got = IS.get(self._store, recipient["individual_id"])
        if not got.ok or got.data.get("status") in ("erased", "merged"):
            return None
        p = got.data
        email, phone = p.get("email"), p.get("phone")
        return Contact(name=p.get("display_name") or p.get("given_name") or "", email=email, phone=phone,
                       backup_phone=p.get("backup_phone"), preferred_channel=preferred_channel(email, phone, p.get("prefers_email")),
                       individual_id=p["id"])

"""RecipientDirectory for LAUNCH: turns {"type": "individual", individual_id} or {"type": "adhoc", ...} into a Contact (R-24).

The channel rule lives here and only here (individual.prefers_email): true is email, false is a text to the phone; when absent, the one
contact given is the preference, and when both are given it is email. A preference that points at a contact that is not there is ignored.
An email address that is not a real address (for example a + typed after the domain) counts as no email, so nothing is
sent to it: with no other contact the notice is logged not_sent / no_contact. LAUNCH has no per-person mute yet, so Contact.muted is always False.
"""
from __future__ import annotations

from typing import Optional

from comms.contract import Contact
from crud import individuals_service as IS
from email_check import is_valid_email


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


def _usable(email):
    return email if isinstance(email, str) and is_valid_email(email) else None


class IndividualDirectory:
    def __init__(self, store):
        self._store = store

    def lookup(self, recipient: dict) -> Optional[Contact]:
        if recipient.get("type") == "adhoc":
            email, phone = _usable(recipient.get("email")), recipient.get("phone")
            ch = preferred_channel(email, phone, None)
            return Contact(name=recipient.get("name") or "", email=email, phone=phone, preferred_channel=ch) if ch else None
        got = IS.get(self._store, recipient["individual_id"])
        if not got.ok or got.data.get("status") in ("erased", "merged"):
            return None
        p = got.data
        email, phone = _usable(p.get("email")), p.get("phone")
        return Contact(name=p.get("display_name") or p.get("given_name") or "", email=email, phone=phone,
                       backup_phone=p.get("backup_phone"), preferred_channel=preferred_channel(email, phone, p.get("prefers_email")),
                       individual_id=p["id"])

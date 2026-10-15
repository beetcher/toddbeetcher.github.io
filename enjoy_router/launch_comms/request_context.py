"""The facts and the call for the request_received kind (the receipt). Port of cms_service.acknowledge's inputs.

The recipient is ad hoc: the name and email on the request (the person has no individual record until identity review).
"""
from __future__ import annotations

COMPLETION_LINK = "https://beetcher.com/enjoy/register/private/?r="


def facts(doc: dict) -> dict:
    out = {"name": " ".join((doc["first_name"], doc["last_name"])), "confirmation_number": doc["confirmation_number"]}
    if doc.get("registration_type") == "private" and doc.get("completion_token"):
        out["completion_link"] = COMPLETION_LINK + doc["completion_token"]
    return out


def call_for(doc: dict, by: str = "web:registration") -> dict:
    """Arguments for comms.notify (R-2): the receipt for a saved registration request."""
    return dict(kind="request_received", recipient={"type": "adhoc", "name": " ".join((doc["first_name"], doc["last_name"])), "email": doc["email"]},
                context=facts(doc), by=by, trigger="automatic", refs={"request_id": doc["id"]}, audience="requester")

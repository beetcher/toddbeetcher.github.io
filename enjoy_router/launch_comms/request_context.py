"""The facts and the call for the request_received kind (the receipt). Port of cms_service.acknowledge's inputs.

The recipient is ad hoc: the name and email on the request (the person has no individual record until identity review).
"""
from __future__ import annotations

TRAINER_NOTICE = "We're securing the best trainer for your area."
COMPLETION_LINK = "https://beetcher.com/enjoy/register/private/?r="


def facts(doc: dict) -> dict:
    out = {"name": " ".join((doc["first_name"], doc["last_name"])), "confirmation_number": doc["confirmation_number"]}
    if doc.get("registration_type") == "private" and doc.get("completion_token"):
        out["completion_link"] = COMPLETION_LINK + doc["completion_token"]
    if doc.get("coverage") == "no_active_region":
        out["trainer_notice"] = TRAINER_NOTICE
    return out


def call_for(doc: dict, by: str = "web:registration") -> dict:
    """Arguments for comms.notify (R-2): the receipt for a saved registration request."""
    return dict(kind="request_received", recipient={"type": "adhoc", "name": " ".join((doc["first_name"], doc["last_name"])), "email": doc["email"]},
                context=facts(doc), by=by, trigger="automatic", refs={"request_id": doc["id"]}, audience="requester")

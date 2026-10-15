"""The CMS call contract: result type, the closed reason-to-status map, the recipient forms (CMS_GUIDE.md sections 2 and 3; rules R-14, R-23).

Product-blind (R-1): standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CONTRACT_VERSION = 1

STATUSES = ("sent", "failed", "unknown", "not_sent", "skipped")
CHANNELS = ("email", "text", "none")
TRIGGERS = ("automatic", "manual")
REF_FIELDS = ("request_id", "scheduled_class_id", "attendance_id")

# Each reason belongs to exactly one status (R-14). communication_log.schema.json enforces the same map.
STATUS_OF = {
    "ok": "sent",
    "adapter_error": "failed",
    "timeout": "unknown",
    "unknown_kind": "not_sent", "invalid_context": "not_sent", "no_contact": "not_sent", "channel_unavailable": "not_sent",
    "no_template": "not_sent", "incomplete": "not_sent", "time_budget": "not_sent", "internal_error": "not_sent",
    "cms_off": "skipped", "log_only": "skipped", "duplicate": "skipped", "excluded": "skipped", "muted": "skipped",
}


@dataclass(frozen=True)
class Result:
    """What notify returns. log_id is None only when the log write itself failed."""
    status: str
    channel: str
    reason: str
    log_id: Optional[str] = None


@dataclass
class Contact:
    """Who a recipient resolves to, as the directory sees them. preferred_channel is the channel to use (already decided by the
    product's preference rules) or None when there is no way to reach the person."""
    name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    backup_phone: Optional[str] = None
    preferred_channel: Optional[str] = None
    muted: bool = False
    individual_id: Optional[str] = None


def normalize_recipient(recipient) -> dict:
    """{"type": "individual", "individual_id"} or {"type": "adhoc", "name", "email"?, "phone"?}. Raises ValueError otherwise."""
    if not isinstance(recipient, dict):
        raise ValueError("recipient must be a dict")
    kind = recipient.get("type")
    if kind == "individual":
        if not isinstance(recipient.get("individual_id"), str) or not recipient["individual_id"]:
            raise ValueError("individual recipient needs individual_id")
        return {"type": "individual", "individual_id": recipient["individual_id"]}
    if kind == "adhoc":
        out = {"type": "adhoc", "name": str(recipient.get("name") or "")}
        for k in ("email", "phone"):
            if recipient.get(k):
                out[k] = str(recipient[k]).strip()
        if "email" in out:
            out["email"] = out["email"].lower()
        if "email" not in out and "phone" not in out:
            raise ValueError("adhoc recipient needs an email or a phone")
        return out
    raise ValueError("recipient type must be individual or adhoc")

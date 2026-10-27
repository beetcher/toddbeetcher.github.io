"""The Console review code (schemas/review_code.schema.json, REVIEW_CODE_GUIDE.md). No Firebase in this file.

A super admin sets ONE temporary code (24 hours). A reviewer types it into the Console's Key box and is signed in as the view-only Global
Inspector. Only a salted hash is stored; the code is never kept or returned. Setting a new code replaces the old one and restarts the clock.

    problems(code, admin_key)        -> [issue, ...]   why a code is refused as a new code ([] when fine)
    set_code(store, code, who, now)  -> Result          creates or replaces the one record; data = {"expires_at": ...}
    clear(store, who, now)           -> None           turns the code off at once
    status(store, now)               -> dict            {"active", "expires_at", "set_by", "set_at"}, never the hash or salt
    access_for(given, store, now)    -> Access | None   the view-only access a matching, unexpired code gives; None otherwise
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from crud.schema_kit import failure, new_id, success, utc_stamp

COLLECTION = "review_codes"
ACCESS_KEY = "current"
HOURS = 24
MIN_LENGTH = 8
MAX_LENGTH = 64
ROLE_KEY = "global_inspector"
ACTOR = "review-code"
NAME = "Review access"
METHOD = "code"
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def normalise(code) -> str:
    return code.strip() if isinstance(code, str) else ""


def looks_like_token(code: str) -> bool:
    return code.count(".") == 2


def problems(code, admin_key="") -> list:
    """Why `code` cannot be a review code. Never says anything about the admin key's value."""
    c = normalise(code)
    out = []
    if len(c) < MIN_LENGTH:
        out.append("too_short")
    if len(c) > MAX_LENGTH:
        out.append("too_long")
    if _CONTROL.search(c):
        out.append("bad_characters")
    if looks_like_token(c):
        out.append("looks_like_a_token")
    if isinstance(admin_key, str) and admin_key and hmac.compare_digest(c.encode("utf-8"), admin_key.encode("utf-8")):
        out.append("same_as_the_admin_key")
    return out


def _hash(code: str, salt: str) -> str:
    return hmac.new(salt.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def _record(store):
    for d in store.query(COLLECTION, [("access_key", "==", ACCESS_KEY)], limit=5):
        if not d.get("deleted_at"):
            return d
    return None


def _parse(stamp):
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _expired(rec, now) -> bool:
    exp = _parse(rec.get("expires_at"))
    return exp is None or now >= exp


def set_code(store, code, who: str, now, admin_key=""):
    """Create the one record, or replace its hash, salt and expiry. `who` is the actor string of the super admin. The caller has already
    checked who may do this."""
    bad = problems(code, admin_key)
    if bad:
        return failure("validation_failed", [{"field": "code", "issue": i} for i in bad])
    c = normalise(code)
    salt = secrets.token_hex(16)
    fields = {"code_hash": _hash(c, salt), "salt": salt, "expires_at": utc_stamp(now + timedelta(hours=HOURS))}
    stamp = utc_stamp(now)
    rec = _record(store)
    if rec is None:
        store.create(COLLECTION, (rid := new_id()), {"id": rid, "schema_version": 1, "access_key": ACCESS_KEY, "created_at": stamp,
                                                      "created_by": who, "updated_at": stamp, "updated_by": who, "source": "dashboard", **fields})
    else:
        store.update(COLLECTION, rec["id"], {**fields, "updated_at": stamp, "updated_by": who}, ())
    return success({"expires_at": fields["expires_at"]})


def clear(store, who: str, now) -> None:
    """Turn the code off at once: the hash and salt are wiped and the expiry is set to now. Nothing to turn off is not an error."""
    rec = _record(store)
    if rec is not None:
        store.update(COLLECTION, rec["id"], {"code_hash": "", "salt": "", "expires_at": utc_stamp(now), "updated_at": utc_stamp(now), "updated_by": who}, ())


def status(store, now) -> dict:
    rec = _record(store)
    if rec is None or _expired(rec, now):
        return {"active": False}
    return {"active": True, "expires_at": rec["expires_at"], "set_at": rec.get("updated_at", ""), "set_by": rec.get("updated_by", "")}


def access_for(given, store, now):
    """The view-only access a matching, unexpired code gives, or None. The role is looked up by its key so the code follows the real
    Global Inspector role; a missing or switched-off role refuses the code."""
    from access.authorize import ALL_GRANT, Access, CAPABILITIES, GLOBAL      # imported here: authorize imports this module
    c = normalise(given)
    if not (MIN_LENGTH <= len(c) <= MAX_LENGTH) or looks_like_token(c):
        return None
    rec = _record(store)
    if rec is None or _expired(rec, now) or not isinstance(rec.get("salt"), str):
        return None
    if not hmac.compare_digest(_hash(c, rec["salt"]).encode("utf-8"), str(rec.get("code_hash", "")).encode("utf-8")):
        return None
    roles = [r for r in store.query("access_roles", [("key", "==", ROLE_KEY)], limit=5) if not r.get("deleted_at") and r.get("is_active") is True]
    if not roles:
        return None
    role = roles[0]
    caps = frozenset(c2 for c2 in role.get("capabilities", []) if c2 in GLOBAL).union(ALL_GRANT["capabilities"])
    return Access(True, actor=ACTOR, name=NAME, role_key=ROLE_KEY, capabilities=caps, is_super_admin=False,
                  grants=(ALL_GRANT,), method=METHOD)

"""What every door does about sign-in (P-62 step 3): one function, so the three doors cannot drift apart.

    access, refusal = sign_in(authorization, admin_key=..., verifier=..., store=..., limiter=..., visitor=..., now=..., tag="admin")
    if refusal: return refusal        # a ready HttpResult (401, 403, 429 or 500)
    ...then ask `allowed(access, need)` from access.policy; a miss is `forbidden()`.

Order, same as the key-only doors always had it: not configured (401) -> rate limit (429) -> check the credential. Only failures count
toward the rate limit (wrong key, bad token, an account that was not invited), never a good sign-in. Nothing here logs a key, a token or
an email: only codes.
"""
from __future__ import annotations

import logging

from handler import HttpResult, _error
from .authorize import MIN_KEY_LENGTH, authenticate

log = logging.getLogger("enjoy_router")

REFUSALS = {  # code -> (status, error code, message)
    "not_configured": (401, "unauthorized", "Unauthorized."),
    "unauthorized": (401, "unauthorized", "Unauthorized."),
    "not_invited": (403, "forbidden", "This Google account has not been invited."),
    "account_changed": (403, "forbidden", "This account cannot sign in. Ask the owner."),
}


def bearer(authorization: str) -> str:
    parts = (authorization or "").split(" ", 1)
    return parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else ""


def forbidden(tag: str) -> HttpResult:
    log.info("%s code=forbidden", tag)
    return _error(403, "forbidden", "You do not have access to this.")


def sign_in(authorization, *, admin_key, verifier, store, limiter, visitor, now, tag):
    """(Access, None) when in; (None, HttpResult) when refused."""
    key_on = isinstance(admin_key, str) and len(admin_key) >= MIN_KEY_LENGTH
    if not key_on and verifier is None:
        log.error("%s code=not_configured", tag)
        return None, _error(401, "unauthorized", "Unauthorized.")
    ts = now.timestamp()
    wait = limiter.retry_after(visitor, ts)
    if wait:
        log.info("%s code=rate_limited", tag)
        return None, _error(429, "rate_limited", "Too many attempts. Try again later.", {"Retry-After": str(wait)})
    try:
        access = authenticate(bearer(authorization), admin_key=admin_key, verifier=verifier, store=store, now=now)
    except Exception as exc:   # the access records could not be read: say nothing about the cause
        log.error("%s code=server_error exception=%s", tag, type(exc).__name__)
        return None, _error(500, "server_error", "Could not complete the request.")
    if access.ok:
        return access, None
    limiter.allow(visitor, ts)
    log.info("%s code=%s", tag, access.code)
    status, code, message = REFUSALS.get(access.code, REFUSALS["unauthorized"])
    return None, _error(status, code, message)


def me(access) -> dict:
    """What the Console learns about who is signed in (the `me` op). Never the key, never the uid."""
    return {"name": access.name, "email": access.email, "role_key": access.role_key, "method": access.method,
            "is_super_admin": access.is_super_admin, "scope_region_id": access.scope_region_id,
            "capabilities": sorted(access.capabilities), "unlimited": bool(access.is_super_admin or any(g.get("kind") == "all" for g in access.grants)),
            "grants": [{"kind": g.get("kind"), "state_code": g.get("state_code", ""), "region_ids": sorted(g.get("region_ids", ())),
                        "capabilities": sorted(g.get("capabilities", ())), "group": g.get("group", "")} for g in access.grants]}

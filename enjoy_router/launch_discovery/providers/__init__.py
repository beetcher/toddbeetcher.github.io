"""The AI-company adapters. Each takes an injected transport (and, for Gemini, a token function), so tests never touch the network,
and each answers with the core's ProviderResult: never raising, never carrying a key or provider text (D-2, D-11).

Closed error codes: key_missing, auth_failed, bad_request, rate_limited, provider_unavailable, unreadable_reply.
Status 401/403/400/404 are the provider refusing us (outcome rejected); 429, 5xx, timeouts and unreadable replies are no_answer.
"""
from __future__ import annotations

from discovery.contract import ProviderResult

CODES = ("key_missing", "auth_failed", "bad_request", "rate_limited", "provider_unavailable", "unreadable_reply")


def from_status(status: int):
    """None when status is a success, else the ProviderResult for the failure."""
    if 200 <= status < 300:
        return None
    if status in (401, 403):
        return ProviderResult("rejected", error_code="auth_failed")
    if status in (400, 404, 413, 422):
        return ProviderResult("rejected", error_code="bad_request")
    if status == 429:
        return ProviderResult("no_answer", error_code="rate_limited")
    return ProviderResult("no_answer", error_code="provider_unavailable")


def whole(n) -> int:
    return n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else 0

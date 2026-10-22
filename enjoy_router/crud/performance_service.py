"""The record_timing op (Console door only): a signed-in page reports how long its own sign-in took. The sender cannot choose who it is
recorded for (the server stamps the actor and the role), cannot send anything but the fixed numbers (the schema refuses unknown fields),
and is limited to one record per person per 10 seconds (more are dropped quietly, best effort per server instance). No name, email or
token is stored. See PERFORMANCE_EVENT_GUIDE.md."""
from __future__ import annotations

import time

from . import performance_events_crud as H
from .schema_kit import success

MIN_GAP_SECONDS = 10
_last: dict = {}


def record(store, access, args, actor, now=None):
    """Save one sign-in timing for `actor`. Returns the create result, or success({"recorded": False}) when it came too soon after the last."""
    t = time.monotonic()
    if t - _last.get(actor, -1e9) < MIN_GAP_SECONDS:
        return success({"recorded": False})
    data = {k: v for k, v in (args or {}).items()}
    data["role_key"] = access.role_key or "unknown"          # never from the sender
    r = H.save(store, data, actor, now=now)
    if r.ok:
        _last[actor] = t
        if len(_last) > 5000:
            _last.clear()
    return r


def reset_limiter():
    _last.clear()

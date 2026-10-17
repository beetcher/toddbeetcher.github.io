"""The Discovery door (`enjoy_discovery`): the Console's way to quote, start, step, stop and withdraw runs and to read them.

    POST  ...  Authorization: Bearer <ICDT_ADMIN_KEY>      body: {"op": "...", "args": {...}}

ops (args):
    status                                   the mode, which model keys exist, the ZIP table (never a key)
    quote       finder_key, model_id, area_ids, type_keys, max_results, spend_cap_cents   cost range and the exact prompts; saves nothing
    plan        (same)                       checks everything, saves the run record, returns its id
    step        run_id                       does ONE chunk (one AI call); the Console calls it again until `done`
    stop        run_id
    withdraw    run_id                       takes back what the run created and is still untouched
    get_run     id
    list_runs   limit (optional)             newest first
    zips        state_code                   every ZIP in that state with its place name and centre point, for the Console map

Fails closed like the Console: no admin key setting (or under 32 characters) means nothing is allowed. Logs only codes. The engine is
built by the caller (main.py), so tests can pass one with a fake AI. This file has no Firebase in it.
"""
from __future__ import annotations

import hmac
import json
import logging

from console import MIN_KEY_LENGTH, _bearer
from crud import discovery_runs_crud as RU
from discovery.contract import RunRequest
from handler import HttpResult, _error
from launch_discovery import wiring, zip_table

log = logging.getLogger("enjoy_router")
ACTOR = "user:admin"
MAX_BODY_BYTES = 20_000
OPS = {"status": (set(), set()), "quote": ({"finder_key", "model_id", "area_ids", "type_keys", "max_results", "spend_cap_cents"}, set()),
       "plan": ({"finder_key", "model_id", "area_ids", "type_keys", "max_results", "spend_cap_cents"}, set()),
       "step": ({"run_id"}, set()), "stop": ({"run_id"}, set()), "withdraw": ({"run_id"}, set()),
       "get_run": ({"id"}, set()), "list_runs": (set(), {"limit"}), "zips": ({"state_code"}, set())}
STATUS = {"mode_off": 409, "run_not_active": 409, "nothing_to_withdraw": 409, "run_not_found": 404, "unknown_finder": 404,
          "unknown_model": 404, "unknown_area": 404, "unknown_type": 404, "internal_error": 500}


def _request(a):
    """A RunRequest from the sender's args, or None when the shapes are wrong."""
    def ids(v, n):
        return isinstance(v, list) and 0 < len(v) <= n and all(isinstance(x, str) and 0 < len(x) <= 100 for x in v)
    def num(v):
        return isinstance(v, int) and not isinstance(v, bool) and v >= 0
    if not (isinstance(a["finder_key"], str) and isinstance(a["model_id"], str) and ids(a["area_ids"], 50) and ids(a["type_keys"], 30)
            and num(a["max_results"]) and num(a["spend_cap_cents"])):
        return None
    return RunRequest(a["finder_key"], a["model_id"], tuple(a["area_ids"]), tuple(a["type_keys"]), a["max_results"], a["spend_cap_cents"])


def handle_discovery(method, authorization, raw_body, admin_key, visitor, store, engine, environ, limiter, now) -> HttpResult:
    if method.upper() != "POST":
        return _error(405, "validation_failed", "Use POST.", {"Allow": "POST"})
    if not admin_key or len(admin_key) < MIN_KEY_LENGTH:
        log.error("discovery code=not_configured")
        return _error(401, "unauthorized", "Unauthorized.")
    ts = now.timestamp()
    wait = limiter.retry_after(visitor, ts)
    if wait:
        return _error(429, "rate_limited", "Too many attempts. Try again later.", {"Retry-After": str(wait)})
    given = _bearer(authorization)
    if not given or not hmac.compare_digest(given.encode("utf-8"), admin_key.encode("utf-8")):
        limiter.allow(visitor, ts)
        log.info("discovery code=unauthorized")
        return _error(401, "unauthorized", "Unauthorized.")
    if len(raw_body) > MAX_BODY_BYTES:
        return _error(413, "validation_failed", "The request is too large.")
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else None
    except (UnicodeDecodeError, ValueError):
        return _error(400, "validation_failed", "The request body must be JSON.")
    if not isinstance(body, dict) or body.get("op") not in OPS:
        return _error(400, "validation_failed", "Send a JSON object with op and args. Known ops: " + ", ".join(sorted(OPS)) + ".")
    op, args = body["op"], body.get("args", {})
    if not isinstance(args, dict):
        return _error(400, "validation_failed", "args must be an object.")
    required, optional = OPS[op]
    missing, extra = sorted(required - set(args)), sorted(set(args) - required - optional)
    if missing or extra:
        return _error(400, "validation_failed", f"For {op}: " + (f"missing {', '.join(missing)}. " if missing else "")
                      + (f"not allowed: {', '.join(extra)}." if extra else ""))
    try:
        data = _run(op, args, store, engine, environ)
    except Exception as exc:
        log.error("discovery code=server_error op=%s exception=%s", op, type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")
    if data[0]:
        log.info("discovery op=%s code=ok", op)
        return HttpResult(200, {"ok": True, "data": data[1]}, {"Cache-Control": "no-store"})
    log.info("discovery op=%s code=%s", op, data[1])
    return _error(STATUS.get(data[1], 400), data[1], data[2])


def _run(op, a, store, engine, environ):
    """(True, data) or (False, code, message)."""
    if op == "status":
        return True, wiring.status(store, environ)
    if op in ("quote", "plan"):
        rq = _request(a)
        if rq is None:
            return False, "bad_request", "The request is not complete."
        with wiring.no_gps():
            r = engine.quote(rq) if op == "quote" else engine.plan(rq, ACTOR)
    elif op in ("step", "stop", "withdraw"):
        if not isinstance(a["run_id"], str):
            return False, "bad_request", "run_id must be text."
        with wiring.no_gps():
            r = getattr(engine, op)(a["run_id"], ACTOR)
    elif op == "zips":
        sc = a["state_code"]
        if not (isinstance(sc, str) and len(sc) == 2 and sc.isalpha() and sc.isupper()):
            return False, "bad_request", "state_code must be two capital letters."
        t = zip_table.table() or {}
        return True, {"state_code": sc, "loaded": bool(t), "zips": [[z, row[1], row[2], row[3] if len(row) > 3 else ""] for z, row in sorted(t.items()) if row[0] == sc]}
    elif op == "get_run":
        got = RU.get(store, a["id"])
        return (True, got.data) if got.ok else (False, "run_not_found", "No such run.")
    else:
        got = RU.list(store, None, "-created_at", a.get("limit", 20)) if isinstance(a.get("limit", 20), int) else None
        return (True, got.data) if got and got.ok else (False, "bad_request", "limit must be a number.")
    return (True, r.data) if r.ok else (False, r.code, r.message)

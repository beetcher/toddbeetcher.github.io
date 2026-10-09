#!/usr/bin/env python3
"""In-memory tests for the Console records endpoint (console.py). Run: python3 run_console_tests.py"""
import io
import json
import logging
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from console import handle_console, make_failure_limiter  # noqa: E402
from memory_store import MemoryStore  # noqa: E402

KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"  # 34 chars, a test value only
NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
fails = []


def check(label, ok):
    print(f"{'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        fails.append(label)


def store_with(n=5):
    s = MemoryStore([])
    for i in range(n):
        s.requests.append({"id": f"id{i}", "confirmation_number": f"ICDT-{i:06d}", "email": f"p{i}@example.com",
                           "created_at": f"2026-10-09T04:26:{i:02d}Z", "registration_type": "private"})
    return s


def call(store=None, auth=None, params=None, key=KEY, method="GET", limiter=None, visitor="v", now=NOW):
    return handle_console(method, auth if auth is not None else f"Bearer {KEY}", params or {}, key, visitor,
                          store or store_with(), limiter or make_failure_limiter(), now)


r = call(auth="")
check("no key: 401 unauthorized, no records", r.status == 401 and r.body["error"]["code"] == "unauthorized" and "data" not in r.body)
r = call(auth="Bearer wrong")
check("wrong key: 401", r.status == 401)
check("401 gives no hint (same body for missing and wrong)", call(auth="").body == call(auth="Bearer wrong").body)
r = call()
ids = [d["id"] for d in r.body["data"]["records"]]
check("correct key: 200 and newest first", r.status == 200 and ids == ["id4", "id3", "id2", "id1", "id0"])
check("reply carries count and server_time", r.body["data"]["count"] == 5 and r.body["data"]["server_time"] == "2026-10-09T12:00:00Z")
check("Cache-Control: no-store on success and on errors", r.headers.get("Cache-Control") == "no-store" and call(auth="").headers.get("Cache-Control") == "no-store")

r = call(params={"since": "2026-10-09T04:26:03Z"})
check("since returns only records at or after it, newest first", [d["id"] for d in r.body["data"]["records"]] == ["id4", "id3"])
r = call(params={"limit": "2"})
check("limit is respected", [d["id"] for d in r.body["data"]["records"]] == ["id4", "id3"])
big = store_with(250)
big_store = MemoryStore([])
for i in range(250):
    big_store.requests.append({"id": f"b{i:03d}", "created_at": f"2026-10-09T{i // 60:02d}:{i % 60:02d}:00Z"})
check("default limit is 100", call(store=big_store).body["data"]["count"] == 100)
check("limit above 200 is capped at 200", call(store=big_store, params={"limit": "9999"}).body["data"]["count"] == 200)
check("limit 0 or negative still returns at least one", call(params={"limit": "0"}).body["data"]["count"] == 1)
check("limit that is not a number: 400", call(params={"limit": "abc"}).status == 400)
check("since that is not a time: 400", call(params={"since": "yesterday"}).status == 400)

for label, k in (("missing", ""), ("short", "short-key")):
    r = call(key=k)
    check(f"admin key setting {label}: refuses everything, even with a matching key", r.status == 401 and "data" not in r.body)
r = call(key="short-key", auth="Bearer short-key")
check("a short setting is not rescued by sending the same short key", r.status == 401)

check("POST gets 405", call(method="POST").status == 405)
check("PUT gets 405", call(method="PUT").status == 405)

lim = make_failure_limiter()
codes = [call(auth="Bearer nope", limiter=lim, visitor="x").status for _ in range(11)]
check("10 wrong keys get 401, the 11th is 429", codes[:10] == [401] * 10 and codes[10] == 429)
r = call(limiter=lim, visitor="x")
check("once blocked, even the right key waits (429 with Retry-After)", r.status == 429 and "Retry-After" in r.headers)
check("another visitor is not blocked", call(limiter=lim, visitor="y").status == 200)
lim2 = make_failure_limiter()
for _ in range(30):
    call(limiter=lim2, visitor="z")
check("correct keys are never counted as failures", call(limiter=lim2, visitor="z").status == 200)

buf = io.StringIO()
h = logging.StreamHandler(buf)
logging.getLogger("enjoy_router").addHandler(h)
logging.getLogger("enjoy_router").setLevel(logging.DEBUG)
call()
call(auth="Bearer SECRETWRONGKEY")
call(key="")
text = buf.getvalue()
check("logs hold codes and counts, never the key or record content",
      KEY not in text and "SECRETWRONGKEY" not in text and "example.com" not in text and "ICDT-" not in text and "code=ok count=5" in text)


class Boom(MemoryStore):
    def list_requests(self, limit, since=None):
        raise RuntimeError("secret detail jane@example.com")


r = call(store=Boom([]))
check("a crash gives a plain server_error that reveals nothing", r.status == 500 and "secret" not in json.dumps(r.body))

# CORS lives in main.py (Firebase's own option); this checks the allowed list it is built from.
import os  # noqa: E402
os.environ["ICDT_STORE"] = "memory"
try:
    import main  # noqa: E402
    check("CORS list allows beetcher.com and not a stranger", "https://beetcher.com" in main.ORIGINS and "https://evil.example" not in main.ORIGINS)
    check("both functions are defined", hasattr(main, "enjoy_console_records") and hasattr(main, "enjoy_registration_request"))
except ImportError as exc:
    print(f"skip main.py checks here: {exc}")

print(f"\nFAILED: {len(fails)}" if fails else "\nOK: all console tests pass (in memory)")
sys.exit(1 if fails else 0)

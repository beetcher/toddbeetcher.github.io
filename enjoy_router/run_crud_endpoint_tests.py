#!/usr/bin/env python3
"""In-memory tests for the CRUD test endpoint (crud_endpoint.py). Run from enjoy_router/: python3 run_crud_endpoint_tests.py"""
import json
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_crud_test, make_failure_limiter  # noqa: E402

KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
EX = json.loads((HERE.parent / "schemas" / "examples" / "venue.examples.json").read_text())["valid"]
fails = []


def check(label, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {label} {'' if ok else detail}")
    if not ok:
        fails.append(label)


store = MemoryDocStore("test_")
limiter = make_failure_limiter()


def call(body, auth=f"Bearer {KEY}", method="POST", key=KEY, raw=None, lim=None, visitor="v"):
    data = raw if raw is not None else json.dumps(body).encode()
    return handle_crud_test(method, auth, data, key, visitor, store, lim or limiter, NOW)


def op(o, **args):
    return call({"collection": "venues", "op": o, "args": args})


r = call({}, auth="")
check("no key: 401, nothing run", r.status == 401 and not store.data)
r = call({}, auth="Bearer wrong")
check("wrong key: 401", r.status == 401 and r.body["error"]["code"] == "unauthorized")
check("GET refused: 405", call({}, method="GET").status == 405)
check("no admin key configured: fails closed", call({}, key="").status == 401)
check("short admin key: fails closed", call({}, key="short", auth="Bearer short").status == 401)

lim = make_failure_limiter()
for _ in range(10):
    call({}, auth="Bearer wrong", lim=lim, visitor="x")
r = call({}, auth="Bearer wrong", lim=lim, visitor="x")
check("11th wrong key: 429 with Retry-After", r.status == 429 and "Retry-After" in r.headers)
r = call({}, lim=lim, visitor="x")
check("blocked visitor is refused even with the right key", r.status == 429)

check("bad JSON: 400", call(None, raw=b"{nope").status == 400)
check("not an object: 400", call(["x"]).status == 400)
check("unknown collection: 400", call({"collection": "people", "op": "get", "args": {}}).status == 400)
check("unknown op: 400", call({"collection": "venues", "op": "drop", "args": {}}).status == 400)
r = op("get")
check("missing arg named: 400", r.status == 400 and "id" in r.body["error"]["message"])
r = op("soft_delete", id="x", extra=1)
check("extra arg refused: 400", r.status == 400 and "extra" in r.body["error"]["message"])
check("oversized body: 413", call(None, raw=b"x" * 100_001).status == 413)
check("nothing written by refused calls", not store.data)

r = op("create", data=EX["active_full_detail"])
check("create: 200 with record", r.status == 200 and r.body["ok"] and r.body["data"]["created_by"] == "system:crud_test")
vid = r.body["data"]["id"]
check("stored only under the test_ prefix", list(store.data) == ["test_venues"])
r = op("create", data=EX["active_full_detail"])
check("duplicate slug: 400 with problem", r.status == 400 and r.body["error"]["problems"] == [{"field": "slug", "issue": "duplicate"}])
r = op("create", data={"name": "x"})
check("invalid: 400, problems name fields only", r.status == 400 and all(set(p) == {"field", "issue"} for p in r.body["error"]["problems"]))
check("get: 200", op("get", id=vid).status == 200)
check("get missing: 404", op("get", id="11111111-1111-4111-8111-111111111111").status == 404)
r = op("update", id=vid, changes={"name": "Renamed"})
check("update: 200 changed name", r.status == 200 and r.body["data"]["changed"] == ["name"])
r = op("update", id=vid, changes={"name": "Again"}, expected_updated_at="2020-01-01T00:00:00Z")
check("stale update: 409 conflict", r.status == 409 and r.body["error"]["code"] == "conflict")
r = op("list")
check("list: 200 count 1", r.status == 200 and r.body["data"]["count"] == 1)
r = op("list", filters={"city": "x"})
check("unsupported list: 400", r.status == 400)
check("set_review_summary: 200", op("set_review_summary", id=vid, review_count=2, average_rating=4).status == 200)
check("soft_delete: 200", op("soft_delete", id=vid).status == 200)
check("soft_delete again: 404", op("soft_delete", id=vid).status == 404)
check("no-store on success", op("list").headers.get("Cache-Control") == "no-store")
blob = json.dumps(call({}, auth="Bearer wrong").body)
check("error body never contains the key", KEY not in blob)

print()
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
print("OK: all CRUD endpoint tests pass (in memory)")

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


# Deleted requests (for Restore): hidden from the normal list, returned alone with ?deleted=1, secret still stripped
ds = store_with(3)
ds.requests[1]["deleted_at"] = "2026-10-09T05:00:00Z"; ds.requests[1]["deleted_by"] = "user:admin"; ds.requests[1]["completion_token"] = "secret-token"
check("a deleted request is not in the normal list", [d["id"] for d in call(store=ds).body["data"]["records"]] == ["id2", "id0"])
rd = call(store=ds, params={"deleted": "1"})
check("deleted=1 returns only the deleted ones, with who and when", rd.status == 200 and [d["id"] for d in rd.body["data"]["records"]] == ["id1"] and rd.body["data"]["records"][0]["deleted_by"] == "user:admin")
check("deleted=1 never carries the receipt-link secret", "secret-token" not in json.dumps(rd.body))
check("deleted=1 still needs the key", call(store=ds, params={"deleted": "1"}, auth="").status == 401)
check("deleted=0 or anything else is the normal list", [d["id"] for d in call(store=ds, params={"deleted": "0"}).body["data"]["records"]] == ["id2", "id0"])
# Search + Region (Requests Search/Region build): regions are worked out on read; q and region search the newest SCAN_MAX; reply carries total
ss = MemoryStore([])
ss.areas["r-front"] = {"id": "r-front", "kind": "region", "name": "Front Range", "state_code": "CO", "is_active": True, "zip_codes": ["80301", "80302"]}
ss.areas["r-west"] = {"id": "r-west", "kind": "region", "name": "Western Slope", "state_code": "CO", "is_active": False, "zip_codes": ["81501"]}
ss.areas["r-gone"] = {"id": "r-gone", "kind": "region", "name": "Gone", "state_code": "CO", "is_active": True, "zip_codes": ["80301"], "deleted_at": "2026-01-01T00:00:00Z"}
def req(i, first, last, zip_=None, region_id=None, **kw):
    d = {"id": "s%d" % i, "confirmation_number": "ICDT-%06d" % (100 + i), "email": "%s@example.com" % first.lower(), "first_name": first, "last_name": last,
         "created_at": "2026-10-09T04:00:%02dZ" % i, "registration_type": "private", "completion_token": "tok"}
    if zip_: d["postal_code"] = zip_
    if region_id: d["region_id"] = region_id
    d.update(kw); return d
ss.requests.extend([req(1, "Ann", "Boulder", "80301"), req(2, "Bob", "Slope", "81501"), req(3, "Cy", "Nowhere", "99999"), req(4, "Di", "Picked", None, "r-front", phone="(303) 555-0142"), req(5, "Ed", "Gone", "80302", deleted_at="2026-10-09T05:00:00Z")])
rs = call(store=ss).body["data"]
byid = {d["id"]: d for d in rs["records"]}
check("each request carries its regions, by ZIP", [r["id"] for r in byid["s1"]["regions"]] == ["r-front"] and [r["name"] for r in byid["s2"]["regions"]] == ["Western Slope"])
check("a deleted region is never a tag; a ZIP nobody holds has no region", all(r["id"] != "r-gone" for r in byid["s1"]["regions"]) and byid["s3"]["regions"] == [])
check("with no ZIP, the region picked on the form is the tag", [r["id"] for r in byid["s4"]["regions"]] == ["r-front"])
check("a plain list has no total (nothing was searched)", "total" not in rs and "completion_token" not in json.dumps(rs))
rq = call(store=ss, params={"q": "ann"}).body["data"]
check("q finds by name and reports total, scanned", [d["id"] for d in rq["records"]] == ["s1"] and rq["total"] == 1 and rq["scanned"] == 5 and rq["truncated"] is False)
check("q finds by email, reference number, ZIP, phone digits, region name", all([d["id"] for d in call(store=ss, params={"q": q}).body["data"]["records"]] == [i] for q, i in
      [("bob@example", "s2"), ("icdt-000103", "s3"), ("99999", "s3"), ("3035550142", "s4"), ("western", "s2")]))
check("every word must match", call(store=ss, params={"q": "ann slope"}).body["data"]["total"] == 0 and call(store=ss, params={"q": "front di"}).body["data"]["total"] == 1)
check("region filter by id", [d["id"] for d in call(store=ss, params={"region": "r-front"}).body["data"]["records"]] == ["s4", "s1"])
check("region=none lists those with no region", [d["id"] for d in call(store=ss, params={"region": "none"}).body["data"]["records"]] == ["s3"])
check("region and q work together", [d["id"] for d in call(store=ss, params={"region": "r-front", "q": "di"}).body["data"]["records"]] == ["s4"])
check("search never shows a deleted request, deleted=1 searches only deleted", call(store=ss, params={"q": "gone"}).body["data"]["total"] == 0 and [d["id"] for d in call(store=ss, params={"q": "gone", "deleted": "1"}).body["data"]["records"]] == ["s5"])
check("search still needs the key; q longer than 80 is a 400", call(store=ss, params={"q": "a"}, auth="").status == 401 and call(store=ss, params={"q": "a" * 81}).status == 400)
import console as _c  # noqa: E402
old = _c.SCAN_MAX; _c.SCAN_MAX = 3
rt = call(store=ss, params={"q": "example"}).body["data"]
_c.SCAN_MAX = old
check("a scan that hits the cap says so", rt["scanned"] == 3 and rt["truncated"] is True)

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

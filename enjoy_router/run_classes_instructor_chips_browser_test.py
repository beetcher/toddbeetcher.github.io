#!/usr/bin/env python3
"""Browser test (P-100): the Classes chips "Needs an instructor" and "Full". A class needs an instructor when it is live and nobody teaches it; it is full when
the seats held by students reach its biggest size (the waiting list and cancelled or withdrawn sign-ups hold no seat). Real sign-ups in an in-memory store.
Run from enjoy_router/:  python3 run_classes_instructor_chips_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import scheduled_classes_crud as CL, individuals_service as IS, attendances_service as AT
from crud_endpoint import handle_admin, make_failure_limiter
from test_helpers import give_address
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []; A = "user:admin"
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
base = {"class_type": "group", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 9, "status": "identified"}
def mk(title, **kw):
    d = {**base, "title": title, "slug": "".join(ch for ch in title.lower() if ch.isalnum())}; d.update(kw)
    r = CL.create(store, d, A); assert r.ok, r.problems; return r.data
def person(given):
    r = IS.create(store, {"given_name": given, "family_name": "Test"}, A); assert r.ok, r.problems; return r.data
def put(cls, who, role, status=None):
    d = {"scheduled_class_id": cls["id"], "role": role, "individual_id": who["id"]}
    if status: d["status"] = status
    r = AT.assign(store, d, A); assert r.ok, r.problems; return r.data
teacher = person("Tina"); give_address(store, teacher["id"])
s1, s2, s3 = person("Sam"), person("Sue"), person("Stu")
c_none = mk("Alpha no teacher")                                     # live, nobody teaches
c_taught = mk("Bravo taught"); put(c_taught, teacher, "primary_instructor")
c_full = mk("Charlie full", capacity_max=2); put(c_full, teacher, "primary_instructor"); put(c_full, s1, "student"); put(c_full, s2, "student")
c_wait = mk("Delta almost", capacity_max=2); put(c_wait, teacher, "instructor"); put(c_wait, s1, "student"); put(c_wait, s2, "student", "waitlisted")   # the waiting list holds no seat
c_cxl = mk("Echo cancelled", status="cancelled", cancelled_reason="test")                       # not live: never "needs an instructor"
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/classes'"); pg.wait_for_selector("#cList li"); pg.wait_for_timeout(300)
    titles = lambda: sorted(t.strip() for t in pg.locator("#cList > li .vname").all_text_contents())
    check("two new switches beside Needs a venue", pg.locator("#cChips .cf-chip", has_text="Needs an instructor").count() == 1 and pg.locator("#cChips .cf-chip", has_text="Full").count() == 1)
    check("badges count the live classes only (1 needs an instructor, 1 is full)", pg.locator("#cChips .cf-chip", has_text="Needs an instructor").inner_text().strip().endswith("1") and pg.locator("#cChips .cf-chip", has_text="Full").inner_text().strip().endswith("1"), pg.locator("#cChips").inner_text())
    pg.locator("#cChips .cf-chip", has_text="Needs an instructor").click(); pg.wait_for_timeout(250)
    check("Needs an instructor shows only the class nobody teaches (not the taught ones, not the cancelled one)", titles() == ["Alpha no teacher"], titles())
    pg.locator("#cChips .cf-chip", has_text="Needs an instructor").click(); pg.wait_for_timeout(200)
    pg.locator("#cChips .cf-chip", has_text="Full").click(); pg.wait_for_timeout(250)
    check("Full shows only the class whose seats are all taken (the waiting list holds no seat)", titles() == ["Charlie full"], titles())
    pg.locator("#cChips .cf-chip", has_text="Needs an instructor").click(); pg.wait_for_timeout(250)
    check("both switches together show nothing here (a full class has a teacher)", titles() == [], titles())
    pg.locator("#cChips .cf-chip", has_text="Full").click(); pg.locator("#cChips .cf-chip", has_text="Needs an instructor").click(); pg.wait_for_timeout(250)
    check("switched off, every class is back", len(titles()) == 4 or len(titles()) == 5, titles())
    # a teacher is added: the class stops needing one after the list is read again
    put(c_none, teacher, "primary_instructor"); pg.click("#cRefresh"); pg.wait_for_timeout(500)
    pg.locator("#cChips .cf-chip", has_text="Needs an instructor").click(); pg.wait_for_timeout(250)
    check("after a teacher is added and the page is refreshed, nothing needs an instructor", titles() == [], titles())
    check("no page errors", not errs, errs)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: classes instructor and full chips pass"); sys.exit(1 if fails else 0)

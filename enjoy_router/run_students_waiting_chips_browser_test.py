#!/usr/bin/env python3
"""Browser test (P-99, students): the Students switches "Waiting for a class" and "In a class". A student is in a class when they hold a seat (placed or
confirmed); otherwise an active student is waiting for a class (never placed, on the waiting list only, or the placement ended). Real sign-ups in an in-memory store.
Run from enjoy_router/:  python3 run_students_waiting_chips_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import scheduled_classes_crud as CL, individuals_service as IS, attendances_service as AT
from crud_endpoint import handle_admin, make_failure_limiter
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
cls = CL.create(store, {**base, "title": "Open class", "slug": "openclass"}, A); assert cls.ok, cls.problems; cls = cls.data
def person(given):
    r = IS.create(store, {"given_name": given, "family_name": "Test"}, A); assert r.ok, r.problems; return r.data
cls2 = CL.create(store, {**base, "title": "Second class", "slug": "secondclass"}, A); assert cls2.ok, cls2.problems; cls2 = cls2.data
def put(who, status=None, into=None):
    d = {"scheduled_class_id": (into or cls)["id"], "role": "student", "individual_id": who["id"]}
    if status: d["status"] = status
    r = AT.assign(store, d, A); assert r.ok, r.problems; return r.data
sam, sal, sue, stu = person("Sam"), person("Sal"), person("Sue"), person("Stu")
put(sam, "confirmed"); put(sal)                       # in a class (confirmed, and placed)
put(sue, "waitlisted"); put(stu, "declined")          # on the waiting list only; placement ended: both are waiting for a class
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/students'"); pg.wait_for_selector("#rsList li"); pg.wait_for_timeout(300)
    names = lambda: sorted(t.split(" ")[0] for t in pg.locator("#rsList > li .vname").all_text_contents())
    chip = lambda t: pg.locator("#rsChips .cf-chip", has_text=t)
    check("two new switches on Students", chip("Waiting for a class").count() == 1 and chip("In a class").count() == 1)
    check("all four active students are listed", names() == ["Sal", "Sam", "Stu", "Sue"], names())
    check("badges: 2 waiting, 2 in a class", chip("Waiting for a class").inner_text().strip().endswith("2") and chip("In a class").inner_text().strip().endswith("2"), pg.locator("#rsChips").inner_text())
    chip("In a class").click(); pg.wait_for_timeout(250)
    check("In a class shows those who hold a seat (placed or confirmed)", names() == ["Sal", "Sam"], names())
    chip("In a class").click(); chip("Waiting for a class").click(); pg.wait_for_timeout(250)
    check("Waiting for a class shows the waiting-list and ended placements", names() == ["Stu", "Sue"], names())
    chip("In a class").click(); pg.wait_for_timeout(250)
    check("both switches together show nobody", names() == [], names())
    chip("In a class").click(); chip("Waiting for a class").click(); pg.wait_for_timeout(250)
    # placing Stu in another class moves them across after the page is refreshed
    put(stu, "confirmed", cls2); pg.click("#rsRefresh"); pg.wait_for_timeout(500); chip("Waiting for a class").click(); pg.wait_for_timeout(250)
    check("after Stu is placed and the page is refreshed, only Sue is still waiting", names() == ["Sue"], names())
    check("no page errors", not errs, errs)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: students waiting and in-a-class chips pass"); sys.exit(1 if fails else 0)

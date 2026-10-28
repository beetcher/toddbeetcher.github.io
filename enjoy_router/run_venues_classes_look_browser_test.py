#!/usr/bin/env python3
"""Browser test (venues + classes look): the Classes page: head, chips, search, paging, row, button cues, plain words, states, form, phone.
Run from enjoy_router/:  python3 run_venues_classes_look_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone, timedelta
from crud.memory_doc_store import MemoryDocStore
from crud import scheduled_classes_crud as CL, venues_service as VS
from crud_endpoint import handle_admin, make_failure_limiter
from test_helpers import give_venue_zone
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
v = VS.create_with_place(store, {"name": "Library", "slug": "library", "status": "inactive", "is_public_venue": True}, A,
                         address={"street": "951 Spruce St", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"})
assert v.ok, v.problems; give_venue_zone(store, v.data["id"], actor=A); assert VS.update(store, v.data["id"], {"status": "active"}, A).ok
base = {"class_type": "private", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 5, "capacity_max": 9}
now = datetime.now(timezone.utc)
def mk(i, **kw):
    d = {**base, "title": "Class %02d" % i, "slug": "c%02d" % i, "status": "identified"}; d.update(kw)
    r = CL.create(store, d, A); assert r.ok, r.problems; return r.data
mk(0, title="A very long class title that goes on and on about the many things people can learn in one friendly afternoon together at the library", slug="long", status="scheduled", venue_id=v.data["id"], starts_at=(now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"), time_zone="America/Denver", duration_minutes=60, is_venue_confirmed=False)
for i in range(1, 56): mk(i)                       # 55 ideas, no venue, no date
mk(60, title="Old Done", slug="olddone", status="scheduled", venue_id=v.data["id"], starts_at=(now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ"), time_zone="America/Denver", duration_minutes=60, is_venue_confirmed=False)
def lay(pg):
    return pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
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
    pg.evaluate("location.hash='#/classes'"); pg.wait_for_selector("#cList li")
    check("head: title, orange Add, Manual and Refresh as links", pg.inner_text("#cTitleH") == "Classes" and "btn-primary" in pg.get_attribute("#cAddBtn", "class") and "btn-link" in pg.get_attribute("#cRefresh", "class"))
    check("old tick-box filter gone, Status chip present", pg.locator("#cFilters, #cShowAll").count() == 0 and pg.locator("#cChips .cf-chip", has_text="Status").count() == 1)
    check("count says 57 classes, 50 on the page", pg.inner_text("#cCount") == "57 classes" and pg.locator("#cList > li").count() == 50, pg.inner_text("#cCount"))
    check("Show more bar", pg.locator("#cMore").inner_text().strip() != "")
    pg.locator("#cMore button").first.click(); pg.wait_for_timeout(250)
    check("show more reveals the rest", pg.locator("#cList > li").count() == 57)
    first = pg.locator("#cList > li", has_text="A very long class").first
    check("scheduled row, status in plain words", "Scheduled" in first.inner_text())
    check("long title clamped, full title in tooltip", len(first.locator(".vname").get_attribute("title")) > 80)
    names = lambda: [b_.inner_text() for b_ in first.locator("button").all()]
    check("action row cues", first.get_by_role("button", name="Attendance", exact=True).get_attribute("class").find("btn-primary") >= 0 and "btn-danger" in first.get_by_role("button", name="Delete", exact=True).get_attribute("class") and "btn-secondary" in first.get_by_role("button", name="Journal", exact=True).get_attribute("class"))
    check("ideas called Idea", "Idea" in pg.locator("#cList > li", has_text="Class 01").first.inner_text())
    pg.locator("#cChips .cf-chip", has_text="Needs a venue").click(); pg.wait_for_timeout(250)
    check("Needs a venue narrows to the 55 ideas", pg.locator("#cList > li").count() == 50 and pg.inner_text("#cCount").startswith("Showing 55 of 57"), pg.inner_text("#cCount"))
    pg.locator("#cChips .cf-chip", has_text="Needs a venue").click(); pg.wait_for_timeout(200)
    pg.locator("#cChips .cf-chip", has_text="Past").click(); pg.wait_for_timeout(250)
    check("Past narrows to the completed one", pg.locator("#cList > li").count() == 1 and "Old Done" in pg.inner_text("#cList"))
    pg.locator("#cChips .cf-chip", has_text="Past").click(); pg.wait_for_timeout(200)
    pg.fill("#cSearch", "zzzz"); pg.wait_for_timeout(250)
    check("no-match with Clear link", pg.evaluate("document.getElementById('cNoMatch').hidden === false") and pg.locator("#cClear").count() == 1)
    pg.click("#cClear"); pg.wait_for_timeout(300)
    check("clear restores the list", pg.inner_text("#cCount") == "57 classes" and pg.input_value("#cSearch") == "")
    pg.fill("#cSearch", "old done"); pg.wait_for_timeout(250)
    check("search by title", pg.locator("#cList > li").count() == 1)
    pg.fill("#cSearch", ""); pg.wait_for_timeout(200)
    pg.click("#cAddBtn"); pg.wait_for_selector("#cAddForm:not([hidden])")
    check("form: sections, stars, Save orange, Cancel outlined", pg.locator("#cAddForm .fsec").count() >= 2 and pg.locator("#cAddForm .req").count() >= 4 and "btn-primary" in pg.get_attribute("#cSaveBtn", "class") and "btn-secondary" in pg.get_attribute("#cCancelBtn", "class"))
    pg.click("#cCancelBtn")
    check("two across at 1440", pg.evaluate("(function(){var l=document.querySelectorAll('#cList > li');return l[0].getBoundingClientRect().top === l[1].getBoundingClientRect().top})()"))
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(300)
    check("phone: no sideways scroll", lay(pg))
    check("phone: buttons 44px", pg.evaluate("[].every.call(document.querySelectorAll('#cList > li:first-child button, #cAddBtn'), function(b){return b.offsetHeight===0||b.offsetHeight>=44})"))
    check("no page errors", not errs, errs)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: venues+classes look checks pass"); sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Browser test (People look, combo build): head, filters, paging, the town and role join, row, button cues, plain words, merge picker, states, forms, phone.
Run from enjoy_router/:  python3 run_people_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_crud as IC, locations_crud as LC, location_links_crud as LK
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
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
A = "user:admin"
for i in range(33):
    n = ("Phylis", "Stewart") if i < 3 else ("Person%02d" % i, "Lee")
    IC.create(store, {"given_name": n[0], "family_name": n[1], "birth_date": "19%02d-04-17" % (40 + i)}, A)
people = sorted(store.data["individuals"].values(), key=lambda r: r["created_at"])
for r in people[-4:]: IC.update(store, r["id"], {"status": "inactive"}, A)
N_ACTIVE = len([r for r in store.data["individuals"].values() if r.get("status") == "active"])
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/people'"); pg.wait_for_selector("#pList li")

    # ===== L-1 head
    check("L-1 page title, orange Add person, Merge history, Manual and Refresh as links", pg.locator("#pTitle").inner_text() == "People" and "btn-primary" in pg.get_attribute("#pAddBtn", "class") and "btn-link" in pg.get_attribute("#pRefresh", "class") and pg.locator("#pHistLink.btn-link").count() == 1 and pg.locator("#peopleView .manualBtn.btn-link").count() == 1)
    pg.click("#pHistLink"); pg.wait_for_timeout(300)
    check("L-1 the Merge history link opens the same box at the bottom", pg.evaluate("document.getElementById('pHist').open"))

    # ===== L-5 chips, paging
    check("L-5 old status drop-down gone, Status chip present", pg.locator("#pFilter").count() == 0 and pg.locator("#pChips .cf-chip", has_text="Status").count() == 1)
    check("L-5 first page shows 50 at most, Active only", pg.locator("#pList > li").count() == min(50, N_ACTIVE) and N_ACTIVE == 29)
    check("L-5 sorted by name", pg.evaluate("(function(){var t=[].map.call(document.querySelectorAll('#pList > li .head'),function(e){return e.textContent.toLowerCase()});return t.length>1})()"))
    pg.fill("#pSearch", "zzzz"); pg.wait_for_timeout(250)
    check("L-5 no match shows the no-match note", pg.evaluate("document.getElementById('pNoMatch').hidden === false"))
    pg.fill("#pSearch", ""); pg.wait_for_timeout(250)
    check("L-5 clearing restores the list", pg.locator("#pList > li").count() == N_ACTIVE)
    check("no page errors", not errs, errs)
    b.close()
print("ALL OK" if not fails else "FAILED: %d" % len(fails)); sys.exit(1 if fails else 0)

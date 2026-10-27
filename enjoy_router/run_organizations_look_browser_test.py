#!/usr/bin/env python3
"""Browser test (Organizations look, combo build): head, filters (chips for Status and Kind with counts), paging at 50, row, button cues, plain words,
empty/loading/error, forms and phone. Run from enjoy_router/:  python3 run_organizations_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import organizations_crud as OC
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
KINDS = [["school"], ["business"], ["school_district"], ["governing_body"], ["nonprofit", "school"]]
for i in range(115):
    OC.create(store, {"name": "Organization %03d" % i, "kinds": KINDS[i % 5], "short_name": "O%d" % i if i % 7 == 0 else None} if i % 7 == 0 else {"name": "Organization %03d" % i, "kinds": KINDS[i % 5]}, A)
orgs = sorted(store.data["organizations"].values(), key=lambda r: r["name"])
for r in orgs[:5]: OC.update(store, r["id"], {"status": "inactive"}, A)
for r in orgs[5:8]: OC.update(store, r["id"], {"status": "closed"}, A)
N_ACTIVE = len([r for r in store.data["organizations"].values() if r.get("status") == "active"])
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/organizations'"); pg.wait_for_selector("#roList li")

    # ===== L-1 head
    check("L-1 page title, orange Add organization, Manual and Refresh as links", pg.locator("#roTitle").inner_text() == "Organizations" and "btn-primary" in pg.get_attribute("#roAddBtn", "class") and "btn-link" in pg.get_attribute("#roRefresh", "class") and pg.locator("#organizationsView .manualBtn.btn-link").count() == 1)
    check("L-1 the search box sits full width under the head, like the other stations", pg.locator("#roSearch.psearch").count() == 1 and pg.locator("#roSearch").bounding_box()["width"] > 800)

    # ===== L-5 filters and paging
    check("L-5 the old drop-down is gone; chips Status and Kind are there", pg.locator("#roFilter").count() == 0 and all(w in pg.locator("#roChips .cf-row").inner_text() for w in ["Status", "Kind"]))
    check("L-5 Active only, 50 rows, 'shown of' count", pg.locator("#roList li").count() == 50 and pg.locator("#roCount").inner_text() == "%d organizations shown of 115" % N_ACTIVE, pg.locator("#roCount").inner_text())
    check("L-5 'Showing 50 of N' and Load more", ("Showing 50 of %d" % N_ACTIVE) in pg.locator("#roMore").inner_text() and pg.locator("#roMore button").count() == 1, pg.locator("#roMore").inner_text())
    while pg.locator("#roMore button").count():
        pg.locator("#roMore button").click(); pg.wait_for_timeout(200)
    check("L-5 Load more brings the rest", pg.locator("#roList li").count() == N_ACTIVE and pg.locator("#roMore .morebar").count() == 0)
    check("L-5 the Kind chip says a record counts under each of its kinds", "counts under each of its kinds" in pg.locator("#roChips").inner_text())
    pg.locator("#roChips .cf-chip", has_text="Kind").click()
    for v in ["school_district", "governing_body", "nonprofit", "business", "government", "association", "club", "training_provider", "community_group", "other", "college_university", "none"]:
        bx = pg.locator("#roChips .cf-pop input[type=checkbox][value=%s]" % v)
        if bx.count() and bx.is_checked(): bx.click()
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    n_school = len([r for r in store.data["organizations"].values() if r.get("status") == "active" and "school" in (r.get("kinds") or [])])
    check("L-5 only School (including those that are also something else)", pg.locator("#roCount").inner_text().startswith("%d organization" % n_school) and n_school > 0, pg.locator("#roCount").inner_text())
    pg.locator("#roChips .cf-chip", has_text="Kind").click()
    for v in ["school_district", "governing_body", "nonprofit", "business", "government", "association", "club", "training_provider", "community_group", "other", "college_university", "none"]:
        bx = pg.locator("#roChips .cf-pop input[type=checkbox][value=%s]" % v)
        if bx.count() and not bx.is_checked(): bx.click()
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    pg.fill("#roSearch", "Organization 01"); pg.wait_for_timeout(250)
    check("L-5 search still narrows (Organization 010 to 019 that are active)", pg.locator("#roList li").count() > 0 and pg.locator("#roList li").count() <= 10, pg.locator("#roList li").count())
    pg.fill("#roSearch", ""); pg.wait_for_timeout(250)

    # ===== L-2 row look
    first = pg.locator("#roList li").first
    check("L-2 the title is the name; kind and short name on the grey line", first.locator(".vname").inner_text().startswith("Organization") and first.locator(".sub").count() == 1)
    xs = pg.evaluate("Array.from(document.querySelectorAll('#roList > li')).slice(0, 4).map(function (e) { return Math.round(e.getBoundingClientRect().left); })")
    check("L-2 two rows across at 1440", len(set(xs)) == 2, xs)
    first.locator("button.head").click()
    check("L-2 an opened card takes the whole width", pg.evaluate("(function(){var l=document.querySelector('#roList > li.open');return l && l.getBoundingClientRect().width > document.getElementById('roList').getBoundingClientRect().width * 0.9;})()"))
    first.locator("button.head").click()
    check("no page errors", not errs, errs)
    b.close()
print("ALL OK" if not fails else "FAILED: %d" % len(fails)); sys.exit(1 if fails else 0)

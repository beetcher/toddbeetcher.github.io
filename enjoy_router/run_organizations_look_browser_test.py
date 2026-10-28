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
OC.create(store, {"name": "Zzz Plain Words Co", "kinds": ["business"], "identifiers": [{"type": "ein", "value": "00-0000000"}], "founded_date": "1999-04-17", "closed_date": "2005"}, A)
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
    check("L-5 Active only, 50 rows, 'shown of' count", pg.locator("#roList li").count() == 50 and pg.locator("#roCount").inner_text() == "%d organizations shown of 116" % N_ACTIVE, pg.locator("#roCount").inner_text())
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

    # ===== L-3 button cues
    first.locator("button.head").click()
    row = first.locator(".actions-row").first
    check("L-3 Edit is the one orange button and comes first; Delete is red and last", row.locator("button.btn-primary").count() == 1 and row.locator("button").first.inner_text() == "Edit" and row.locator("button").last.inner_text() == "Delete" and "btn-danger" in (row.locator("button").last.get_attribute("class") or ""))
    hs = pg.evaluate("Array.from(document.querySelectorAll('#roList li.open .actions-row')[0].querySelectorAll('button')).map(function (b) { return Math.round(b.getBoundingClientRect().height); })")
    check("L-3 one height (40 px) on the card's main buttons", len(set(hs)) == 1 and hs[0] == 40, hs)
    first.locator("button.head").click()

    # ===== L-4 plain words in the card
    pg.fill("#roSearch", "Zzz Plain"); pg.wait_for_timeout(250)
    pw = pg.locator("#roList li", has_text="Zzz Plain Words Co"); pw.locator("button.head").click()
    ptxt = pw.inner_text()
    check("L-4 identifier and dates in plain words", "EIN (tax number): 00-0000000" in ptxt and "Founded: Apr 17, 1999" in ptxt and "Closed: 2005" in ptxt and "ein:" not in ptxt and "1999-04-17" not in ptxt, ptxt)
    pw.locator("button.head").click()

    # ===== L-7 empty, loading, error states
    pg.fill("#roSearch", "zzzzzz"); pg.wait_for_timeout(250)
    check("L-7 no match says what to do and offers to clear", pg.locator("#roNoMatch").is_visible() and "No organization matches that." in pg.locator("#roNoMatch").inner_text())
    pg.click("#roClear"); pg.wait_for_timeout(300)
    check("L-7 clearing brings the list back", pg.locator("#roNoMatch").is_hidden() and pg.locator("#roSearch").input_value() == "" and pg.locator("#roList li").count() > 0)
    flaky = {"on": True}
    def drop(route):
        q = route.request
        if q.method != "OPTIONS" and flaky["on"] and "organizations" in (q.post_data or "") and '"op":"list"' in (q.post_data or "").replace(" ", ""):
            route.fulfill(status=500, headers=CORS, body=json.dumps({"ok": False})); return
        admin_route(route)
    pg.unroute("**/enjoy_admin"); pg.route("**/enjoy_admin", drop)
    pg.click("#roRefresh"); pg.wait_for_selector("#roRetry:not([hidden])")
    check("L-7 a failed load says so and offers Try again", "Could not load the organizations" in pg.locator("#roMsg").inner_text() and pg.locator("#roRetry").inner_text() == "Try again")
    flaky["on"] = False; pg.click("#roRetry"); pg.wait_for_function("document.getElementById('roRetry').hidden && document.querySelectorAll('#roList li').length > 0")
    check("L-7 Try again loads the list", pg.locator("#roList li").count() > 0)

    # ===== L-8 forms
    pg.click("#roAddBtn"); pg.wait_for_selector("#roAddFields .fsec")
    check("L-8 the Add form has sections and a red star on Name only", [h.lower() for h in pg.locator("#roAddFields .fsec").all_inner_texts()] == ["who it is", "how to reach it"] and pg.locator("#roAddFields .req").count() == 1 and pg.get_attribute("#roA_name", "aria-required") == "true")
    kb = pg.locator("#roA_kinds").bounding_box(); k0 = pg.locator("#roA_kinds label").nth(0).bounding_box(); k1 = pg.locator("#roA_kinds label").nth(1).bounding_box()
    check("L-8 the twelve kinds sit in a grid, not one long run", abs(k0["y"] - k1["y"]) < 4 and kb["height"] < 12 * 30, (kb, k0, k1))
    pg.click("#roSaveBtn"); pg.wait_for_timeout(200)
    check("L-8 an empty Name says Required right under the box", pg.locator("#roAddFields .ferr").first.inner_text() == "Required.")
    sb, cb = pg.locator("#roSaveBtn").bounding_box(), pg.locator("#roCancelBtn").bounding_box()
    check("L-8 Save and Cancel sit together, Save orange", abs(sb["y"] - cb["y"]) < 4 and "btn-primary" in pg.get_attribute("#roSaveBtn", "class"))
    pg.click("#roCancelBtn")

    # ===== L-6 links panel
    lp = pg.locator("#roList li").first; lp.locator("button.head").click()
    check("L-6 the links panel has two labelled groups, outlined buttons", [h.lower() for h in lp.locator(".olinks .dgh").all_inner_texts()] == ["links to people, venues and organizations", "places"] and lp.locator(".olinks button.btn-secondary").count() == 4 and lp.locator(".olinks button.quiet").count() == 0)
    check("L-6 the four buttons keep their words", lp.locator(".olinks button").all_inner_texts() == ["Show links", "Add link", "Show places", "Add place"], lp.locator(".olinks button").all_inner_texts())
    lp.locator("button.head").click()

    # ===== L-9 phone pass (390 px)
    ph = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    ph.route("**/enjoy_admin", admin_route); ph.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    ph.goto(PAGE); ph.fill("#keyInput", KEY); ph.click("#unlockBtn"); ph.wait_for_selector("#homeView:not([hidden])")
    ph.evaluate("location.hash='#/organizations'"); ph.wait_for_selector("#roList li")
    ph.locator("#roList li button.head").first.click(); ph.wait_for_timeout(300)
    check("L-9 no sideways scrolling at 390", ph.evaluate("document.documentElement.scrollWidth") <= 390)
    small = ph.evaluate("Array.from(document.querySelectorAll('#organizationsView button, #organizationsView select, #organizationsView input:not([type=checkbox])')).filter(function (e) { var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 44 && !e.closest('[hidden]'); }).map(function (e) { return (e.id || e.className) + ':' + Math.round(e.getBoundingClientRect().height); })")
    check("L-9 every button and box on the page is at least 44 px tall", not small, small)
    ph.click("#roAddBtn"); ph.wait_for_selector("#roAddFields .kindgrid")
    check("L-9 the Add form fits and the kind boxes are 44 px tall on a phone", ph.evaluate("document.documentElement.scrollWidth") <= 390 and ph.evaluate("Math.round(document.querySelector('#roA_kinds label').getBoundingClientRect().height)") >= 44)
    ph.click("#roCancelBtn")
    check("L-9 the page is far shorter than before (was 10,151 px at 1440 and 13,072 at 390)", ph.evaluate("document.documentElement.scrollHeight") < 9000, ph.evaluate("document.documentElement.scrollHeight"))
    check("no page errors", not errs, errs)
    b.close()
print("ALL OK" if not fails else "FAILED: %d" % len(fails)); sys.exit(1 if fails else 0)

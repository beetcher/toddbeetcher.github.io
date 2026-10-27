#!/usr/bin/env python3
"""Browser test (Places look, combo build): filters (chips for Status, State and "Needs a time zone"), paging at 50, then (as the steps land) the row,
button cues, plain words, detail, states, forms and phone. Run from enjoy_router/:  python3 run_places_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import locations_crud as LC
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SHOTS = pathlib.Path(os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="places_look_")); SHOTS.mkdir(parents=True, exist_ok=True)
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
CITY = [("Boulder", "CO", "80301"), ("Rochester", "MN", "55901"), ("Madison", "WI", "53703")]
for i in range(83):
    c = CITY[i % 3]
    d = {"name": ("Panera Bread cafe number %d" % i) if i % 3 == 0 else "Site %d" % i, "kind": "site",
         "addresses": [{"usage": "civic", "street_number": str(100 + i), "street": "Main Street", "locality": c[0], "region": c[1], "postal_code": c[2], "country": "US"}]}
    rec = LC.create(store, d, A).data
    if i % 4 == 0: store.data["locations"][rec["id"]].pop("time_zone", None)   # create fills the zone from the ZIP; take it off so some places need one
retired = [r for r in store.data["locations"].values()][:5]
for r in retired: LC.update(store, r["id"], {"status": "retired"}, A)
NO_TZ_ACTIVE = len([r for r in store.data["locations"].values() if r.get("status") == "active" and not r.get("time_zone")])
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/places'"); pg.wait_for_selector("#lList li")
    total_active = len([r for r in store.data["locations"].values() if r.get("status") == "active"])

    # ===== L-5 filters and paging
    check("L-5 the old Active/Retired drop-down is gone and a chip row is there", pg.locator("#lFilter").count() == 0 and pg.locator("#lChips .cf-row").count() == 1)
    chips_text = pg.locator("#lChips .cf-row").inner_text()
    check("L-5 chips: Status, State, Needs a time zone", all(w in chips_text for w in ["Status", "State", "Needs a time zone"]), chips_text)
    check("L-5 Active places only to begin with, 50 rows shown", pg.locator("#lList li").count() == 50 and pg.locator("#lCount").inner_text() == "%d places" % total_active, pg.locator("#lCount").inner_text())
    check("L-5 'Showing 50 of N places' and a Load more button", pg.locator("#lMore .morebar").count() == 1 and ("Showing 50 of %d places" % total_active) in pg.locator("#lMore").inner_text() and pg.get_by_role("button", name="Load 24 more").count() == 1 if total_active - 50 == 24 else pg.locator("#lMore button").count() == 1, pg.locator("#lMore").inner_text())
    pg.locator("#lMore button").click()
    check("L-5 Load more shows everything left and the bar goes", pg.locator("#lList li").count() == total_active and pg.locator("#lMore .morebar").count() == 0)
    check("L-5 the count line says how many of how many once narrowed", ("%d of 83 places" % total_active) in pg.locator("#lChips").inner_text(), pg.locator("#lChips").inner_text())
    pg.locator("#lChips .cf-chip", has_text="Needs a time zone").click(); pg.wait_for_timeout(200)
    check("L-5 the switch carries the number of places that need a zone", NO_TZ_ACTIVE > 0 and pg.locator("#lChips .cf-chip", has_text="Needs a time zone").inner_text().strip().endswith(str(len([r for r in store.data["locations"].values() if not r.get("time_zone")]))), pg.locator("#lChips .cf-chip", has_text="Needs a time zone").inner_text())
    check("L-5 'Needs a time zone' keeps only places with no zone", pg.locator("#lCount").inner_text() == "%d places" % NO_TZ_ACTIVE, pg.locator("#lCount").inner_text())
    pg.locator("#lChips .cf-chip", has_text="Needs a time zone").click(); pg.wait_for_timeout(200)
    pg.locator("#lChips .cf-chip", has_text="Status").click(); pg.wait_for_timeout(200)
    pg.locator("input[type=checkbox][value=retired]").check(); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("L-5 ticking Retired adds the 5 retired places", pg.locator("#lCount").inner_text() == "%d places" % (total_active + 5), pg.locator("#lCount").inner_text())
    pg.fill("#lSearch", "Panera"); pg.wait_for_timeout(200)
    n_pan = len([r for r in store.data["locations"].values() if "Panera" in r.get("name", "")])
    check("L-5 search still narrows the list", pg.locator("#lCount").inner_text() == "%d places" % n_pan, pg.locator("#lCount").inner_text())

    # ===== L-2 row look
    pg.fill("#lSearch", ""); pg.wait_for_timeout(200)
    pg.locator("#lChips .cf-chip", has_text="Status").click(); pg.locator("input[type=checkbox][value=retired]").uncheck(); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    first = pg.locator("#lList li").first
    check("L-2 the title is the name alone", "·" not in first.locator(".vname").inner_text() and first.locator(".vname").inner_text().startswith(("Panera", "Site")), first.locator(".vname").inner_text())
    check("L-2 the address sits on a grey line under the name", first.locator(".paddr").count() == 1 and "Main Street" in first.locator(".paddr").inner_text())
    check("L-2 the kind is in plain words, never the raw word", "Building or campus" in first.inner_text() and "\nsite" not in first.inner_text().lower() + "")
    xs = pg.evaluate("Array.from(document.querySelectorAll('#lList > li')).slice(0, 4).map(function (e) { return Math.round(e.getBoundingClientRect().left); })")
    check("L-2 two rows across at 1440", len(set(xs)) == 2, xs)
    first.locator("button.head").click()
    check("L-2 an opened card takes the whole width", pg.evaluate("(function(){var l=document.querySelector('#lList > li.open');return l && l.getBoundingClientRect().width > document.getElementById('lList').getBoundingClientRect().width * 0.9;})()"))
    first.locator("button.head").click()

    # ===== L-3 button cues
    first.locator("button.head").click()
    row = first.locator(".actions-row").first
    check("L-3 one orange button (Edit), first", row.locator("button.btn-primary").count() == 1 and row.locator("button").first.inner_text() == "Edit")
    check("L-3 no more than three outlined buttons", row.locator("button.btn-secondary").count() == 3, row.locator("button.btn-secondary").all_inner_texts())
    check("L-3 Delete is red and the last button", row.locator("button").last.inner_text() == "Delete" and "btn-danger" in (row.locator("button").last.get_attribute("class") or ""))
    check("L-3 History is a plain link", row.locator("button.btn-link", has_text="Change history").count() == 1)
    hs = pg.evaluate("Array.from(document.querySelectorAll('#lList li.open .actions-row button')).map(function (b) { return Math.round(b.getBoundingClientRect().height); })")
    check("L-3 one height (40 px) across the buttons", len(set(hs)) == 1 and hs[0] == 40, hs)
    first.locator("button.head").click()

    # ===== L-4 plain words in the card
    first.locator("button.head").click()
    txt = first.inner_text()
    check("L-4 the card shows no raw field names or ids", not any(w in txt for w in ["time_zone", "part_of_location_id", "aliases", "kind:", "America/", "id:"]) and "loc_" not in txt, txt)
    check("L-4 the time zone is a plain name (or says not set yet)", ("Time zone: Mountain" in txt or "Time zone: Eastern" in txt or "Time zone: Central" in txt) or "Time zone: Not set yet" in txt, txt)
    check("L-4 an address line says what kind it is", "Street address" in txt, txt)
    first.locator("button.head").click()

    # ===== L-6 detail groups
    first.locator("button.head").click()
    heads = [h.lower() for h in first.locator(".dgh").all_inner_texts()]
    check("L-6 the card has Addresses, Details and Linked to groups", heads[0] == "addresses" and "details" in heads and heads[-1] == "linked to", heads)
    check("L-6 time zone sits under Details, who is linked under Linked to", first.locator(".dgroup", has_text="Time zone").locator(".dgh").inner_text().lower() == "details" and first.locator(".dgroup", has_text="Show who is linked here").locator(".dgh").inner_text().lower() == "linked to")
    first.locator("button.head").click()

    # ===== L-7 empty, loading, error states
    pg.fill("#lSearch", "zzzzzz"); pg.wait_for_timeout(200)
    check("L-7 no match says what to do and offers to clear", pg.locator("#lNoMatch").is_visible() and "No place matches that." in pg.locator("#lNoMatch").inner_text() and pg.locator("#lClear").is_visible())
    pg.click("#lClear"); pg.wait_for_timeout(300)
    check("L-7 clearing brings the list back (Active, no search)", pg.locator("#lNoMatch").is_hidden() and pg.locator("#lSearch").input_value() == "" and pg.locator("#lList li").count() > 0)
    flaky = {"on": True}
    def drop(route):
        q = route.request
        if q.method != "OPTIONS" and flaky["on"] and '"op":"list"' in (q.post_data or "").replace(" ", "") and "locations" in (q.post_data or ""):
            route.fulfill(status=500, headers=CORS, body=json.dumps({"ok": False})); return
        admin_route(route)
    pg.unroute("**/enjoy_admin"); pg.route("**/enjoy_admin", drop)
    pg.click("#lRefresh"); pg.wait_for_selector("#lRetry:not([hidden])")
    check("L-7 a failed load says so and offers Try again", "Could not load the places" in pg.locator("#lMsg").inner_text() and pg.locator("#lRetry").inner_text() == "Try again")
    flaky["on"] = False; pg.click("#lRetry"); pg.wait_for_function("document.getElementById('lRetry').hidden && document.querySelectorAll('#lList li').length > 0")
    check("L-7 Try again loads the list", pg.locator("#lList li").count() > 0)

    # ===== L-8 forms
    pg.click("#lAddBtn"); pg.wait_for_selector("#lAddFields .fsec")
    secs = [h.lower() for h in pg.locator("#lAddFields .fsec").all_inner_texts()]
    check("L-8 the Add form has sections", secs == ["about the place", "address", "map point (optional)", "time zone"], secs)
    check("L-8 it says at least one of name, street or GPS is needed", "at least one of" in pg.locator("#lAddFields").inner_text())
    city, state, street = [pg.locator("#lAddFields").get_by_label(n, exact=True).bounding_box() for n in ("City", "State", "Street address")]
    check("L-8 City and State sit side by side on a wide screen, street address takes the full row", abs(city["y"] - state["y"]) < 4 and street["width"] > city["width"] * 1.6, (city, state, street))
    check("L-8 time zone is a drop-down with plain names", pg.locator("#lAddFields").get_by_label("Time zone (optional)").inner_text().count("Mountain") == 1)
    sb, cb = pg.locator("#lSaveBtn").bounding_box(), pg.locator("#lCancelBtn").bounding_box()
    check("L-8 Save and Cancel sit together", abs(sb["y"] - cb["y"]) < 4 and cb["x"] - (sb["x"] + sb["width"]) < 40)
    pg.click("#lCancelBtn")

    # ===== L-9 phone pass (390 px)
    ph = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    ph.route("**/enjoy_admin", admin_route); ph.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    ph.goto(PAGE); ph.fill("#keyInput", KEY); ph.click("#unlockBtn"); ph.wait_for_selector("#homeView:not([hidden])")
    ph.evaluate("location.hash='#/places'"); ph.wait_for_selector("#lList li")
    ph.locator("#lList li button.head").first.click(); ph.wait_for_timeout(300)
    check("L-9 no sideways scrolling at 390", ph.evaluate("document.documentElement.scrollWidth") <= 390)
    small = ph.evaluate("Array.from(document.querySelectorAll('#placesView button, #placesView select, #placesView input')).filter(function (e) { var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 44 && !e.closest('[hidden]'); }).map(function (e) { return (e.id || e.className) + ':' + Math.round(e.getBoundingClientRect().height); })")
    check("L-9 every button and box on the page is at least 44 px tall", not small, small)
    check("L-9 the phone header is one short row", ph.evaluate("document.getElementById('topbar').offsetHeight") <= 64, ph.evaluate("document.getElementById('topbar').offsetHeight"))
    check("L-9 the page is much shorter than before (paged at 50)", ph.evaluate("document.documentElement.scrollHeight") < 9000, ph.evaluate("document.documentElement.scrollHeight"))
    check("no page errors", not errs, errs)
    b.close()
print("ALL OK" if not fails else "FAILED: %d" % len(fails)); sys.exit(1 if fails else 0)

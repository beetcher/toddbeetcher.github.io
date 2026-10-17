#!/usr/bin/env python3
"""Browser test: the State and Region filters on the Console Venues list. Real admin door over an in-memory store, real venue and place
handlers, headless Chromium. Nothing leaves this computer.
Run from enjoy_router/:  python3 run_venue_filter_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timedelta, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import venues_service as VS
from crud_endpoint import handle_admin
from console import make_failure_limiter
from launch_discovery import zip_table
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
fails, total = [], [0]
def check(label, ok, detail=""):
    total[0] += 1
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

zip_table.set_table({"55802": ["MN", 46.78, -92.1, "Duluth"], "55806": ["MN", 46.77, -92.08, "Duluth"], "55976": ["MN", 43.85, -92.49, "Stewartville"],
                     "55901": ["MN", 44.0, -92.46, "Rochester"], "80302": ["CO", 40.0, -105.3, "Boulder"], "80501": ["CO", 40.16, -105.1, "Longmont"],
                     "78701": ["TX", 30.2, -97.7, "Austin"]})
store, limiter = MemoryDocStore(""), make_failure_limiter()
clock = [0]
def tick():
    clock[0] += 3
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=clock[0])
def call(coll, op, **args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter, tick())
    return r.status, r.body
def area(**kw):
    r = call("discovery_areas", "create", data=kw, source="import")
    assert r[0] == 200, (kw, r[1])
for code, name, on in (("MN", "Minnesota", True), ("CO", "Colorado", True), ("TX", "Texas", False)):
    area(kind="state", state_code=code, name=name, is_active=on)
area(kind="region", state_code="MN", name="Duluth MN", zip_codes=["55802", "55806"], is_active=True)
area(kind="region", state_code="MN", name="Rochester MN", zip_codes=["55901"], is_active=True)
area(kind="region", state_code="MN", name="Stewartville MN", zip_codes=["55976"], is_active=True)
area(kind="region", state_code="MN", name="Old Duluth idea", zip_codes=["55802"], is_active=False)
area(kind="region", state_code="CO", name="Boulder", zip_codes=["80302"], is_active=True)
area(kind="region", state_code="TX", name="Austin", zip_codes=["78701"], is_active=True)     # its state is switched off
def venue(name, city, state, zip_, status="inactive"):
    addr = {"usage": "civic", "is_primary": True, "locality": city, "region": state, "country": "US", "street_number": "1", "street": "Main St"}
    if zip_: addr["postal_code"] = zip_
    r = VS.create_with_place(store, {"name": name, "slug": name.lower().replace(" ", "_"), "status": "inactive", "is_public_venue": True}, "system:test", address=addr, source="import", now=tick())
    assert r.ok, (name, r.problems)
    if status == "active":                       # an active venue needs rooms, contacts and more; the filter test only needs the status word
        store.data["venues"][r.data["id"]]["status"] = "active"
venue("Dovetail Cafe", "Duluth", "MN", "55806"); venue("Duluth Coffee", "Duluth", "MN", "55802", "active")
venue("Darlin Bakery", "Stewartville", "MN", "55976"); venue("Rochester Roast", "Rochester", "MN", "55901")
venue("Minnesota No ZIP", "Duluth", "MN", None)
venue("Trident", "Boulder", "CO", "80302"); venue("Longmont Beans", "Longmont", "CO", "80501"); venue("Austin Cup", "Austin", "TX", "78701")

def admin_route(route):
    q = route.request; H = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**H, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, tick())
    route.fulfill(status=r.status, headers=H, body=json.dumps(r.body))

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1000}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "venues"); pg.wait_for_function("document.getElementById('vChecked').textContent.length > 0")
    names = lambda: sorted(pg.locator("#vList > li .name, #vList > li h3, #vList > li b").first.evaluate_all("x => []") or [])
    def shown():
        return sorted(pg.locator("#vList > li").evaluate_all("els => els.map(e => e.innerText.split('\\n')[0].trim())"))
    count = lambda: pg.inner_text("#vCount")
    check("all venues show by default, with a plain count", len(shown()) == 8 and count() == "8 venues", (shown(), count()))
    sopts = pg.locator("#vState option").all_inner_texts()
    check("the State list is All states plus ONLY the states switched on, by name", sopts == ["All states", "Colorado", "Minnesota"], sopts)
    ropts = pg.locator("#vRegion option").all_inner_texts()
    groups = pg.locator("#vRegion optgroup").evaluate_all("g => g.map(x => [x.label, [...x.querySelectorAll('option')].map(o => o.textContent)])")
    check("the Region list is grouped by state and has only regions that are switched on, in switched-on states",
          groups == [["Colorado", ["Boulder"]], ["Minnesota", ["Duluth MN", "Rochester MN", "Stewartville MN"]]] and ropts[0] == "All regions", groups)
    pg.select_option("#vState", "MN")
    check("a state shows every venue in that state, even one with no ZIP", len(shown()) == 5 and count() == "Showing 5 of 8 venues" and "Minnesota No ZIP" in shown(), (shown(), count()))
    groups = pg.locator("#vRegion optgroup").evaluate_all("g => g.map(x => x.label)")
    check("choosing a state narrows the region list to that state", groups == ["Minnesota"], groups)
    pg.select_option("#vRegion", label="Duluth MN")
    check("a region shows only the venues whose ZIP is on its list", shown() == ["Dovetail Cafe", "Duluth Coffee"] and count() == "Showing 2 of 8 venues", (shown(), count()))
    check("a venue in the state with no ZIP is not in any region", "Minnesota No ZIP" not in shown())
    pg.select_option("#vState", "CO")
    check("changing the state clears a region that no longer fits", pg.input_value("#vRegion") == "" and len(shown()) == 2, (pg.input_value("#vRegion"), shown()))
    pg.select_option("#vState", ""); pg.select_option("#vRegion", label="Boulder")
    check("a region works without picking a state first", shown() == ["Trident"], shown())
    pg.select_option("#vRegion", ""); pg.select_option("#vState", "MN"); pg.select_option("#vRegion", label="Stewartville MN")
    check("a one-ZIP region", shown() == ["Darlin Bakery"], shown())
    pg.select_option("#vRegion", label="Duluth MN"); pg.select_option("#vFilter", "inactive"); pg.wait_for_function("document.getElementById('vCount').textContent.indexOf('of 7') > 0")
    check("State, Region and Status combine: Minnesota + Duluth + Inactive is the review pile", shown() == ["Dovetail Cafe"] and count() == "Showing 1 of 7 venues", (shown(), count()))
    pg.select_option("#vRegion", label="Rochester MN"); pg.select_option("#vFilter", "active"); pg.wait_for_function("document.getElementById('vCount').textContent.indexOf('of 1') > 0")
    check("a filter that matches nothing says so", pg.locator("#vEmpty").is_visible() and "match these filters" in pg.inner_text("#vEmpty") and shown() == [], pg.inner_text("#vEmpty"))
    pg.select_option("#vFilter", ""); pg.select_option("#vState", ""); pg.select_option("#vRegion", ""); pg.wait_for_function("document.getElementById('vCount').textContent === '8 venues'")
    check("back to All shows everything again", len(shown()) == 8 and not pg.locator("#vEmpty").is_visible())
    def refresh():
        with pg.expect_response(lambda r: "enjoy_admin" in r.url and "discovery_areas" in (r.request.post_data or "")):
            pg.click("#vRefresh")
        pg.wait_for_timeout(400)
    pg.select_option("#vState", "MN"); pg.select_option("#vRegion", label="Duluth MN"); refresh()
    check("Refresh keeps your State and Region choices", pg.input_value("#vState") == "MN" and shown() == ["Dovetail Cafe", "Duluth Coffee"], (pg.input_value("#vState"), shown()))
    area(kind="region", state_code="MN", name="Aaa newest region", zip_codes=["55976"], is_active=True)
    refresh(); pg.wait_for_function("document.getElementById('vRegion').textContent.indexOf('Aaa newest') >= 0")
    check("Refresh also picks up a region made since, listed alphabetically in its state", pg.locator("#vRegion optgroup").first.locator("option").first.inner_text() == "Aaa newest region" and pg.input_value("#vRegion") != "")
    pg.select_option("#collPick", "home"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "venues"); pg.wait_for_function("document.getElementById('vChecked').textContent.length > 0 && document.getElementById('vCount').textContent.length > 0")
    check("leaving Venues and coming back keeps your State and Region choices (like the status filter)", pg.input_value("#vState") == "MN" and pg.input_value("#vRegion") != "" and shown() == ["Dovetail Cafe", "Duluth Coffee"], (pg.input_value("#vState"), shown()))
    pg.click("#lockBtn"); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#lockView", state="hidden")
    if pg.locator("#venuesView").count() and not pg.locator("#venuesView").is_visible(): pg.select_option("#collPick", "venues")
    pg.wait_for_function("document.getElementById('vCount').textContent.length > 0")
    check("locking the Console clears them: back to All states / All regions", pg.input_value("#vState") == "" and pg.input_value("#vRegion") == "" and len(shown()) == 8, (pg.input_value("#vState"), pg.input_value("#vRegion"), shown()))
    check("the page raised no errors", not errors, errors)
    b.close()
print(f"\n{total[0] - len(fails)}/{total[0]} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)

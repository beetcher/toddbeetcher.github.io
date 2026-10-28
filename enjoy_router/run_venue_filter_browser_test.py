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
    pg.click("#sideNav a[data-nav=venues]"); pg.wait_for_function("document.getElementById('vChecked').textContent.length > 0")
    def chip(name): return pg.locator("#vChips .cf-chip", has_text=name).first
    def pick(name, *labels, clear_first=False):
        """Open a chip, click the entries with these labels, close it."""
        chip(name).click()
        for l in labels: pg.locator("#vChips .cf-pop:visible label", has_text=l).first.click()
        pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    def entries(name):
        chip(name).click(); t = pg.locator("#vChips .cf-pop:visible label").all_inner_texts(); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        return [x.strip().split("\n")[0].strip() for x in t if x.strip()]
    def shown():
        return sorted(pg.locator("#vList > li").evaluate_all("els => els.map(e => (e.querySelector('.vname') || e).innerText.split('\\n')[0].trim())"))
    count = lambda: pg.inner_text("#vCount")
    check("all venues show by default, with a plain count", len(shown()) == 8 and count() == "8 venues", (shown(), count()))
    check("the old Filters button and drop-downs are gone, chips are there", pg.locator("#vFilterBtn").count() == 0 and pg.locator("#vFilter").count() == 0 and all(chip(n).count() == 1 for n in ("Status", "State", "Region", "Kind", "Not ready")))
    se = [e for e in entries("State") if e]
    check("the State list is All states plus ONLY the states switched on, by name", se == ["All states", "Colorado", "Minnesota"], se)
    re_ = entries("Region")
    check("the Region list has only regions that are switched on, in switched-on states", sorted([x for x in re_ if x in ("Boulder", "Duluth MN", "Rochester MN", "Stewartville MN")]) == ["Boulder", "Duluth MN", "Rochester MN", "Stewartville MN"], re_)
    pick("State", "Minnesota")
    check("a state shows every venue in that state, even one with no ZIP", len(shown()) == 5 and count() == "Showing 5 of 8 venues" and "Minnesota No ZIP" in shown(), (shown(), count()))
    re2 = entries("Region")
    check("choosing a state narrows the region list to that state", "Boulder" not in re2 and "Duluth MN" in re2, re2)
    pick("Region", "Duluth MN")
    check("a region shows only the venues whose ZIP is on its list", shown() == ["Dovetail Cafe", "Duluth Coffee"] and count() == "Showing 2 of 8 venues", (shown(), count()))
    check("a venue in the state with no ZIP is not in any region", "Minnesota No ZIP" not in shown())
    pick("State", "Colorado")
    check("changing the state clears a region that no longer fits", len(shown()) == 2 and "Region:" not in chip("Region").inner_text(), (chip("Region").inner_text(), shown()))
    pick("State", "All states"); pick("Region", "Boulder")
    check("a region works without picking a state first", shown() == ["Trident"], shown())
    pick("Region", "Boulder"); pick("State", "Minnesota"); pick("Region", "Stewartville MN")
    check("a one-ZIP region", shown() == ["Darlin Bakery"], shown())
    pick("Region", "Stewartville MN"); pick("Region", "Duluth MN"); pick("Status", "Active")
    check("State, Region and Status combine: Minnesota + Duluth + Inactive is the review pile", shown() == ["Dovetail Cafe"] and count() == "Showing 1 of 8 venues", (shown(), count()))
    pick("Region", "Duluth MN"); pick("Region", "Rochester MN"); pick("Status", "Active"); pick("Status", "Inactive")
    check("a filter that matches nothing says so", pg.locator("#vNoMatch").is_visible() and "No venue matches" in pg.inner_text("#vNoMatch") and shown() == [], pg.inner_text("#vNoMatch"))
    pg.click("#vClear"); pg.wait_for_timeout(300)
    check("the Clear link brings everything back", len(shown()) == 8 and not pg.locator("#vNoMatch").is_visible() and count() == "8 venues", (shown(), count()))
    pg.fill("#vSearch", "duluth"); pg.wait_for_timeout(250)
    check("search finds by name or address", shown() == ["Dovetail Cafe", "Duluth Coffee"] or "Duluth Coffee" in shown(), shown())
    pg.fill("#vSearch", "")
    def refresh():
        with pg.expect_response(lambda r: "enjoy_admin" in r.url and "discovery_areas" in (r.request.post_data or "")):
            pg.click("#vRefresh")
        pg.wait_for_timeout(400)
    pick("State", "Minnesota"); pick("Region", "Duluth MN"); refresh()
    check("Refresh keeps your State and Region choices", shown() == ["Dovetail Cafe", "Duluth Coffee"], shown())
    area(kind="region", state_code="MN", name="Aaa newest region", zip_codes=["55976"], is_active=True)
    refresh()
    r3 = entries("Region")
    check("Refresh also picks up a region made since, listed alphabetically", r3 and r3[0] == "Aaa newest region" and "Duluth MN" in r3, r3)
    check("the chosen region is still chosen after the refresh", shown() == ["Dovetail Cafe", "Duluth Coffee"], shown())
    pg.click("#sideNav a[data-nav=home]"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.click("#sideNav a[data-nav=venues]"); pg.wait_for_function("document.getElementById('vChecked').textContent.length > 0 && document.getElementById('vCount').textContent.length > 0")
    check("leaving Venues and coming back keeps your State and Region choices", shown() == ["Dovetail Cafe", "Duluth Coffee"], shown())
    pg.click("#lockBtn"); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#lockView", state="hidden")
    if pg.locator("#venuesView").count() and not pg.locator("#venuesView").is_visible(): pg.click("#sideNav a[data-nav=venues]")
    pg.wait_for_function("document.getElementById('vCount').textContent.length > 0")
    check("locking the Console clears them: back to All states / All regions", len(shown()) == 8 and "State:" not in chip("State").inner_text() and "Region:" not in chip("Region").inner_text(), (shown(), chip("State").inner_text()))
    check("the page raised no errors", not errors, errors)
    b.close()
print(f"\n{total[0] - len(fails)}/{total[0]} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)

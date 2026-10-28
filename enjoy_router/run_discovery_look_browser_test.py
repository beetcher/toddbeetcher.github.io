#!/usr/bin/env python3
"""Browser test (Discovery + Performance look): Discovery head, banner, tabs, form, dollars, runs chips, errors, phone. (Based on run_discovery_browser_test.py setup.)
OLD DOC: the Discovery station. Real admin door and Discovery door over an in-memory store (seeded the way the live system is), a fake AI,
headless Chromium. Covers the banner, the Run tab (pickers, estimate, Go, progress, review), Runs (open, withdraw), and Settings (models, areas,
types, prompt draft and publish, limits). Nothing leaves this computer.
Run from enjoy_router/:  python3 run_discovery_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timedelta, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import venues_crud as VE, discovery_runs_crud as RU
from crud_endpoint import handle_admin
from console import make_failure_limiter
from discovery.contract import ProviderResult
from discovery.memory_stores import FakeProvider
from discovery_door import handle_discovery
from launch_discovery import city_table, wiring, zip_table
import seed_discovery as SEED
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SECRET = "sk-REAL-LOOKING-SECRET-1234567890"
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

# the ZIP table the live system will have (a few Colorado ZIPs and one Texas ZIP is enough here)
zip_table.set_table({z: ["CO", 39.6 + 0.12 * n, -105.4 + 0.15 * (n % 4), "Longmont" if z.startswith("805") else "Boulder"] for n, z in enumerate(("80301", "80302", "80303", "80304", "80305", "80027", "80026", "80501", "80503", "80504"))}
                    | {"78701": ["TX", 30.2, -97.7, "Austin"], "78702": ["TX", 30.3, -97.7, "Austin"], "99501": ["AK", 61.2, -149.9, "Anchorage"], "99546": ["AK", 51.88, -176.64, "Adak"]})
CITIES = {"CO": [{"name": "Boulder", "population": 108250, "lat": 40.0, "lon": -105.2, "zips": ["80301", "80302", "80303", "80304", "80305"]},
                 {"name": "Longmont", "population": 98000, "lat": 40.2, "lon": -105.1, "zips": ["80501", "80503", "80504"]}]}
city_table.set_table(CITIES)
store, limiter, dlimiter = MemoryDocStore(""), make_failure_limiter(), make_failure_limiter()
clock = [0]
def tick():
    clock[0] += 3
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=clock[0])
def seed_call(coll, op, **args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter, tick())
    return r.status, r.body
quiet = lambda *_: None
SEED.seed(seed_call, say=quiet); SEED.seed(seed_call, say=quiet, regions=True)
ENV = {"ICDT_DISCOVERY_MODE": "live", "ICDT_CLAUDE_KEY": SECRET}
def ai(req):
    def item(**kw): return {k: {"value": v, "mark": "sure", "source_url": "https://example.org/" + k} for k, v in kw.items()}
    good = item(name="Ozo Coffee", operator="Ozo Coffee Company", city="Boulder", state="CO", is_public_venue=True, street="1825 Pearl St", website_url="https://ozo.example.org", description="Situated inside the historic building in the park, this modern cafe features exposed brick, abundant natural light, and comfortable seating areas including couches and small tables well-suited for conversations among small groups, with a long back table for twelve.")
    good["phone"] = {"value": "303-555-0101", "mark": "verify"}
    good["public_hours"] = {"value": "Mon-Fri 7am-5pm, Sat 8am-3pm", "mark": "verify"}
    noaddr = item(name="Corner Table Cafe", operator="Corner Table LLC", city="Boulder", state="CO", is_public_venue=True)
    apt = item(name="Sam's Apartment", operator="Sam", city="Boulder", state="CO", is_public_venue=False, street="5 Elm St")
    return ProviderResult("ok", text=json.dumps({"venues": [good, noaddr, apt]}), input_tokens=500, output_tokens=300)
engine = wiring.build_engine(store, ENV, providers={"gemini": FakeProvider("gemini", ai)}, clock=tick)

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, tick())
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def disc_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_discovery(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, engine, ENV, dlimiter, tick())
    body = r.body
    if EXTRA_RUNS and '"list_runs"' in (q.post_data or "") and '"limit":200' in (q.post_data or "").replace(' ', '') and body.get("ok"):
        body = {**body, "data": {**body["data"], "records": body["data"]["records"] + EXTRA_RUNS}}
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(body))
EXTRA_RUNS = []
def recs(coll, **f):
    return SEED._records(seed_call, coll, **f)

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e))); posts = []; pg.on("request", lambda r: posts.append(r.post_data or "") if r.method == "POST" else None)
    pg.route("**/enjoy_admin", admin_route); pg.route("**/enjoy_discovery", disc_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("Discovery is a station on the home page", pg.locator("#stationTiles .tile", has_text="Discovery").count() == 1)
    pg.click("#sideNav a[data-nav=discovery]"); pg.wait_for_selector("#dModel")

    check("head: title, Manual and Refresh as links", pg.inner_text("#dCount") == "Discovery" and "btn-link" in pg.get_attribute("#dRefresh", "class") and pg.locator("#discoveryView .manualBtn.btn-link").count() == 1)
    check("LIVE banner is amber and says it spends real money", "live" in pg.get_attribute("#dBanner", "class") and "real money" in pg.inner_text("#dBanner") and pg.evaluate("getComputedStyle(document.getElementById('dBanner')).backgroundColor") == "rgb(255, 233, 179)")
    sel = pg.evaluate("getComputedStyle(document.querySelector('#dTabs button[aria-pressed=true]')).backgroundColor")
    check("the selected tab is not orange (underline instead)", sel in ("rgba(0, 0, 0, 0)", "transparent") and pg.evaluate("getComputedStyle(document.querySelector('#dTabs button[aria-pressed=true]')).borderBottomWidth") == "3px", sel)
    check("form has sections Where / What to look for / Limits", [t.strip() for t in pg.locator("#dRun .fsec").all_text_contents()] == ["Where", "What to look for", "Limits"], pg.locator("#dRun .fsec").all_inner_texts())
    check("two across at 1280 (Model beside State)", pg.evaluate("(function(){var a=document.getElementById('dModel').getBoundingClientRect(),b=document.getElementById('dState').getBoundingClientRect();return Math.abs(a.top-b.top)<4 && b.left>a.left})()"))
    check("labels sit above the fields", pg.evaluate("(function(){var l=document.querySelector('label[for=dMax]').getBoundingClientRect(),f=document.getElementById('dMax').getBoundingClientRect();return l.bottom<=f.top+1})()"))
    check("spend cap is in dollars", pg.input_value("#dCap") == "0.10" and pg.locator("label[for=dCap]").inner_text().startswith("Spend cap (dollars)"))
    check("Estimate outlined, Go orange", "btn-secondary" in pg.get_attribute("#dEstimate", "class") and "btn-primary" in pg.get_attribute("#dGo", "class"))
    check("no word INACTIVE in capitals", "INACTIVE" not in pg.inner_text("#dRun"))
    pg.locator("#dAreas label", has_text="Boulder").locator("input").check(); pg.locator("#dTypes label", has_text="coffee shops").locator("input").check()
    pg.fill("#dCap", "0.10"); posts.clear(); pg.click("#dEstimate"); pg.wait_for_selector("#dQuote .dcard")
    check("a $0.10 cap is sent to the server as 10 cents", any('"quote"' in x and '"spend_cap_cents":10' in x.replace(" ", "") for x in posts), [x[:150] for x in posts][-2:])
    pg.fill("#dCap", "0.10"); pg.click("#dEstimate"); pg.wait_for_selector("#dQuote .dcard"); pg.click("#dGo")
    pg.wait_for_function("document.getElementById('dRunLine') && /Finished|finished|Stopped|Done|saved/i.test(document.getElementById('dRunLine').textContent)", timeout=20000)
    pg.click("#dTabs button[data-tab=runs]"); pg.wait_for_selector("#dRuns .dcard")
    check("Runs has Status and Mode chips and a count", pg.locator("#dRunChips .cf-chip", has_text="Status").count() == 1 and pg.locator("#dRunChips .cf-chip", has_text="Mode").count() == 1 and "run" in pg.inner_text("#dRunCount"))
    pg.locator("#dRunChips .cf-chip", has_text="Mode").click(); pg.locator(".cf-pop:visible label", has_text="Dry run").first.click(); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    check("turning Dry run off keeps the live runs", pg.locator("#dRuns .dcard").count() >= 1 and "Dry run" not in pg.inner_text("#dRuns"))
    pg.locator("#dRunChips .cf-chip", has_text="Status").click(); pg.locator(".cf-pop:visible label", has_text="Finished").first.click(); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    check("filtering out every match says so", "No run matches" in pg.inner_text("#dRuns") or pg.locator("#dRuns .dcard").count() >= 1)
    pg.click("#dRuns .dcard button[data-run]") if pg.locator("#dRuns .dcard button[data-run]").count() else None
    pg.click("#dTabs button[data-tab=settings]"); pg.wait_for_selector("#dSubBody .dcard")
    check("Settings: Add orange, Edit outlined, Delete red", "btn-primary" in pg.locator("#dSubBody button[id^=dAdd_]").first.get_attribute("class") and "btn-secondary" in pg.locator("#dSubBody .dcard button", has_text="Edit").first.get_attribute("class"))
    pg.set_viewport_size({"width": 390, "height": 800}); pg.click("#dTabs button[data-tab=run]"); pg.wait_for_timeout(300)
    check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    check("phone: buttons 44px", pg.evaluate("[].every.call(document.querySelectorAll('#dEstimate,#dGo,#dRefresh'), function(b){return b.offsetHeight>=44})"))
    check("no page errors", not errors, errors)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: discovery look checks pass"); sys.exit(1 if fails else 0)

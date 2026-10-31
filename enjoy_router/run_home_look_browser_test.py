#!/usr/bin/env python3
"""Browser test (Home look): plain words, waiting card with a named button, light tiles, wide and phone layouts.
Run from enjoy_router/:  python3 run_home_look_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import attendances_service as AT
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
REQS = []
names = [("Chuck", "Norris"), ("Dana", "Fox"), ("Ronald", "Reed"), ("Sue", "Park")]
for i, (f, l) in enumerate(names):
    rid = "%08d-1111-4111-8111-111111111111" % (i + 1)
    REQS.append({"id": rid, "confirmation_number": "LCH-%04d" % (i + 1), "registration_type": "private", "attendee_count": 1, "created_at": "2026-10-10T1%d:00:00Z" % i,
                                          "first_name": f, "last_name": l, "email": f.lower() + "@example.com", "processing_status": "received"}); store.create(AT.REQUESTS.name, rid, dict(REQS[-1]))
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": REQS}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.wait_for_function("document.getElementById('attnBadge').textContent === '4'")
    t = pg.inner_text("#homeView")
    check("no ship talk on Home (Flight basics, Station N, ship's)", not any(w in t for w in ["Flight basics", "Station 1", "Station 2", "ship"]) and pg.locator(".howto").count() == 0, t[:200])
    check("tiles say Daily work / Records / Admin", set(x.strip() for x in pg.locator("#stationTiles .tile[data-go] .tno").all_text_contents() if x.strip()) <= {"Daily work", "Records", "Admin"} and pg.locator("#stationTiles .tile .tno", has_text="Daily work").count() >= 2)
    check("waiting buttons name the person", all(("Place " + f) in pg.inner_text("#attnBody") for f, _ in names) and "Open requests" not in pg.inner_text("#attnBody"), pg.inner_text("#attnBody")[:300])
    check("waiting card is light, not navy", pg.evaluate("getComputedStyle(document.getElementById('attnBox')).backgroundColor") == "rgb(255, 255, 255)")
    check("tiles are light cards", pg.evaluate("getComputedStyle(document.querySelector('#stationTiles .tile:not(.adm)')).backgroundColor") == "rgb(255, 255, 255)")
    check("admin tiles keep the red edge", pg.locator("#stationTiles .tile.adm").count() == 6 and pg.evaluate("getComputedStyle(document.querySelector('#stationTiles .tile.adm')).borderLeftWidth") == "4px")
    check("wide: page uses 1100 px and waiting items sit two across", pg.evaluate("document.getElementById('homeView').getBoundingClientRect().width") > 1000 and pg.evaluate("(function(){var a=document.querySelectorAll('#attnBody .aitem');return a[0].getBoundingClientRect().top===a[1].getBoundingClientRect().top})()"))
    pg.locator("#attnBody button", has_text="Place Chuck").click(); pg.wait_for_selector("#listView:not([hidden])")
    check("a Place button opens Requests", pg.locator("#listView").is_visible())
    pg.set_viewport_size({"width": 390, "height": 800}); pg.evaluate("location.hash='#/home'"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(300)
    check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    h = pg.evaluate("document.documentElement.scrollHeight")
    check("phone: Home is much shorter than before (was 2,875 px)", h < 2200, h)
    check("phone: tiles two across", pg.evaluate("(function(){var a=document.querySelectorAll('#stationTiles .tile[data-go]');var v=[].filter.call(a,function(e){return e.offsetParent});return v[0].getBoundingClientRect().top===v[1].getBoundingClientRect().top})()"))
    check("home.js is loaded and owns the tiles (HomeStation show, reset, access)", pg.evaluate("typeof HomeStation === 'object' && ['show','reset','access'].every(function (k) { return typeof HomeStation[k] === 'function' })"))
    check("the Home tiles are not built in console.js any more (H-2)", not any(w in (HERE.parent / "console" / "console.js").read_text() for w in ["COMING", "stationTiles", "tile soon"]))
    check("one tile for every station, plus Coming soon", pg.locator("#stationTiles .tile[data-go]").count() == pg.evaluate("document.querySelectorAll('#collPick option').length") - 1 and pg.locator("#stationTiles .tile.soon").count() == 1)
    pg.evaluate("document.getElementById('lockBtn').click()"); pg.wait_for_selector("#lockView:not([hidden])")
    check("locking hides Home", pg.locator("#homeView").is_hidden())
    check("no page errors", not errs, errs)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: home look checks pass"); sys.exit(1 if fails else 0)

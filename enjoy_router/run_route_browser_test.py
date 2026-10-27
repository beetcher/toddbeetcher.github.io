#!/usr/bin/env python3
"""Browser test (S-0): a station address may carry more after the name. #/access/roles opens Access, #/activity?kind=venue opens Activity,
a made-up address opens Home, and the kit reads the pieces (ConsoleKit.hash) and writes them back (ConsoleKit.setHash) without a hashchange.
Run from enjoy_router/:  python3 run_route_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.activity_store import ActivityStore
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = ActivityStore(MemoryDocStore("")); limiter = make_failure_limiter(); fails = []
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
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1200, "height": 900}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    def vis(view): return pg.evaluate("(v)=>!document.getElementById(v).hidden", view)
    pg.evaluate("location.hash='#/access/roles'"); pg.wait_for_function("!document.getElementById('accessView').hidden")
    check("#/access/roles opens Access", vis("accessView") and not vis("homeView"))
    pg.evaluate("location.hash='#/activity?kind=venue&q=a%20b'"); pg.wait_for_function("!document.getElementById('activityView').hidden")
    check("#/activity?kind=venue opens Activity", vis("activityView") and not vis("accessView"))
    h = pg.evaluate("ConsoleKit.hash()")
    check("the kit reads the pieces", h["route"] == "activity" and h["query"] == {"kind": "venue", "q": "a b"} and h["sub"] == [], h)
    h = pg.evaluate("(location.hash='#/access/roles/x', ConsoleKit.hash())")
    check("the kit reads a sub-path", h["route"] == "access" and h["sub"] == ["roles", "x"], h)
    pg.wait_for_function("!document.getElementById('accessView').hidden")
    pg.evaluate("ConsoleKit.setHash('activity', {kind: 'class', q: ''})")
    check("setHash writes the address and leaves the page where it is", pg.evaluate("location.hash") == "#/activity?kind=class" and vis("accessView"), pg.evaluate("location.hash"))
    pg.evaluate("location.hash='#/nonsense/here'"); pg.wait_for_function("!document.getElementById('homeView').hidden")
    check("a made-up address opens Home", vis("homeView"))
    pg.evaluate("location.hash='#/station/venues'"); pg.wait_for_function("!document.getElementById('venuesView').hidden")
    check("the old #/station/<name> form still works", vis("venuesView"))
    check("no script errors", not errs, errs)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "all passed"); sys.exit(1 if fails else 0)

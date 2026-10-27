#!/usr/bin/env python3
"""Browser test (Access look, steps L-1 to L-8): the tab row (People, Territory, Roles, Sign-in and data checks), its addresses and keyboard, tabs that
would be empty are hidden (a person who may only invite sees People alone), no inline style, then (as the steps land) plain words, buttons, People,
Roles, Territory, Sign-in checks, states and phone. Run from enjoy_router/:  python3 run_access_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import access_roles_crud as AR_, access_persons_crud as PE
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SHOTS = pathlib.Path(os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="access_look_")); SHOTS.mkdir(parents=True, exist_ok=True)
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
sup = AR_.create(store, {"key": "super_admin", "label": "Super admin", "is_super_admin": True, "is_active": True}, A).data
head = AR_.create(store, {"key": "region_head", "label": "Region head", "is_super_admin": False, "is_active": True, "capabilities": ["view_console", "edit_venues"]}, A).data
PE.create(store, {"email": "todd@example.com", "display_name": "Todd Beetcher", "role_id": sup["id"]}, A)
PE.create(store, {"email": "hana@example.com", "display_name": "Hana Head", "role_id": head["id"]}, A)
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/access'"); pg.wait_for_selector("#accessView .acrow")

    # ===== L-1 tabs shell
    tabs = pg.locator("#accessView [role=tab]")
    check("L-1 four tabs, People first and selected", tabs.all_inner_texts() == ["People", "Territory", "Roles", "Sign-in and data checks"] and pg.get_attribute("#acTab-people", "aria-selected") == "true", tabs.all_inner_texts())
    check("L-1 the tab row is a tablist with a tabpanel", pg.locator("#accessView [role=tablist]").count() == 1 and pg.get_attribute("#acPanel", "role") == "tabpanel" and pg.get_attribute("#acPanel", "aria-labelledby") == "acTab-people")
    check("L-1 only the People tab's content is on the page", pg.locator("#acTerr").count() == 0 and pg.locator("#acSignIn").count() == 0 and pg.locator("#accessView table").count() == 0)
    pg.click("#acTab-signin"); pg.wait_for_selector("#acSignIn")
    check("L-1 Sign-in and data checks holds the sign-in, review code and time zone boxes under their old ids", all(pg.locator(i).count() == 1 for i in ["#acSignIn", "#acReview", "#acZones"]))
    check("L-1 the time zone box sits under a Data checks heading", pg.locator("#accessView h2", has_text="Data checks").count() == 1)
    check("L-1 the address follows the tab and keeps the page", pg.evaluate("location.hash") == "#/access/signin" and pg.locator("#accessView").is_visible())
    pg.click("#acTab-territory"); pg.wait_for_selector("#acTerr")
    check("L-1 Territory holds the two views", pg.evaluate("location.hash") == "#/access/territory" and pg.locator("#accessView").get_by_role("button", name="By capability").count() == 1)
    pg.click("#acTab-roles"); pg.wait_for_selector("#accessView table")
    check("L-1 Roles holds the role cards and the permission list", pg.locator("#accessView .acrow").count() >= 2 and pg.locator("#accessView table").count() == 1)
    pg.focus("#acTab-roles"); pg.keyboard.press("ArrowRight"); pg.wait_for_selector("#acTab-signin[aria-selected=true]")
    check("L-1 arrow keys move between tabs and focus follows", pg.evaluate("document.activeElement.id") == "acTab-signin")
    pg.keyboard.press("Home"); pg.wait_for_selector("#acTab-people[aria-selected=true]")
    check("L-1 Home goes to the first tab", pg.evaluate("document.activeElement.id") == "acTab-people")
    pg.evaluate("location.hash='#/home'"); pg.evaluate("location.hash='#/access/roles'"); pg.wait_for_selector("#acTab-roles[aria-selected=true]")
    check("L-1 an address with a tab opens that tab", pg.locator("#accessView table").count() == 1)
    check("L-1 no inline style block (the rules are in console.css)", pg.locator("style#accessStyle").count() == 0 and pg.evaluate("getComputedStyle(document.querySelector('.acs')).maxWidth") == "900px")
    pg.screenshot(path=str(SHOTS / "L1_roles.png"), full_page=True)

    # a person who may only invite sees People alone (no empty tabs)
    pg.evaluate("ConsoleKit.me = function () { return { name: 'Hana Head', is_super_admin: false, inspector: false, method: 'google', grants: [{ kind: 'all', capabilities: ['invite_people'] }] }; }")
    pg.evaluate("location.hash='#/home'"); pg.evaluate("location.hash='#/access/roles'"); pg.wait_for_selector("#accessView .acs")
    check("L-1 a person who may only invite sees no tab row and the People page", pg.locator("#accessView [role=tab]").count() == 0 and "Invite someone" in pg.inner_text("#accessView") and pg.locator("#accessView table").count() == 0)
    check("no script errors", not errs, errs)
    b.close()
print("screenshots:", SHOTS)
print("\nOK: all Access look checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

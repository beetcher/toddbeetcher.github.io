#!/usr/bin/env python3
"""Browser test (Console step 1.2a): the left sidebar. Same harness as run_signin_browser_test.py (fake Firebase, real doors, in-memory store).
Checks: at 1440 the sidebar shows (five parts: Home and four groups) and the station drop-down is gone; every station is in it once, in order;
admin stations are tagged; the current page is marked; clicking, Back and the keyboard work; the sidebar stays put while scrolling and never
overlaps the content; Lock hides it. At exactly 1180 it shows, at 1179 and below the drop-down is back and nothing changes (1100, 390).
A region head and a Discovery-only role see only their own stations, with no empty group heading.
Run from enjoy_router/:  python3 run_console_sidebar_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from console import handle_console, make_failure_limiter
from crud import access_persons_crud as PE, access_roles_crud as RO
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin
from memory_store import MemoryStore
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
A = "user:admin"
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, token):
        if token not in self.tokens: raise ValueError("bad")
        return dict(self.tokens[token])
V = Fake()
store = MemoryDocStore("")
def role(key, caps=None, sup=False):
    r = RO.create(store, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps})}, A); assert r.ok, r.problems; return r.data
STATE_ID = "a0000000-0000-4000-8000-000000000001"
REGION_ID = "a0000000-0000-4000-8000-000000000002"
store.create("discovery_areas", STATE_ID, {"id": STATE_ID, "kind": "state", "state_code": "CO", "name": "Colorado", "is_active": True})
store.create("discovery_areas", REGION_ID, {"id": REGION_ID, "kind": "region", "state_code": "CO", "name": "Boulder", "zip_codes": ["80301"], "is_active": True})
def person(email, r, name):
    from access.capabilities import TERRITORIAL
    terr = [c for c in r.get("capabilities", []) if c in TERRITORIAL]
    extra = {"grants": [{"kind": "regions", "state_code": "CO", "region_ids": [REGION_ID], "capabilities": terr}]} if terr else {}      # territorial capabilities now come from grants
    p = PE.create(store, {"email": email, "display_name": name, "role_id": r["id"], **extra}, A); assert p.ok, p.problems
    tok = f"tok.{email.split('@')[0]}.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    V.tokens[tok] = {"uid": "uid-" + email, "email": email, "email_verified": True, "provider": "google.com", "name": name}
    return tok
sup = role("super_admin", sup=True)
head = role("region_head", ["view_console", "edit_venues", "activate_venues", "manage_instructors", "manage_requests"])
spend = role("spend_viewer", ["view_spend"])
T_TODD = person("todd@example.com", sup, "Todd Beetcher")
T_HEAD = person("head@example.com", head, "Hana Head")
T_SPEND = person("spend@example.com", spend, "Sam Spend")
lead_r = role("lead_role", ["view_console", "view_spend"])
PE.create(store, {"email": "lead@example.com", "display_name": "Lena Lead", "role_id": lead_r["id"], "grants": [{"kind": "regions", "state_code": "CO", "region_ids": [REGION_ID], "capabilities": ["manage_requests", "edit_venues", "activate_venues", "manage_instructors", "invite_people"]}]}, A)
T_LEAD = "tok.lead.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
V.tokens[T_LEAD] = {"uid": "uid-lead", "email": "lead@example.com", "email_verified": True, "provider": "google.com", "name": "Lena Lead"}
T_STRANGER = "tok.stranger.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
V.tokens[T_STRANGER] = {"uid": "uid-x", "email": "stranger@example.com", "email_verified": True, "provider": "google.com", "name": "Stranger"}

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
limiter, climiter = make_failure_limiter(), make_failure_limiter()
seen = []   # (path, bearer, status)
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc), verifier=V)
    seen.append(("admin:" + (json.loads(q.post_data or "{}").get("op", "")), q.headers.get("authorization", "")[7:], r.status))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def records_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_console("GET", q.headers.get("authorization", ""), {}, KEY, "v", MemoryStore([]), climiter, datetime.now(timezone.utc), verifier=V, access_store=store)
    seen.append(("records", q.headers.get("authorization", "")[7:], r.status))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def any_route(route):   # every other door the page might call: refuse nothing, return an empty list
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    seen.append(("other:" + q.url.rsplit("/", 1)[-1], q.headers.get("authorization", "")[7:], 200))
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}}))

FAKE_FIREBASE = """
(function () {
  try { Object.defineProperty(window, "CONSOLE_FIREBASE", { value: { apiKey: "__APIKEY__", projectId: "p" }, writable: false }); } catch (e) {}
  var listeners = [], cur = null, N = 0;
  function user(t) { return { getIdToken: function () { return Promise.resolve(t); } }; }
  try { var kept = sessionStorage.getItem("fakeTok"); if (kept) cur = user(kept); } catch (e) {}
  var auth = {
    get currentUser() { return cur; },
    onIdTokenChanged: function (cb) { listeners.push(cb); setTimeout(function () { cb(cur); }, 0); },
    signInWithPopup: function () {
      return new Promise(function (ok, no) {
        var t = window.__NEXT; if (!t) { no({ code: "auth/popup-closed-by-user" }); return; }
        cur = user(t); try { sessionStorage.setItem("fakeTok", t); } catch (e) {}
        listeners.forEach(function (cb) { cb(cur); }); ok({ user: cur });
      });
    },
    signOut: function () { cur = null; window.__signedOut = (window.__signedOut || 0) + 1; try { sessionStorage.removeItem("fakeTok"); } catch (e) {} listeners.forEach(function (cb) { cb(null); }); return Promise.resolve(); }
  };
  window.__refresh = function (t) { cur = user(t); listeners.forEach(function (cb) { cb(cur); }); };
  var fb = { apps: [], initializeApp: function () { fb.apps.push(1); }, auth: function () { return auth; } };
  fb.auth.GoogleAuthProvider = function () { this.setCustomParameters = function () {}; };
  window.firebase = fb;
})();
"""

def launch(p):
    exe = "/opt/pw-browsers/chromium"
    return p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
def new_page(b, fake=True, w=900, apikey="test-key"):
    ctx = b.new_context(viewport={"width": w, "height": 900})
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    if fake: pg.add_init_script(FAKE_FIREBASE.replace("__APIKEY__", apikey))
    pg.route("**/enjoy_admin", admin_route); pg.route("**/enjoy_console_records*", records_route); pg.route("**/enjoy_discovery", any_route)
    return pg, errs
def tiles(pg): return sorted(t.strip().split("\n")[1] if "\n" in t.strip() else t.strip() for t in pg.locator("#stationTiles .tile[data-go]:visible").all_inner_texts())
def sign_in(pg, tok):
    pg.evaluate("t => { window.__NEXT = t; }", tok); pg.click("#googleBtn")


IDS = "Array.from(document.querySelectorAll('#sideNav a[data-nav]')).filter(a => a.offsetParent !== null).map(a => a.dataset.nav)"
HEADS = "Array.from(document.querySelectorAll('#sideNav .nhead')).filter(h => h.offsetParent !== null).map(h => h.textContent)"
TILES = "Array.from(document.querySelectorAll('#stationTiles .tile[data-go]')).filter(t => t.offsetParent !== null).map(t => t.dataset.go)"
EXPECT = ["home", "requests", "messages", "classes", "attendance", "venues", "curriculums", "instructors", "people", "students", "organizations", "places", "discovery", "access", "activity", "performance"]
def go(pg, w, tok):
    pg.set_viewport_size({"width": w, "height": 900})
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg, tok); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(450)
def no_sideways(pg): return pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

with sync_playwright() as p:
    b = launch(p)
    # ---------- Todd at 1440
    pg, errs = new_page(b, w=1440)
    go(pg, 1440, T_TODD)
    check("1440: the sidebar shows and the station drop-down is gone", pg.locator("#sideNav").is_visible() and not pg.locator("#collPick").is_visible())
    check("four group headings, in order", pg.evaluate(HEADS) == ["Today", "Classes", "People", "Growth and admin"], pg.evaluate(HEADS))
    ids = pg.evaluate(IDS)
    check("Home and all 15 stations, each once, in the planned order", ids == EXPECT, ids)
    check("...the same stations the tiles on Home offer", sorted(i for i in ids if i != "home") == sorted(pg.evaluate(TILES)))
    check("the six admin stations are tagged", pg.locator("#sideNav .nadm").count() == 6 == pg.locator("#stationTiles .tile.adm").count(), pg.locator("#sideNav .nadm").count())
    check("Home is marked as the current page", pg.locator('#sideNav a[aria-current="page"]').count() == 1 and pg.locator('#sideNav a[data-nav="home"]').get_attribute("aria-current") == "page")
    pg.screenshot(path="/tmp/claude-0/sidebar_home_1440.png")
    pg.click('#sideNav a[data-nav="venues"]'); pg.wait_for_timeout(500)
    check("clicking Venues opens it at #/venues", pg.evaluate("location.hash") == "#/venues" and pg.locator("#venuesView").is_visible() and not pg.locator("#homeView").is_visible())
    check("...and only Venues is marked current", pg.locator('#sideNav a[aria-current="page"]').count() == 1 and pg.locator('#sideNav a[data-nav="venues"]').get_attribute("aria-current") == "page")
    pg.go_back(); pg.wait_for_timeout(500)
    check("Back returns to Home and moves the mark", pg.locator("#homeView").is_visible() and pg.locator('#sideNav a[data-nav="home"]').get_attribute("aria-current") == "page")
    pg.focus('#sideNav a[data-nav="messages"]'); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    check("the keyboard works: Enter on Messages opens it", pg.locator("#messagesView").is_visible() and pg.evaluate("location.hash") == "#/messages")
    box_nav = pg.locator("#sideNav").bounding_box(); box_main = pg.locator("main").bounding_box()
    check("the sidebar does not overlap the content", box_nav["x"] + box_nav["width"] <= box_main["x"] + 1, (box_nav, box_main))
    check("the content column is wide, not the old 760px", box_main["width"] > 900, box_main["width"])
    check("nothing scrolls sideways at 1440", no_sideways(pg))
    pg.click('#sideNav a[data-nav="home"]'); pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(250)
    top_h = pg.evaluate("document.getElementById('topbar').getBoundingClientRect().height")
    check("the sidebar stays in view, just under the top bar, while scrolling", abs(pg.evaluate("document.getElementById('sideNav').getBoundingClientRect().top") - top_h) <= 1.5 and pg.locator("#sideNav").is_visible())
    pg.evaluate("window.scrollTo(0, 0)")
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("Lock hides the sidebar", not pg.locator("#sideNav").is_visible())
    check("the page made no script errors at 1440", not errs, errs)

    # ---------- the breakpoint and the narrow layouts (unchanged)
    pg2, e2 = new_page(b, w=1180)
    go(pg2, 1180, T_TODD)
    check("1180 exactly: the sidebar shows, the drop-down is gone, nothing scrolls sideways", pg2.locator("#sideNav").is_visible() and not pg2.locator("#collPick").is_visible() and no_sideways(pg2))
    pg2.set_viewport_size({"width": 1179, "height": 900}); pg2.wait_for_timeout(200)
    check("1179: the drop-down is back and the sidebar is gone", not pg2.locator("#sideNav").is_visible() and pg2.locator("#collPick").is_visible())
    pg2.set_viewport_size({"width": 1100, "height": 900}); pg2.wait_for_timeout(200)
    check("1100: the old layout, with a 760px column", not pg2.locator("#sideNav").is_visible() and pg2.locator("#collPick").is_visible() and pg2.locator("main").bounding_box()["width"] <= 761)
    pg2.set_viewport_size({"width": 390, "height": 900}); pg2.wait_for_timeout(250)
    check("390 (phone): drop-down, no sidebar, nothing scrolls sideways", not pg2.locator("#sideNav").is_visible() and pg2.locator("#collPick").is_visible() and no_sideways(pg2))
    pg2.select_option("#collPick", "classes"); pg2.wait_for_timeout(400)
    check("...and the drop-down still switches stations", pg2.locator("#classesView").is_visible())
    check("the page made no script errors across the breakpoint", not e2, e2)

    # ---------- other roles see only their own stations
    pg3, e3 = new_page(b, w=1440)
    go(pg3, 1440, T_HEAD)
    nav_ids, tile_ids, heads = pg3.evaluate(IDS), pg3.evaluate(TILES), pg3.evaluate(HEADS)
    check("a region head's sidebar offers exactly the stations on their Home tiles (plus Home)", sorted(i for i in nav_ids if i != "home") == sorted(tile_ids) and "home" in nav_ids, (nav_ids, tile_ids))
    check("...and no station they cannot open", not ({"access", "activity", "performance", "discovery", "people"} & set(nav_ids)), nav_ids)
    empty = pg3.evaluate("Array.from(document.querySelectorAll('#sideNav .ngroup')).filter(g => g.offsetParent !== null).filter(g => !Array.from(g.querySelectorAll('li')).some(li => li.offsetParent !== null)).length")
    check("...with no empty group heading", empty == 0 and len(heads) >= 1, heads)
    check("no script errors for the region head", not e3, e3)
    pg4, e4 = new_page(b, w=1440)
    go(pg4, 1440, T_SPEND)
    check("a Discovery-only role sees Home and Discovery only", pg4.evaluate(IDS) == ["home", "discovery"], pg4.evaluate(IDS))
    check("...under one heading, Growth and admin", pg4.evaluate(HEADS) == ["Growth and admin"], pg4.evaluate(HEADS))
    # ---------- 1.2b: skip link, titles, focus, #/station/<id>
    pg5, e5 = new_page(b, w=1440)
    go(pg5, 1440, T_TODD)
    check("title on Home", pg5.title() == "Home \u00b7 LAUNCH Console", pg5.title())
    pg5.click('#sideNav a[data-nav="venues"]'); pg5.wait_for_timeout(450)
    pg5.screenshot(path="/tmp/claude-0/sidebar_venues_1440.png")
    check("title names the station", pg5.title() == "Venues \u00b7 LAUNCH Console", pg5.title())
    check("focus moves to the content on a station change", pg5.evaluate("document.activeElement.id") == "main")
    pg5.goto(PAGE + "#/station/classes"); pg5.wait_for_timeout(600)
    if not pg5.locator("#classesView").is_visible():
        sign_in(pg5, T_TODD); pg5.wait_for_timeout(600)
    pg5.evaluate("location.hash = '#/station/classes'"); pg5.wait_for_timeout(500)
    check("#/station/classes opens Classes", pg5.locator("#classesView").is_visible() and pg5.title().startswith("Classes"), pg5.title())
    pg5.focus("#brand")
    pg5.keyboard.press("Shift+Tab")
    check("the skip link comes just before the top bar in Tab order, and shows", pg5.evaluate("document.activeElement.className") == "skip" and pg5.evaluate("document.querySelector('.skip').getBoundingClientRect().top") >= 0)
    pg5.keyboard.press("Enter"); pg5.wait_for_timeout(200)
    check("Enter on it moves focus to the content and keeps the address", pg5.evaluate("document.activeElement.id") == "main" and "classes" in pg5.evaluate("location.hash"))
    pg5.click("#lockBtn"); pg5.wait_for_selector("#lockView:not([hidden])")
    check("Lock resets the title", pg5.title() == "Console", pg5.title())
    check("no script errors in 1.2b checks", not e5, e5)
    b.close()

if fails:
    print("\nFAILED:", len(fails)); sys.exit(1)
print("\nOK: all sidebar browser checks pass")

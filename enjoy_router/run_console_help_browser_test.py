#!/usr/bin/env python3
"""Browser test (Console step 1.4): the Help drawer - manuals and workflows in one place. Same harness as the sidebar test. Run from enjoy_router/:  python3 run_console_ui_browser_test.py"""
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
import seed_access
insp_role = role("global_inspector", seed_access.ROLES[-1]["capabilities"])
T_INSP = person("inspector@example.com", insp_role, "Ivy Inspector")
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



def go(pg, w, tok):
    pg.set_viewport_size({"width": w, "height": 900})
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg, tok); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(450)
ASK = "window.__ans = undefined; UI.confirm(%s).then(function (a) { window.__ans = a; }); 0;"
def ans(pg): return pg.evaluate("window.__ans")

with sync_playwright() as p:
    b = launch(p)
    pg, errs = new_page(b, w=1440)
    VSCHEMA = (HERE.parent / "schemas" / "venue.schema.json").read_text()
    pg.route("**/schemas/venue.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=VSCHEMA))
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    check("no Help button on the lock screen", pg.locator("#helpOpen").is_hidden())
    go(pg, 1440, T_TODD)
    check("a Help button is in the top bar once signed in", pg.locator("#helpOpen").is_visible())
    check("the drawer starts closed", pg.locator("#manual").is_hidden() and pg.get_attribute("#helpOpen", "aria-expanded") == "false")
    check("Home has no workflow list or manual buttons of its own any more", pg.locator("#wfHomeList").count() == 0 and pg.locator("#homeManualBtns").count() == 0)
    check("the old workflow dialog is gone", pg.locator("#wfDlg").count() == 0)

    pg.click("#helpOpen"); pg.wait_for_selector("#manual:not([hidden])")
    check("Help opens a drawer on the Manuals tab", pg.get_attribute("#hTabM", "aria-selected") == "true" and pg.locator("#paneM").is_visible() and pg.locator("#paneW").is_hidden())
    check("the toggle says it is expanded", pg.get_attribute("#helpOpen", "aria-expanded") == "true")
    box = pg.locator("#manual").bounding_box()
    check("it is a side drawer, not a full overlay", box["width"] <= 641 and box["x"] + box["width"] >= 1439, box)
    check("the page behind can still scroll (no body lock on a wide screen)", pg.evaluate("getComputedStyle(document.body).overflow") != "hidden")
    pg.screenshot(path="/tmp/claude-0/help_drawer_manuals_1440.png")
    n = pg.locator("#overlayBtns button").count()
    check("one button per manual", n >= 10, n)
    pg.click('#overlayBtns button[data-m="venues"]')
    check("a manual button shows that manual", pg.locator("#manual h2", has_text="Venues").is_visible() and pg.get_attribute('#overlayBtns button[data-m="venues"]', "aria-pressed") == "true")

    pg.click("#hTabW")
    check("the Workflows tab lists the four workflows", pg.locator("#paneW").is_visible() and pg.locator("#wfBody details.wfcard").count() == 4 and pg.get_attribute("#hTabW", "aria-selected") == "true")
    pg.screenshot(path="/tmp/claude-0/help_drawer_workflows_1440.png")
    pg.click("#hTabM")
    check("back on Manuals the last manual is still showing", pg.locator("#manual h2", has_text="Venues").is_visible())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(50)
    check("Escape closes the drawer and focus returns to Help", pg.locator("#manual").is_hidden() and pg.evaluate("document.activeElement.id") == "helpOpen")
    pg.click("#helpOpen"); pg.click("#helpOpen")
    check("the Help button toggles it closed", pg.locator("#manual").is_hidden())

    # station Manual button and the (i) button open the right tab
    pg.click('#sideNav a[data-nav="venues"]'); pg.wait_for_selector("#venuesView:not([hidden])")
    pg.click("#venuesView .manualBtn"); pg.wait_for_selector("#manual:not([hidden])")
    check("a station's Manual button opens that manual in the drawer", pg.locator("#manual h2", has_text="Venues").is_visible() and pg.get_attribute("#hTabM", "aria-selected") == "true")
    pg.click("#manualClose")
    check("Close closes the drawer", pg.locator("#manual").is_hidden())
    pg.click('#sideNav a[data-nav="requests"]'); pg.wait_for_selector("#listView:not([hidden])")
    pg.click("#reqInfo"); pg.wait_for_selector("#manual:not([hidden]) #paneW:not([hidden])")
    check("the (i) button on Requests opens the Workflows tab with the first one expanded", pg.locator("#wfBody details[open]").count() == 1 and pg.get_attribute("#hTabW", "aria-selected") == "true")
    pg.locator("#wfBody details[open]").get_by_role("button", name="Open Classes").first.click()
    pg.wait_for_selector("#classesView:not([hidden])")
    check("a workflow step jumps to its station and closes the drawer", pg.locator("#manual").is_hidden())

    # keyboard: arrow keys between tabs
    pg.click("#helpOpen"); pg.focus("#hTabM"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(50)
    check("the right arrow moves to Workflows", pg.get_attribute("#hTabW", "aria-selected") == "true" and pg.evaluate("document.activeElement.id") == "hTabW")
    pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(50)
    check("the left arrow moves back to Manuals", pg.get_attribute("#hTabM", "aria-selected") == "true" and pg.evaluate("document.activeElement.id") == "hTabM")
    check("only the selected tab is in the tab order", pg.evaluate("document.getElementById('hTabW').tabIndex") == -1)
    pg.click("#manualClose")

    # phone width: full width, page locked
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(100)
    pg.click("#helpOpen"); pg.wait_for_selector("#manual:not([hidden])")
    box = pg.locator("#manual").bounding_box()
    check("on a phone the drawer fills the width", box["width"] >= 389, box)
    check("no sideways scroll on a phone", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    pg.screenshot(path="/tmp/claude-0/help_drawer_390.png")
    pg.click("#hTabW"); pg.wait_for_timeout(50)
    check("no sideways scroll on a phone, workflows", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    pg.click("#manualClose")

    # Home buttons
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.click('#sideNav a[data-nav="requests"]'); pg.click("#brand"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.click("#helpHomeW"); pg.wait_for_selector("#paneW:not([hidden])")
    check("Home's Workflows button opens the Workflows tab", pg.locator("#wfBody details.wfcard").count() == 4)
    pg.click("#manualClose"); pg.click("#helpHomeM"); pg.wait_for_selector("#paneM:not([hidden])")
    check("Home's Manuals button opens the Manuals tab", pg.get_attribute("#hTabM", "aria-selected") == "true")
    pg.click("#manualClose")
    pg.click("#helpOpen")
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("locking closes the drawer and hides Help", pg.locator("#manual").is_hidden() and pg.locator("#helpOpen").is_hidden())
    check("the page made no script errors", not errs, errs)
    b.close()

if fails:
    print("\nFAILED:", len(fails)); sys.exit(1)
print("\nOK: all Help drawer browser checks pass")

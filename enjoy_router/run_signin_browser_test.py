#!/usr/bin/env python3
"""Browser test (P-62 step 4): the Console's "Sign in with Google". A fake Firebase stands in for Google in the page, the real doors
(handle_admin / handle_console with a fake verifier and an in-memory access store) answer. Headless Chromium.
Checks: key-only until configured; the Google button; Todd sees everything; a region head sees only the stations the role allows; a
Discovery-only role sees one station and the home page makes no refused calls; an uninvited account is told so and signed out; the Bearer
value is the Google token (and follows a refreshed one); Lock signs out; a reload keeps the Google session; the admin key still works.
Run from enjoy_router/:  python3 run_signin_browser_test.py"""
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
def person(email, r, name):
    p = PE.create(store, {"email": email, "display_name": name, "role_id": r["id"]}, A); assert p.ok, p.problems
    tok = f"tok.{email.split('@')[0]}.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    V.tokens[tok] = {"uid": "uid-" + email, "email": email, "email_verified": True, "provider": "google.com", "name": name}
    return tok
sup = role("super_admin", sup=True)
head = role("region_head", ["view_console", "edit_venues", "activate_venues", "manage_instructors", "manage_requests"])
spend = role("spend_viewer", ["view_spend"])
T_TODD = person("todd@example.com", sup, "Todd Beetcher")
T_HEAD = person("head@example.com", head, "Hana Head")
T_SPEND = person("spend@example.com", spend, "Sam Spend")
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

with sync_playwright() as p:
    b = launch(p)

    # ---------- not configured: key only, as before
    pg, errs = new_page(b, fake=False)
    pg.goto(PAGE); pg.wait_for_selector("#lockView:not([hidden])")
    check("no web key set: only the admin-key box shows", pg.locator("#keyBox").is_visible() and not pg.locator("#googleBox").is_visible() and not pg.locator("#swapLink").is_visible())
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("...and the key still opens the Console, with every station", len(tiles(pg)) == 12, tiles(pg))
    check("...labelled as the admin key", "Admin key" in pg.locator("#who").inner_text())
    check("the page made no script errors (key only)", not errs, errs)

    pg0, e0 = new_page(b, apikey="")
    pg0.goto(PAGE); pg0.wait_for_selector("#lockView:not([hidden])"); pg0.wait_for_timeout(300)
    check("an empty web key keeps the page key-only even if Firebase is present", pg0.locator("#keyBox").is_visible() and not pg0.locator("#googleBox").is_visible())

    # ---------- configured
    pg, errs = new_page(b)
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    check("web key set: the Google button shows and the key box is tucked away", pg.locator("#googleBtn").is_visible() and not pg.locator("#keyBox").is_visible() and pg.locator("#swapLink").inner_text() == "Use admin key")
    pg.click("#swapLink")
    check("'Use admin key' reveals the key box and offers the way back", pg.locator("#keyBox").is_visible() and not pg.locator("#googleBox").is_visible() and pg.locator("#swapLink").inner_text() == "Use Google sign-in")
    pg.click("#swapLink")
    pg.evaluate("window.__NEXT = ''"); pg.click("#googleBtn")
    check("closing the Google window is not an error message", pg.locator("#lockMsg").inner_text() == "")

    # ---------- Todd (super admin)
    seen.clear(); sign_in(pg, T_TODD); pg.wait_for_selector("#homeView:not([hidden])")
    check("the name label is showing", pg.locator("#who").is_visible())
    check("Todd is in, named with his role", "Todd Beetcher" in pg.locator("#who").inner_text() and "super admin" in pg.locator("#who").inner_text(), pg.locator("#who").inner_text())
    check("Todd sees every station", len(tiles(pg)) == 12, tiles(pg))
    check("the first call asked who he is, with the Google token (not the key)", any(s[0] == "admin:me" and s[1] == T_TODD and s[2] == 200 for s in seen) and not any(s[1] == KEY for s in seen), seen[:4])
    pg.wait_for_timeout(600)
    store_dump = pg.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage).filter(e => e[0] !== 'fakeTok')])")
    check("the Google token is never saved by the Console itself", T_TODD not in store_dump and "console_key" not in store_dump, store_dump[:200])
    # a token refresh is picked up
    seen.clear()
    V.tokens["tok.refreshed.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"] = V.tokens[T_TODD]
    NEW = "tok.refreshed.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    pg.evaluate("t => window.__refresh(t)", NEW)
    pg.select_option("#collPick", "venues"); pg.wait_for_timeout(700)
    check("after a refresh the next call carries the new token", any(s[0].startswith("admin:") and s[1] == NEW for s in seen) and not any(s[1] == T_TODD for s in seen[-3:]), seen[-4:])
    # reload keeps the session
    pg.evaluate("location.hash = '#/home'"); pg.reload(); pg.wait_for_function("!document.getElementById('homeView').hidden && document.getElementById('who').textContent.length > 0")
    check("a reload keeps the Google session (no sign-in screen)", "Todd Beetcher" in pg.locator("#who").inner_text())
    # Lock signs out
    before = pg.evaluate("window.__signedOut || 0"); pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("Lock signs out of Google and returns to the Google button", pg.evaluate("window.__signedOut || 0") > before and pg.locator("#googleBtn").is_visible() and not pg.locator("#who").is_visible())
    pg.reload(); pg.wait_for_selector("#lockView:not([hidden])"); pg.wait_for_timeout(300)
    check("after Lock a reload stays on the sign-in screen", pg.locator("#googleBtn").is_visible() and not pg.locator("#homeView").is_visible())

    # ---------- region head
    seen.clear(); sign_in(pg, T_HEAD); pg.wait_for_selector("#homeView:not([hidden])")
    want = sorted(["Registration requests", "Venues", "Classes", "Places", "Instructors", "Students", "Curriculum", "Attendance"])
    check("the region head sees only the stations the role allows", tiles(pg) == want, tiles(pg))
    opts = pg.eval_on_selector_all("#collPick option", "o => o.map(x => x.value)")
    check("...and the station menu agrees", sorted(opts) == sorted(["home", "requests", "venues", "classes", "places", "instructors", "students", "curriculums", "attendance"]), opts)
    check("...with no refused calls on the way in", not [s for s in seen if s[2] in (401, 403)], seen)
    pg.evaluate("location.hash = '#/discovery'"); pg.wait_for_timeout(400)
    check("typing a station address the role may not use sends them home", pg.evaluate("location.hash") == "#/home" and pg.locator("#homeView").is_visible())
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")

    # ---------- Discovery-only role
    seen.clear(); sign_in(pg, T_SPEND); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(700)
    check("a Discovery-only role sees just that station", tiles(pg) == ["Discovery"], tiles(pg))
    check("...the 'waiting to be placed' box is hidden for them", not pg.locator("#attnBox").is_visible())
    check("...and the home page made no refused calls", not [s for s in seen if s[2] in (401, 403)], seen)
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")

    # ---------- uninvited
    before = pg.evaluate("window.__signedOut || 0"); sign_in(pg, T_STRANGER); pg.wait_for_function("document.getElementById('lockMsg').textContent.length > 0")
    check("an uninvited Google account is told so", "not been invited" in pg.locator("#lockMsg").inner_text(), pg.locator("#lockMsg").inner_text())
    check("...stays on the sign-in screen and is signed out of Google", pg.locator("#lockView").is_visible() and not pg.locator("#homeView").is_visible() and pg.evaluate("window.__signedOut || 0") > before)

    # ---------- the key still works beside Google
    pg.click("#swapLink"); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("the admin key still opens everything with Google switched on", len(tiles(pg)) == 12 and "Admin key" in pg.locator("#who").inner_text())
    pg.evaluate("t => window.__refresh(t)", T_HEAD); pg.wait_for_timeout(500)
    check("a Google session appearing while the key is in use does not take over", "Admin key" in pg.locator("#who").inner_text() and len(tiles(pg)) == 12)
    check("the page made no script errors (Google on)", not errs, errs)

    # ---------- a phone-width sign-in screen
    pg2, e2 = new_page(b, w=390)
    pg2.goto(PAGE); pg2.wait_for_selector("#googleBox:not([hidden])")
    check("phone width: the button fits and nothing scrolls sideways", pg2.evaluate("document.documentElement.scrollWidth <= window.innerWidth") and pg2.locator("#googleBtn").bounding_box()["width"] > 250)
    b.close()

print("\nFAILED: " + ", ".join(fails) if fails else "\nOK: all sign-in browser checks pass")
sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""
Signing in again after the Console timed you out (found live 2026-10-22). After "You were signed out after N minutes without activity" the Google button
signed the person in and then straight out again ("That key did not work") until the page was refreshed, because the old last-active time survived the
timeout. Here the clock is pushed past the timeout, the page locks itself, the sign-in answer is held back for 2.5 seconds (so the page's one-second
timer runs during it, as on a slow network), and signing in again must work, twice, and stay signed in. Run from enjoy_router/:  python3 run_idle_resignin_browser_test.py
"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from types import SimpleNamespace
from console import handle_console, make_failure_limiter
from crud import access_persons_crud as PE, access_roles_crud as RO, venues_service as VS
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin
from discovery_door import handle_discovery
from memory_store import MemoryStore
import seed_access
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
A = "user:admin"
SHOTS = pathlib.Path("/tmp/claude-0/shots"); SHOTS.mkdir(parents=True, exist_ok=True)
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
insp_role = role("global_inspector", seed_access.ROLES[-1]["capabilities"]); assert seed_access.ROLES[-1]["key"] == "global_inspector"
sup_role = role("super_admin", sup=True)
T_INSP = person("inspector@example.com", insp_role, "Ivy Inspector")
T_TODD = person("todd@example.com", sup_role, "Todd Beetcher")

# a world with private details in it
REGION = "a0000000-0000-4000-8000-000000000002"
store.create("discovery_areas", REGION, {"id": REGION, "kind": "region", "state_code": "CO", "name": "Boulder", "zip_codes": ["80301"], "is_active": True, "schema_version": 1})
r = VS.create_with_place(store, {"name": "Boulder Hall", "slug": "boulder_hall", "status": "inactive", "is_public_venue": True, "email": "hall@venue.example", "phone": "303-555-0100"}, A,
                         address={"lines": ["1 Main St"], "locality": "Boulder", "region": "CO", "postal_code": "80301", "country": "US"}); assert r.ok, r.problems
VID = r.data["id"]
PID = "00000231-0000-4000-8000-000000000000"
store.create("individuals", PID, {"id": PID, "schema_version": 1, "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z", "display_name": "Ann Student", "given_name": "Ann",
             "family_name": "Student", "status": "active", "email": "ann.private@home.example", "phone": "303-555-0122", "birth_date": "1961-04-17", "notes": "widow, prefers mornings"})
REQS = [{"id": "r1", "created_at": "2026-10-09T04:26:00Z", "registration_type": "private", "first_name": "Mel", "last_name": "Jones", "email": "mel.private@home.example", "phone": "303-555-0144",
         "postal_code": "80301", "notes": "has two dogs", "attendee_count": 1}]
SECRETS = ["ann.private@home.example", "303-555-0122", "1961-04-17", "widow", "mel.private@home.example", "303-555-0144", "two dogs"]

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
limiter, climiter, dlimiter = make_failure_limiter(), make_failure_limiter(), make_failure_limiter()
seen = []
class Engine:
    def __init__(self): self.calls = []
    def plan(self, rq, actor): self.calls.append(("plan", rq.spend_cap_cents)); return SimpleNamespace(ok=True, data={"id": "run1"}, code="", message="")
    def quote(self, rq): self.calls.append(("quote", rq.spend_cap_cents)); return SimpleNamespace(ok=True, data={"low": 1, "high": 5}, code="", message="")
eng = Engine()
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS": route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    body = json.loads(q.post_data or "{}")
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc), verifier=V)
    seen.append((body.get("collection", ""), body.get("op", ""), r.status))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def records_route(route):
    q = route.request
    if q.method == "OPTIONS": route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    ms = MemoryStore([]); ms.requests.extend(REQS)
    r = handle_console("GET", q.headers.get("authorization", ""), {}, KEY, "v", ms, climiter, datetime.now(timezone.utc), verifier=V, access_store=store)
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def disc_route(route):
    q = route.request
    if q.method == "OPTIONS": route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_discovery(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, eng, {}, dlimiter, datetime.now(timezone.utc), verifier=V)
    seen.append(("discovery", json.loads(q.post_data or "{}").get("op", ""), r.status))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

FAKE_FIREBASE = """
(function () {
  try { Object.defineProperty(window, "CONSOLE_FIREBASE", { value: { apiKey: "test-key", projectId: "p" }, writable: false }); } catch (e) {}
  var listeners = [], cur = null;
  function user(t) { return { getIdToken: function () { return Promise.resolve(t); } }; }
  try { var kept = sessionStorage.getItem("fakeTok"); if (kept) cur = user(kept); } catch (e) {}
  var auth = { get currentUser() { return cur; },
    onIdTokenChanged: function (cb) { listeners.push(cb); setTimeout(function () { cb(cur); }, 0); },
    signInWithPopup: function () { return new Promise(function (ok, no) { var t = window.__NEXT; if (!t) { no({ code: "auth/popup-closed-by-user" }); return; }
        cur = user(t); try { sessionStorage.setItem("fakeTok", t); } catch (e) {} listeners.forEach(function (cb) { cb(cur); }); ok({ user: cur }); }); },
    signOut: function () { cur = null; try { sessionStorage.removeItem("fakeTok"); } catch (e) {} listeners.forEach(function (cb) { cb(null); }); return Promise.resolve(); } };
  var fb = { apps: [], initializeApp: function () { fb.apps.push(1); }, auth: function () { return auth; } };
  fb.auth.GoogleAuthProvider = function () { this.setCustomParameters = function () {}; };
  window.firebase = fb;
})();
"""
def launch(p):
    exe = "/opt/pw-browsers/chromium"
    return p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
def new_page(b, w=1100):
    ctx = b.new_context(viewport={"width": w, "height": 900}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.add_init_script(FAKE_FIREBASE)
    pg.route("**/enjoy_admin", admin_route); pg.route("**/enjoy_console_records*", records_route); pg.route("**/enjoy_discovery", disc_route)
    return pg, errs
def tiles(pg): return sorted(t.strip().split("\n")[1] if "\n" in t.strip() else t.strip() for t in pg.locator("#stationTiles .tile[data-go]:visible").all_inner_texts())
def sign_in(pg, tok): pg.evaluate("t => { window.__NEXT = t; }", tok); pg.click("#googleBtn")
def goto(pg, station, wait=900): pg.select_option("#collPick", station); pg.wait_for_timeout(wait)
def disabled_edit_buttons(pg): return pg.locator("main button[data-viewonly='1']").count()
def enabled_write_buttons(pg):
    import re
    out = []
    for t in pg.locator("main button:visible:not([disabled])").all_inner_texts():
        t = t.strip()
        if t.lower() == "change history": continue          # looking at the log is allowed
        if re.match(r"^(edit|save|delete|remove|add|change|switch|merge|undo|publish|resend|invite|put in|create|retire|withdraw|mark|send|assign|activate|find gps|new )", t, re.I): out.append(t)
    return out


import time
DELAY = {"me": 0.0}
_orig_admin = admin_route
def slow_admin(route):
    try:
        if json.loads(route.request.post_data or "{}").get("op") == "me" and DELAY["me"]: time.sleep(DELAY["me"])
    except Exception: pass
    _orig_admin(route)

SKEW = "(function(){ var n = Date.now; window.__skew = 0; Date.now = function(){ return n.call(Date) + window.__skew; }; })();"
with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={"width": 1100, "height": 900}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.add_init_script(SKEW); pg.add_init_script(FAKE_FIREBASE)
    pg.route("**/enjoy_admin", slow_admin); pg.route("**/enjoy_console_records*", records_route); pg.route("**/enjoy_discovery", disc_route)
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg, T_TODD); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(800)
    check("signed in the first time", pg.locator("#homeView").is_visible())
    for rnd in (1, 2):
        pg.evaluate("window.__skew += 11 * 60 * 1000"); pg.wait_for_selector("#lockView:not([hidden])", timeout=5000)
        msg = pg.locator("#lockMsg").inner_text()
        check(f"round {rnd}: the timeout signs the person out with the inactivity message", "without activity" in msg, msg)
        DELAY["me"] = 2.5
        sign_in(pg, T_TODD)
        try: pg.wait_for_selector("#homeView:not([hidden])", timeout=9000); ok = True
        except Exception: ok = False
        pg.wait_for_timeout(2500)
        msg = pg.locator("#lockMsg").inner_text() if pg.locator("#lockMsg").is_visible() else ""
        check(f"round {rnd}: signing in again after the timeout works (slow answer)", ok and pg.locator("#homeView").is_visible(), msg)
        check(f"round {rnd}: no 'That key did not work' or other error", "key did not work" not in msg and "did not work" not in msg and not pg.locator("#lockView:not([hidden])").count(), msg)
        DELAY["me"] = 0.0
        pg.evaluate("location.hash = '#/home'"); pg.wait_for_timeout(1500)
        check(f"round {rnd}: and it stays signed in", pg.locator("#homeView").is_visible() and not pg.locator("#lockView:not([hidden])").count())
    check("no script errors", not errs, errs)
    b.close()
print("\nOK: all idle re-sign-in checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

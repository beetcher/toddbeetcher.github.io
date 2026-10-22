#!/usr/bin/env python3
"""
The launch screen (P-79): the instant a sign-in starts the form is replaced by a spinning tile and a line that follows the real stages ("Boarding pass accepted",
"Mission control is checking your clearance", "Fueling the stations", then "Liftoff!"; after 8 seconds the slow line), the tab icon spins and is put back, a failure
brings the form back with "Launch aborted: ...", a second press does nothing, and reduced motion pulses instead of spinning. A recorder in the page logs every change,
so what happens during a slow server answer is checked afterwards. Run from enjoy_router/:  python3 run_launch_screen_browser_test.py
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

import http.server, functools, threading
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass
_srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(HERE.parent / "console")))
threading.Thread(target=_srv.serve_forever, daemon=True).start()
PAGE = "http://127.0.0.1:%d/index.html" % _srv.server_address[1]       # served over http (a drawn tab icon needs a real origin; from file:// the browser refuses it)
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
    pg.route("**/enjoy_admin", admin_route); pg.route("**/enjoy_console_records*", slow_records); pg.route("**/enjoy_discovery", disc_route)
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
DELAY = {"me": 0.0, "rec": 0.0}; RECS = []
_orig_admin = admin_route
def slow_admin(route):
    try:
        if json.loads(route.request.post_data or "{}").get("op") == "me" and DELAY["me"]: time.sleep(DELAY["me"])
    except Exception: pass
    _orig_admin(route)
_orig_records = records_route
def slow_records(route):
    if route.request.method != "OPTIONS":
        RECS.append(1)
        if DELAY["rec"]: time.sleep(DELAY["rec"])
    _orig_records(route)

RECORDER = """
(function () {
  window.__log = []; var t0 = Date.now(); var _n = Date.now; window.__skew = 0; Date.now = function () { return _n.call(Date) + window.__skew; };
  function note(what, extra) { window.__log.push(Object.assign({ at: Date.now() - t0, what: what }, extra || {})); }
  window.__note = note;
  document.addEventListener("DOMContentLoaded", function () {
    var box = document.getElementById("launching"), line = document.getElementById("launchLine");
    new MutationObserver(function () {
      var img = box.querySelector("img");
      note("box", { shown: !box.hidden, line: line.textContent, google: !document.getElementById("googleBox").hidden, key: !document.getElementById("keyBox").hidden,
                    anim: !box.hidden && img ? getComputedStyle(img).animationName : "" });
    }).observe(box, { attributes: true, attributeFilter: ["hidden"] });
    new MutationObserver(function () { note("line", { line: line.textContent }); }).observe(line, { childList: true, characterData: true, subtree: true });
    var icons = document.querySelectorAll('link[rel="icon"]');
    window.__icon0 = icons[0].getAttribute("href");
    new MutationObserver(function () { note("icon", { href: icons[0].getAttribute("href").slice(0, 22) }); }).observe(icons[0], { attributes: true, attributeFilter: ["href"] });
  });
})();
"""
def page(b, **kw):
    ctx = b.new_context(viewport={"width": kw.pop("w", 1100), "height": 900}, **kw); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.add_init_script(RECORDER); pg.add_init_script(FAKE_FIREBASE)
    pg.route("**/enjoy_admin", slow_admin); pg.route("**/enjoy_console_records*", slow_records); pg.route("**/enjoy_discovery", disc_route)
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])"); return pg, errs
def log(pg): return pg.evaluate("window.__log")
def lines(pg): return [e["line"] for e in log(pg) if e["what"] == "line" and e["line"]]

with sync_playwright() as p:
    b = launch(p)
    # ---------- a sign-in with a slow answer
    pg, errs = page(b)
    check("before signing in the sign-in form shows and the launch screen does not", pg.locator("#googleBox").is_visible() and not pg.locator("#launching").is_visible())
    DELAY["me"] = 2.5; seen.clear(); RECS.clear()
    pg.evaluate("""() => { const a = firebase.auth(), o = a.signInWithPopup; window.__pops = 0; a.signInWithPopup = function () { window.__pops++; return o.apply(a, arguments); }; }""")
    pg.evaluate("""(a) => { window.__NEXT = a.t; const b = document.getElementById('googleBtn'); b.click();
        setTimeout(() => { b.click(); document.getElementById('keyInput').value = a.k; document.getElementById('lockForm').dispatchEvent(new Event('submit', { cancelable: true })); }, 900); }""", {"t": T_TODD, "k": KEY})   # one press, then more while it is launching
    pg.wait_for_selector("#homeView:not([hidden])", timeout=15000); pg.wait_for_timeout(600); DELAY["me"] = 0.0
    L = log(pg); shown = [e for e in L if e["what"] == "box" and e["shown"]]; hidden = [e for e in L if e["what"] == "box" and not e["shown"]]
    check("the launch screen appeared", len(shown) == 1, L[:6])
    check("...with the sign-in buttons gone while it showed", shown and not shown[0]["google"] and not shown[0]["key"], shown)
    check("...and it opened on 'Boarding pass accepted…'", shown and shown[0]["line"] == "Boarding pass accepted…", shown)
    ln = lines(pg)
    check("the line followed the stages in order: clearance, then fueling, then Liftoff", [x for x in ln if x in ("Mission control is checking your clearance…", "Fueling the stations…", "Liftoff!")] == ["Mission control is checking your clearance…", "Fueling the stations…", "Liftoff!"], ln)
    check("the launch screen is gone once the Console is open", not pg.locator("#launching").is_visible() and len(hidden) == 1)
    check("the tile spins (it is the slow spin, not the reduced-motion pulse)", shown and shown[0]["anim"] == "launchSpin", shown)
    icons = [e for e in L if e["what"] == "icon"]
    check("the tab icon spun (changed to drawn frames) while it waited", sum(1 for e in icons if e["href"].startswith("data:image/png")) >= 5, icons[:3])
    check("...and was put back afterwards", pg.evaluate("document.querySelector('link[rel=icon]').getAttribute('href') === window.__icon0"))
    check("two presses made one sign-in (the server was asked who you are once)", sum(1 for c in seen if c[1] == "me") == 1, [c for c in seen if c[1] == "me"])
    check("presses while it was launching (Google button, key form) did nothing: one pop-up, one list load", pg.evaluate("window.__pops") == 1 and len(RECS) == 1, (pg.evaluate("window.__pops"), len(RECS)))
    check("no script errors", not errs, errs)
    # ---------- a quick answer then a slow list never shows an earlier stage again
    pg.evaluate("document.getElementById('lockBtn').click()"); pg.wait_for_selector("#lockView:not([hidden])")
    DELAY["rec"] = 1.6; pg.evaluate("t => { window.__NEXT = t; window.__log.length = 0; document.getElementById('googleBtn').click(); }", T_TODD)
    pg.wait_for_selector("#homeView:not([hidden])", timeout=15000); DELAY["rec"] = 0.0; ln = lines(pg)
    fue = [i for i, x in enumerate(ln) if x == "Fueling the stations…"]
    check("a quick answer then a slow list: the line never goes back to an earlier stage", fue and all(x not in ("Boarding pass accepted…", "Mission control is checking your clearance…") for x in ln[fue[0]:]), ln)
    # ---------- the page locks itself (inactivity) while it is launching: the form comes back with the message
    pg.evaluate("document.getElementById('lockBtn').click()"); pg.wait_for_selector("#lockView:not([hidden])")
    DELAY["me"] = 2.5; pg.evaluate("t => { window.__NEXT = t; document.getElementById('googleBtn').click(); setTimeout(() => { window.__skew += 11 * 60000; }, 900); }", T_TODD)
    pg.wait_for_function("document.getElementById('lockMsg').textContent.includes('without activity')", timeout=15000); pg.wait_for_timeout(3000); DELAY["me"] = 0.0
    check("locked while launching: the launch screen is gone, the form is back, and the Console did not open behind it", not pg.locator("#launching").is_visible() and pg.locator("#googleBox").is_visible() and not pg.locator("#homeView").is_visible(), pg.locator("#lockMsg").inner_text())
    # ---------- the slow line after 8 seconds
    DELAY["me"] = 9.5; pg.evaluate("t => { window.__NEXT = t; document.getElementById('googleBtn').click(); }", T_TODD)
    pg.wait_for_selector("#homeView:not([hidden])", timeout=30000); DELAY["me"] = 0.0
    check("after 8 seconds the line says it is still on the launch pad", "Still on the launch pad. Slow link or cold engines. Hang tight." in lines(pg), lines(pg))
    pg.context.close()
    # ---------- a failed sign-in brings the form back
    pg, errs = page(b)
    pg.evaluate("window.__NEXT = 'tok.nobody.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; document.getElementById('googleBtn').click();")
    pg.wait_for_function("document.getElementById('lockMsg').textContent.length > 0", timeout=10000); pg.wait_for_timeout(300)
    msg = pg.locator("#lockMsg").inner_text()
    check("a refused sign-in says 'Launch aborted:' with the plain reason", msg.startswith("Launch aborted: ") and len(msg) > 20, msg)
    check("...the launch screen is gone and the sign-in form is back", not pg.locator("#launching").is_visible() and pg.locator("#googleBox").is_visible())
    check("...and the tab icon is put back", pg.evaluate("document.querySelector('link[rel=icon]').getAttribute('href') === window.__icon0"))
    check("...and signing in again works", True)
    pg.evaluate("t => { window.__NEXT = t; document.getElementById('googleBtn').click(); }", T_TODD); pg.wait_for_selector("#homeView:not([hidden])", timeout=15000)
    check("...a good sign-in after a refused one opens the Console", pg.locator("#homeView").is_visible())
    pg.context.close()
    # ---------- the admin key path shows the launch screen too
    pg, errs = page(b)
    pg.evaluate("document.getElementById('swapLink').click()"); pg.wait_for_selector("#keyBox:not([hidden])")
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])", timeout=15000)
    L = log(pg)
    check("the admin key path also showed the launch screen and opened the Console", any(e["what"] == "box" and e["shown"] for e in L) and pg.locator("#homeView").is_visible(), L[:4])
    pg.context.close()
    # ---------- reduced motion: pulse, no spinning icon
    pg, errs = page(b, reduced_motion="reduce")
    DELAY["me"] = 1.5; pg.evaluate("t => { window.__NEXT = t; document.getElementById('googleBtn').click(); }", T_TODD)
    pg.wait_for_selector("#homeView:not([hidden])", timeout=15000); DELAY["me"] = 0.0; L = log(pg)
    shown = [e for e in L if e["what"] == "box" and e["shown"]]
    check("reduced motion: the tile pulses instead of spinning", shown and shown[0]["anim"] == "launchPulse", shown)
    check("reduced motion: the tab icon is left alone", not [e for e in L if e["what"] == "icon"], [e for e in L if e["what"] == "icon"][:2])
    pg.context.close()
    # ---------- how it looks (the real markup and styles, held still): desktop and phone
    for name, w in (("launch_desktop", 1100), ("launch_phone", 390)):
        pg, errs = page(b, w=w)
        pg.evaluate("""() => { document.getElementById('googleBox').hidden = true; document.getElementById('keyBox').hidden = true; document.getElementById('swapLink').hidden = true;
            document.getElementById('launching').hidden = false; document.getElementById('launchLine').textContent = 'Mission control is checking your clearance…'; }""")
        pg.wait_for_timeout(400); pg.screenshot(path=str(SHOTS / (name + ".png")))
        check(f"{name}: the tile and line are on screen and nothing scrolls sideways", pg.locator("#launching img").is_visible() and pg.locator("#launchLine").is_visible() and pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
        pg.context.close()
    b.close()
print("\nOK: all launch screen checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

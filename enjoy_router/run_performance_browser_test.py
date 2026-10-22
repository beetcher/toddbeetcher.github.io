#!/usr/bin/env python3
"""
The Performance station (P-80): a real sign-in sends its timing to the server (record_timing) and the station shows it. Seeded timings are listed,
the 7/30/90 day and device filters work, a manager (no View performance) has no Performance station, the view-only Inspector can look but sends nothing,
and the screens are photographed at desktop and phone width. Run from enjoy_router/:  python3 run_performance_browser_test.py
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


import datetime as _dt
mgr_role = role("manager", [r for r in seed_access.ROLES if r["key"] == "manager"][0]["capabilities"])
T_MGR = person("manager@example.com", mgr_role, "Mia Manager")
def seed(n, days_ago, device, total, check, load, server, cold, role_key="manager", method="google"):
    ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"); i = f"{n:08d}-0000-4000-8000-0000000000aa"
    store.create("performance_events", i, {"id": i, "schema_version": 1, "created_at": ts, "created_by": "user:x", "updated_at": ts, "updated_by": "user:x", "source": "dashboard",
        "kind": "sign_in", "device": device, "method": method, "total_ms": total, "check_ms": check, "load_ms": load, "server_ms": server, "cold": cold, "role_key": role_key})
seed(1, 0.2, "desktop", 6400, 4900, 1300, 420, True)
seed(2, 1.0, "phone", 1500, 700, 650, 90, False, role_key="instructor")
seed(3, 3.0, "desktop", 1200, 500, 600, 80, False)
seed(4, 20.0, "phone", 9000, 7000, 1500, 500, True, role_key="admin")
seed(5, 60.0, "desktop", 2000, 800, 900, 100, False)

with sync_playwright() as p:
    b = launch(p)
    pg, errs = new_page(b)
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    seen.clear(); sign_in(pg, T_TODD); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(1200)
    check("a real sign-in sent its timing to the server", any(c[1] == "record_timing" and c[2] == 200 for c in seen), seen)
    mine = [d for d in store.data["performance_events"].values() if d.get("created_by", "").startswith("user:") and d["role_key"] == "super_admin"]
    check("...stored for the person who signed in, with the page's numbers and the server's cold flag", len(mine) == 1 and mine[0]["total_ms"] >= 0 and mine[0]["device"] == "desktop" and mine[0]["method"] == "google" and isinstance(mine[0].get("cold"), bool) and isinstance(mine[0].get("server_ms"), int), mine)
    check("...and it holds no name, email or token", not any(k in mine[0] for k in ("email", "name", "token", "display_name")) and "todd@example.com" not in json.dumps(mine[0]))
    opts = pg.locator("#collPick option").all_inner_texts()
    check("a super admin has Performance in the station list", "Performance" in " ".join(opts), opts)
    goto(pg, "performance", wait=1500)
    t = pg.locator("#performanceView").inner_text()
    check("the station shows the title and the Sign-in speed section", "Performance" in t and "Sign-in speed" in t, t[:200])
    rowsn = pg.locator("#performanceView .pftab tr").count() - 1
    check("7 days lists the recent sign-ins (the seeded ones from the last week and the real one)", rowsn == 4, rowsn)
    check("the tiles show the count, the typical and slowest time and the share asleep", pg.locator("#performanceView .pfT").count() == 4 and "Server was asleep" in t and "6.4 s" in t, t[:400])
    check("the bar shows where the time goes, with all four parts named", pg.locator("#performanceView .pfstack div").count() >= 3 and "Waking up and network" in t and "Server work" in t and "Loading the lists" in t and "Everything else" in t, t)
    pg.click("#performanceView button[data-days='30']"); pg.wait_for_timeout(200)
    check("30 days brings in the older sign-in", pg.locator("#performanceView .pftab tr").count() - 1 == 5)
    pg.click("#performanceView button[data-days='90']"); pg.wait_for_timeout(200)
    check("90 days brings in the oldest", pg.locator("#performanceView .pftab tr").count() - 1 == 6)
    pg.click("#performanceView button[data-days='7']"); pg.select_option("#pfDevice", "phone"); pg.wait_for_timeout(200)
    check("the device filter narrows to phones", pg.locator("#performanceView .pftab tr").count() - 1 == 1 and "Phone" in pg.locator("#performanceView .pftab").inner_text())
    pg.select_option("#pfDevice", "all"); pg.wait_for_timeout(200)
    check("a cold sign-in is marked yes, a warm one no", "yes" in pg.locator("#performanceView .pftab").inner_text() and "no" in pg.locator("#performanceView .pftab").inner_text())
    pg.screenshot(path=str(SHOTS / "performance_desktop.png"), full_page=True)
    check("the page made no script errors", not errs, errs)
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    # ---------- a manager has no Performance station (and the server refuses her anyway)
    sign_in(pg, T_MGR); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(800)
    check("a manager has no Performance station", "Performance" not in " ".join(pg.locator("#collPick option").all_inner_texts()))
    pg.evaluate("location.hash = '#/performance'"); pg.wait_for_timeout(500)
    check("...and typing the address goes home", not pg.locator("#performanceView").is_visible())
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    # ---------- the Inspector can look, and sends nothing
    seen.clear(); sign_in(pg, T_INSP); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(1000)
    check("the view-only Inspector sends no timing", not any(c[1] == "record_timing" for c in seen), seen)
    goto(pg, "performance", wait=1200)
    check("...and can look at Performance", pg.locator("#performanceView .pftab").count() == 1 and pg.locator("#performanceView .pftab tr").count() - 1 >= 4)
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    # ---------- phone width
    pg2, e2 = new_page(b, w=390); pg2.goto(PAGE); pg2.wait_for_selector("#googleBox:not([hidden])"); sign_in(pg2, T_TODD); pg2.wait_for_selector("#homeView:not([hidden])"); pg2.wait_for_timeout(600)
    goto(pg2, "performance", wait=1200); pg2.screenshot(path=str(SHOTS / "performance_phone.png"), full_page=True)
    check("phone width: nothing scrolls the page sideways (the table scrolls inside itself)", pg2.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg2.evaluate("document.documentElement.scrollWidth"))
    check("phone width: no script errors", not e2, e2)
    b.close()
print("\nOK: all Performance browser checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

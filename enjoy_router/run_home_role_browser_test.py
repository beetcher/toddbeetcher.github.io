#!/usr/bin/env python3
"""Browser test (P-103): Home for the role. A person limited to a territory is told which one; an Instructor sees the classes they teach; a super admin sees neither.
Same sign-in harness as the Help test (a fake Google sign-in, real roles, real territory). Run from enjoy_router/:  python3 run_home_role_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from console import handle_console, make_failure_limiter
from crud import access_persons_crud as PE, access_roles_crud as RO
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin
from memory_store import MemoryStore
from crud import scheduled_classes_crud as CL, individuals_service as IS, attendances_service as AT
from test_helpers import give_address
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

# an Instructor: a role like the seeded one, a person record that teaches Alpha, a sign-in linked to that person
inst_role = role("instructor", ["view_console", "manage_classes"])
base = {"class_type": "group", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 9, "status": "identified"}
def mkc(title, slug, **kw):
    r = CL.create(store, {**base, "title": title, "slug": slug, **kw}, A); assert r.ok, r.problems; return r.data
alpha, bravo, gone = mkc("Alpha basics", "alpha"), mkc("Bravo basics", "bravo"), mkc("Charlie cancelled", "charlie", status="cancelled", cancelled_reason="test")
tina = IS.create(store, {"given_name": "Tina", "family_name": "Teach"}, A).data; give_address(store, tina["id"])
for c in (alpha, gone):
    r = AT.assign(store, {"scheduled_class_id": c["id"], "role": "instructor", "individual_id": tina["id"]}, A); assert r.ok, r.problems   # the server shows an Instructor the classes where they are attached with the role instructor
pi = PE.create(store, {"email": "tina@example.com", "display_name": "Tina Teach", "role_id": inst_role["id"], "individual_id": tina["id"]}, A); assert pi.ok, pi.problems
T_INSTR = "tok.tina.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
V.tokens[T_INSTR] = {"uid": "uid-tina", "email": "tina@example.com", "email_verified": True, "provider": "google.com", "name": "Tina Teach"}

with sync_playwright() as p:
    b = launch(p)
    # a region head (Manager with one regions grant: Boulder)
    pg, errs = new_page(b, w=1440); go(pg, 1440, T_HEAD)
    check("a region head is told their region", pg.locator("#scopeLine").is_visible() and "Boulder" in pg.inner_text("#scopeLine") and "hidden from you" in pg.inner_text("#scopeLine"), pg.inner_text("#scopeLine"))
    check("a region head has no Your classes box", pg.locator("#mineBox").is_hidden())
    # an Instructor
    pg2, errs2 = new_page(b, w=1440); go(pg2, 1440, T_INSTR)
    pg2.wait_for_selector("#mineBox:not([hidden])")
    txt = pg2.inner_text("#mineBody")
    check("an Instructor sees Your classes with the class they teach", pg2.inner_text("#mineBox h3").lower().startswith("your classes") and "Alpha basics" in txt, pg2.inner_text("#mineBox"))
    check("it leaves out a class they do not teach and a cancelled one", "Bravo" not in txt and "Charlie" not in txt, txt)
    check("it has one button to Classes", pg2.locator("#mineBody button[data-go=classes]").inner_text() == "Open Classes")
    check("an Instructor with no territory is not given a region line", pg2.locator("#scopeLine").is_hidden())
    pg2.locator("#mineBody button[data-go=classes]").click(); pg2.wait_for_selector("#classesView:not([hidden])")
    check("Open Classes goes to Classes", pg2.locator("#classesView").is_visible())
    pg2.evaluate("location.hash='#/home'"); pg2.wait_for_selector("#homeView:not([hidden])"); pg2.wait_for_selector("#mineBox:not([hidden])")
    pg2.click("#lockBtn"); pg2.wait_for_selector("#lockView:not([hidden])")
    check("locking hides and empties both role parts", pg2.locator("#mineBox").is_hidden() and pg2.locator("#scopeLine").is_hidden() and pg2.evaluate("document.getElementById('mineBody').children.length === 0"))
    # a super admin
    pg3, errs3 = new_page(b, w=1440); go(pg3, 1440, T_TODD); pg3.wait_for_timeout(500)
    check("a super admin sees neither the region line nor Your classes", pg3.locator("#scopeLine").is_hidden() and pg3.locator("#mineBox").is_hidden())
    check("no page errors", not errs and not errs2 and not errs3, errs + errs2 + errs3)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: home role checks pass"); sys.exit(1 if fails else 0)

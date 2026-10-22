#!/usr/bin/env python3
"""Browser test (P-83 build 3): requests with no active trainer in the real Console page. Real doors over an in-memory store, headless Chromium; a fake Firebase stands in for Google.
Checks: the red chip and the banner count, the No active trainer filter, Mark handled needs a note, the row turns to Handled and the count drops, and the Global Inspector sees the badge but has no Mark handled.
(Based on run_inspector_browser_test.py) Screenshots go to /tmp/claude-0/shots/. Run from enjoy_router/:  python3 run_coverage_console_browser_test.py

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
import comms
from comms.channels.fake import FakeChannel
from crud import comms_settings_crud as CSET, message_templates_crud as MT
from launch_comms import kinds as K
from launch_comms.directory import IndividualDirectory
from launch_comms.stores import LogStore, SettingsStore, TemplateStore
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

# a world with three requests: two from a ZIP no active region holds, one covered
REGION = "a0000000-0000-4000-8000-000000000002"
store.create("discovery_areas", "a0000000-0000-4000-8000-000000000001", {"id": "a0000000-0000-4000-8000-000000000001", "kind": "state", "state_code": "CO", "name": "Colorado", "is_active": True, "schema_version": 1})
store.create("discovery_areas", REGION, {"id": REGION, "kind": "region", "state_code": "CO", "name": "Boulder", "zip_codes": ["80301"], "is_active": True, "schema_version": 1})
def req(n, first, zip_code, **kw):
    rid = "0000%04d-0000-4000-8000-000000000000" % n
    d = {"id": rid, "schema_version": 1, "created_at": "2026-10-22T0%d:00:00Z" % n, "updated_at": "2026-10-22T0%d:00:00Z" % n, "registration_type": "private", "first_name": first,
         "last_name": "Test", "email": first.lower() + ".private@home.example", "phone": "303-555-01%02d" % n, "postal_code": zip_code, "attendee_count": 1,
         "confirmation_number": "ICDT-TEST0%d" % n, **kw}
    store.create("registration_requests", rid, d); return rid
R1 = req(1, "Barty", "80202", coverage="no_active_region", coverage_state_code="CO")
R2 = req(2, "Cora", "80202", coverage="no_active_region", coverage_state_code="CO")
R3 = req(3, "Dana", "80301", coverage="covered", coverage_state_code="CO")
SECRETS = ["barty.private@home.example", "303-555-0101", "cora.private@home.example", "80202"]
class RegView:
    """The registration store the records door reads, over the same documents the admin door changes."""
    def list_requests(self, limit, since=None):
        rows = sorted(store.query("registration_requests", [], limit=500), key=lambda r: r["created_at"], reverse=True)
        return [r for r in rows if not since or r["created_at"] >= since][:limit]
    def list_areas(self): return store.query("discovery_areas", [], limit=1000)

SEED = json.loads((HERE.parent / "schemas" / "examples" / "message_template.seed.json").read_text())["templates"]
for tpl in SEED:
    rr = MT.create(store, {k: tpl[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A); assert rr.ok, rr.problems; assert MT.publish(store, rr.data["id"], A).ok
assert CSET.create(store, {}, A).ok
chan = FakeChannel()
comms.configure(comms.Comms(kinds=K.registry(), directory=IndividualDirectory(store), templates=TemplateStore(store), log=LogStore(store), settings=SettingsStore(store),
                            channels=[chan], mode="live"))
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
    r = handle_console("GET", q.headers.get("authorization", ""), {}, KEY, "v", RegView(), climiter, datetime.now(timezone.utc), verifier=V, access_store=store)
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


def banner(pg): return pg.locator("#covBanner").inner_text().strip() if pg.locator("#covBanner").is_visible() else ""
with sync_playwright() as p:
    b = launch(p)
    pg, errs = new_page(b)
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg, T_TODD); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(700)
    check("Home: says how many requests wait for a trainer", "2 requests are waiting for a trainer" in pg.locator("#attnBox").inner_text(), pg.locator("#attnBox").inner_text()[:300])
    goto(pg, "requests")
    check("Requests: the banner counts the waiting ones", banner(pg).startswith("2 requests are waiting for a trainer"), banner(pg))
    check("Requests: two red chips, none on the covered request", pg.locator("#list .nochip").count() == 2)
    pg.screenshot(path=str(SHOTS / "coverage_banner.png"))
    pg.select_option("#reqShow", "notrainer"); pg.wait_for_timeout(300)
    check("Filter: No active trainer shows exactly those two", pg.locator("#list li:visible").count() == 2 and "2 requests with no active trainer" in pg.locator("#countText").inner_text(), pg.locator("#countText").inner_text())
    pg.select_option("#reqShow", "open"); pg.wait_for_timeout(200)
    pg.locator("#covBanner button", has_text="Show them").click(); pg.wait_for_timeout(300)
    check("The banner's Show them applies the filter", pg.locator("#reqShow").input_value() == "notrainer" and pg.locator("#list li:visible").count() == 2)
    first = pg.locator("#list li:visible").first
    first.locator("button.head").click(); pg.wait_for_timeout(200)
    first.locator("button", has_text="Mark handled").click(); pg.wait_for_timeout(200)
    box = first.locator(".covbox"); check("Mark handled opens a form asking what was done", box.is_visible() and "required" in box.inner_text())
    box.locator("button", has_text="Mark handled").click(); pg.wait_for_timeout(200)
    check("An empty note is refused in red and nothing is saved", "Say what was done" in box.inner_text() and not [d for d in store.query("registration_requests", [], limit=50) if d.get("coverage_handled_at")])
    pg.screenshot(path=str(SHOTS / "coverage_mark_form.png"))
    box.locator("textarea").fill("Phoned her; a trainer from Fort Collins will drive down."); box.locator("button", has_text="Mark handled").click(); pg.wait_for_timeout(800)
    done = [d for d in store.query("registration_requests", [], limit=50) if d.get("coverage_handled_at")]
    check("With a note it is saved on the server with who and when", len(done) == 1 and done[0]["coverage_handled_note"].startswith("Phoned") and done[0]["coverage_handled_by"].startswith("user:"), done)
    check("The banner drops to 1 and the handled one leaves the filter", banner(pg).startswith("1 request is waiting") and pg.locator("#list li:visible").count() == 1, (banner(pg), pg.locator("#list li:visible").count()))
    pg.select_option("#reqShow", "all"); pg.wait_for_timeout(200)
    check("The handled request shows a Handled chip, not the red one", pg.locator("#list .donechip").count() == 1 and pg.locator("#list .nochip").count() == 1)
    pg.screenshot(path=str(SHOTS / "coverage_after.png"))
    pg.select_option("#reqShow", "open"); pg.wait_for_timeout(200)
    pg.locator("#covBanner button", has_text="Send reminders now").click(); pg.wait_for_timeout(1200)
    done_txt = pg.locator("#reqDone").inner_text()
    check("Send reminders now: says who was told, and the emails really went (to the super admin and the Inspector)", "Reminders sent to 2 people about 1 request waiting for a trainer" in done_txt and sorted(x["to"] for x in chan.sent) == ["inspector@example.com", "todd@example.com"], (done_txt, [x["to"] for x in chan.sent]))
    pg.screenshot(path=str(SHOTS / "coverage_reminders.png"))
    check("no script errors (super admin)", not errs, errs)

    pg2, errs2 = new_page(b)
    pg2.goto(PAGE); pg2.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg2, T_INSP); pg2.wait_for_selector("#homeView:not([hidden])"); pg2.wait_for_timeout(700)
    goto(pg2, "requests")
    check("Inspector: sees the banner and the red chip", banner(pg2).startswith("1 request is waiting") and pg2.locator("#list .nochip").count() == 1, banner(pg2))
    pg2.locator("#list li", has=pg2.locator(".nochip")).first.locator("button.head").click(); pg2.wait_for_timeout(200)
    txt = pg2.locator("#listView").inner_text()
    check("Inspector: no Mark handled button, and no private value or note on screen", pg2.locator("button", has_text="Mark handled").count() == 0 and not any(s in txt for s in SECRETS) and "Fort Collins" not in txt, txt[:300])
    check("Inspector: no Send reminders now button either", pg2.locator("button", has_text="Send reminders now").count() == 0)
    pg2.select_option("#reqShow", "all"); pg2.wait_for_timeout(200)
    check("Inspector: the handled request's note is not shown", "Fort Collins" not in pg2.locator("#listView").inner_text())
    pg2.screenshot(path=str(SHOTS / "coverage_inspector.png"))
    check("no script errors (inspector)", not errs2, errs2)
    b.close()
print("FAILED" if fails else "all checks passed", len(fails)); sys.exit(1 if fails else 0)

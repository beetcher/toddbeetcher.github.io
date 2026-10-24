#!/usr/bin/env python3
"""Browser test (Console 2.1): the Requests station on the List page template - visible title, count and last-checked under it, the Show filter as a segmented control with radio-group keys, a two-column card grid at desktop width that opens an expanded card across both columns, and the phone layout. Same fixture as the coverage test. Run from enjoy_router/:  python3 run_requests_browser_test.py"""
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
VENUE = "b0000000-0000-4000-8000-000000000001"; CURR = "c0000000-0000-4000-8000-000000000001"
store.create("venues", VENUE, {"id": VENUE, "name": "Test Hall", "status": "active", "place": {"address": {"locality": "Boulder"}, "time_zone": "America/Denver"}, "schema_version": 1})
store.create("curriculums", CURR, {"id": CURR, "title": "Test Basics", "status": "active", "session_count": 1, "minutes_per_session": 60, "schema_version": 1})
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
    from urllib.parse import urlparse, parse_qs
    r = handle_console("GET", q.headers.get("authorization", ""), {k: v[0] for k, v in parse_qs(urlparse(q.url).query).items()}, KEY, "v", RegView(), climiter, datetime.now(timezone.utc), verifier=V, access_store=store)
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
    pg.set_viewport_size({"width": 1440, "height": 1000})
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg, T_TODD); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(700)
    pg.click('#sideNav a[data-nav="requests"]'); pg.wait_for_selector("#list li", state="attached"); pg.wait_for_timeout(600)
    check("the page has one visible title, Registration requests", pg.locator("#reqTitle").is_visible() and pg.locator("#reqTitle").inner_text() == "Registration requests" and pg.locator("#listView h2:visible").count() == 1)
    check("the count and last-checked sit under the title", pg.evaluate("(function(){var t=document.getElementById('reqTitle').getBoundingClientRect(),c=document.getElementById('countText').getBoundingClientRect(),m=document.getElementById('checkedText').getBoundingClientRect(); return t.bottom<=c.top+1 && c.bottom<=m.top+1})()"))
    check("the tab title names the station", pg.title().startswith("Requests"), pg.title())
    segs = pg.locator("#reqSeg button")
    check("the Show filter is a radio group of five", pg.get_attribute("#reqSeg", "role") == "radiogroup" and segs.count() == 5 and [__import__("re").sub(r"\s*\d+\s*$", "", x) for x in segs.all_inner_texts()] == ["Open", "Closed", "All", "No active trainer", "Deleted"], segs.all_inner_texts())
    check("Open is chosen at first, the others are out of the tab order", pg.get_attribute('#reqSeg [data-v="open"]', "aria-checked") == "true" and pg.evaluate("Array.from(document.querySelectorAll('#reqSeg button')).filter(b => b.tabIndex === 0).length") == 1)
    check("no drop-down for it on the page (the stored select is hidden)", pg.locator("#reqShow").is_hidden())
    cols = pg.evaluate("getComputedStyle(document.getElementById('list')).gridTemplateColumns.split(' ').length")
    check("at desktop width the cards sit in two columns", cols == 2, cols)
    xs = pg.evaluate("Array.from(document.querySelectorAll('#list > li')).filter(li => li.offsetParent).map(li => Math.round(li.getBoundingClientRect().left))")
    check("the first two cards are side by side", len(set(xs[:2])) == 2, xs)
    pg.screenshot(path="/tmp/claude-0/requests_1440.png")
    pg.locator("#list > li:visible button.head").first.click(); pg.wait_for_timeout(150)
    w = pg.evaluate("(function(){var li=document.querySelector('#list > li.open'); var l=document.getElementById('list').getBoundingClientRect(); var r=li.getBoundingClientRect(); return [Math.round(r.width), Math.round(l.width)]})()")
    check("an opened card spans both columns", abs(w[0] - w[1]) <= 2, w)
    pg.screenshot(path="/tmp/claude-0/requests_1440_open.png")
    pg.locator("#list > li.open button.head").click()
    # keyboard
    pg.focus('#reqSeg [data-v="open"]'); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(100)
    check("the right arrow chooses Closed and moves focus", pg.get_attribute('#reqSeg [data-v="closed"]', "aria-checked") == "true" and pg.evaluate("document.activeElement.dataset.v") == "closed")
    pg.keyboard.press("End"); pg.wait_for_timeout(100)
    check("End chooses the last one, Deleted, and shows no normal cards", pg.get_attribute('#reqSeg [data-v="deleted"]', "aria-checked") == "true" and pg.locator("#list > li:visible").count() == 0)
    pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(300)
    check("the left arrow moves to No active trainer and shows exactly those", pg.get_attribute('#reqSeg [data-v="notrainer"]', "aria-checked") == "true" and pg.locator("#list > li:visible").count() == 2 and "2 requests with no active trainer" in pg.locator("#countText").inner_text(), pg.locator("#countText").inner_text())
    pg.keyboard.press("Home"); pg.wait_for_timeout(100)
    check("Home goes back to Open", pg.get_attribute('#reqSeg [data-v="open"]', "aria-checked") == "true" and pg.locator("#list > li:visible").count() == 3)
    pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(100)
    check("the left arrow from the first wraps to the last, Deleted", pg.get_attribute('#reqSeg [data-v="deleted"]', "aria-checked") == "true")
    pg.click('#reqSeg [data-v="open"]')
    # the banner's Show them still drives the control
    pg.click("#covBanner button:has-text('Show them')"); pg.wait_for_timeout(150)
    check("the banner's Show them selects No active trainer in the control", pg.get_attribute('#reqSeg [data-v="notrainer"]', "aria-checked") == "true")
    pg.click('#reqSeg [data-v="all"]'); pg.wait_for_timeout(100)
    check("All shows the count of every request", "3 requests" in pg.locator("#countText").inner_text(), pg.locator("#countText").inner_text())
    pg.click('#reqSeg [data-v="open"]')
    # one column below the sidebar width
    pg.set_viewport_size({"width": 1000, "height": 900}); pg.wait_for_timeout(250)
    cols = pg.evaluate("getComputedStyle(document.getElementById('list')).gridTemplateColumns.split(' ').length")
    check("below the sidebar width the cards stack in one column", cols == 1, cols)
    # Delete, then Undo (C-7): the server restores the request and the card comes back
    n0 = pg.locator("#list > li:visible").count()
    pg.locator("#list > li:visible").first.get_by_role("button", name="Delete").click()
    pg.locator("#list > li:visible").first.get_by_role("button", name="Really delete").click(); pg.wait_for_timeout(600)
    check("deleting hides the card and offers Undo", pg.locator("#list > li:visible").count() == n0 - 1 and pg.locator("#reqDone button", has_text="Undo").is_visible(), pg.locator("#reqDone").inner_text())
    pg.locator("#reqDone button", has_text="Undo").click(); pg.wait_for_timeout(900)
    check("Undo brings the card back", pg.locator("#list > li:visible").count() == n0 and "is back in the list" in pg.locator("#reqDone").inner_text(), pg.locator("#reqDone").inner_text())
    # ---- Deleted filter and Restore: the deleted request can be found again after the Undo bar is gone
    pg.locator("#list > li:visible").first.get_by_role("button", name="Delete (").click(); pg.locator("#list > li:visible").first.get_by_role("button", name="Really delete").click(); pg.wait_for_timeout(600)
    pg.click('#reqSeg [data-v="deleted"]'); pg.wait_for_selector("#delList li")
    check("Deleted filter lists the deleted request with a Restore button, and no normal cards", pg.locator("#delList li button", has_text="Restore").count() >= 1 and pg.locator("#list > li:visible").count() == 0, pg.locator("#delList").inner_text())
    check("a deleted card says Deleted and offers no Delete or Put in a class", "Deleted" in pg.locator("#delList li").first.inner_text() and pg.locator("#delList li button", has_text="Delete").count() == 0 and pg.locator("#delList li button", has_text="Put in").count() == 0)
    n_del = pg.locator("#delList li").count()
    pg.locator("#delList li").first.get_by_role("button", name="Restore").click()
    pg.wait_for_function("document.getElementById('reqDone').textContent.indexOf('is back in the list') >= 0")
    check("Restore takes it off the Deleted list and says so", pg.locator("#delList li").count() == n_del - 1)
    pg.click('#reqSeg [data-v="open"]'); pg.wait_for_timeout(500)
    check("the restored card is back in Open", pg.locator("#list > li:visible").count() == n0, pg.locator("#list > li:visible").count())
    # phone
    pg.set_viewport_size({"width": 390, "height": 900}); pg.wait_for_timeout(250)
    check("no sideways scroll on a phone", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    check("every segment is at least 44px tall and wide enough to tap on a phone", pg.evaluate("Array.from(document.querySelectorAll('#reqSeg button')).every(b => b.getBoundingClientRect().height >= 44 && b.getBoundingClientRect().width >= 80)"))
    check("on a phone the station picker is wide enough to read and the name is not cut off", pg.evaluate("(function(){var s=document.getElementById('collPick').getBoundingClientRect(), w=document.getElementById('who'); return s.width >= 100 && w.scrollWidth <= w.clientWidth + 1})()"))
    pg.screenshot(path="/tmp/claude-0/requests_390.png")
    # ---- shared names (R-1): the venue and curriculum names have one owner, console/names.js (window.ConsoleNames), and leave the page on sign-out
    check("names.js is its own file loaded after console.js and ConsoleNames is there", pg.evaluate("typeof window.ConsoleNames === 'object' && ['loadVenueChoices','loadCurriculumChoices','venues','venueById','curricula','venueAsked','curriculumAsked','reset'].every(k => typeof ConsoleNames[k] === 'function')"))
    ok_v = pg.evaluate("ConsoleNames.loadVenueChoices().then(ok => ok === true && ConsoleNames.venues().length === 1 && ConsoleNames.venueAsked('%s') === 'Test Hall, Boulder' && ConsoleNames.venueById('%s').name === 'Test Hall')" % (VENUE, VENUE))
    check("the venue names load through names.js and say 'Name, Town'", ok_v)
    ok_c = pg.evaluate("ConsoleNames.loadCurriculumChoices().then(ok => ok === true && ConsoleNames.curricula().length === 1 && ConsoleNames.curriculumAsked('%s') === 'Test Basics')" % CURR)
    check("the curriculum titles load through names.js", ok_c)
    src_big = (HERE.parent / "console" / "console.js").read_text()
    check("nothing of the name caches is left in console.js", not __import__("re").search(r"\b(cVenues|cVenueById|cCurricula|venueChipFetch|curChipFetch|refreshVenueChips|refreshCurriculumChips)\b|function (loadVenueChoices|loadCurriculumChoices|venueAsked|curriculumAsked)\b", src_big))
    # ---- shared dialogs (R-2): the Journal has one owner, console/dialogs.js (window.ConsoleDialogs); Put in a class stays with Attendance for now
    check("dialogs.js is its own file and ConsoleDialogs.openJournal is there", pg.evaluate("typeof window.ConsoleDialogs === 'object' && typeof ConsoleDialogs.openJournal === 'function'"))
    pg.set_viewport_size({"width": 1100, "height": 900}); pg.wait_for_timeout(150)
    pg.locator("#list > li:visible").first.get_by_role("button", name="History").click(); pg.wait_for_selector("#jrDlg[open]")
    pg.wait_for_function("document.getElementById('jrBody').textContent.indexOf('Nothing has happened here yet') >= 0")
    check("History on a request card opens the Journal (through dialogs.js) and says so when nothing has happened", pg.locator("#jrTitle").inner_text().startswith("History: ") and pg.locator("#jrDlg").is_visible())
    pg.click("#jrClose"); pg.wait_for_timeout(150)
    check("Close shuts the Journal", not pg.evaluate("document.getElementById('jrDlg').open"))
    check("nothing of the Journal is left in console.js", not __import__("re").search(r"\bJR_WORD\b|function openJournal\b|\$\(\"jrClose\"\)", src_big))
    # inspector keeps the view
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    # ---- the Requests station (R-4): its own file, nothing left behind, hooks work, sign-out empties it, the 20 second check starts and stops with the sign-in
    check("requests.js is its own file and RequestsStation has every hook", pg.evaluate("typeof window.RequestsStation === 'object' && ['show','start','stop','check','loadPlaced','reset','clearList','adopt','records'].every(k => typeof RequestsStation[k] === 'function')"))
    check("nothing of the Requests station is left in console.js", not __import__("re").search(r"function (buildRow|fillCovBox|merge|check|startTimer|stopTimer|loadPlaced|decorateCards|fillQRow|applyReqFilter|pickReq|loadDeleted|renderAttention|newest)\b|\bvar (known = \{\}|rows = \{\}|firstLoadDone = false|timer = null;)|var P = \{ loaded", src_big))
    check("requests.js reaches the big file only through the kit and the shared files (no station, no borrowed name)", "window.ConsoleKit" in (HERE.parent / "console" / "requests.js").read_text())
    check("sign-out empties the Requests page and its data", pg.evaluate("document.querySelectorAll('#list li').length === 0 && RequestsStation.records().length === 0 && document.getElementById('countText').textContent === ''"))
    check("sign-out empties the name caches", pg.evaluate("ConsoleNames.venues().length === 0 && ConsoleNames.curricula().length === 0 && ConsoleNames.venueAsked('%s') === ''" % VENUE))
    # the 20 second check, on a fake clock in its own page: runs while signed in on Requests, stops when the Console locks
    pg2, errs2 = new_page(b, 1100); gets = []
    pg2.on("request", lambda r: gets.append(r.url) if "enjoy_console_records" in r.url and r.method == "GET" else None)
    pg2.clock.install()
    pg2.goto(PAGE); pg2.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg2, T_TODD); pg2.wait_for_selector("#homeView:not([hidden])"); pg2.wait_for_timeout(500)
    pg2.select_option("#collPick", "requests"); pg2.wait_for_selector("#list li", state="attached"); pg2.wait_for_timeout(500)
    n1 = len(gets); pg2.clock.fast_forward(21000); pg2.wait_for_timeout(600); n2 = len(gets)
    check("on Requests the 20 second check runs", n2 > n1, (n1, n2))
    pg2.click("#lockBtn"); pg2.wait_for_selector("#lockView:not([hidden])"); n3 = len(gets); pg2.clock.fast_forward(45000); pg2.wait_for_timeout(600)
    check("after the Console locks the check stops", len(gets) == n3, (n3, len(gets)))
    pg2.wait_for_selector("#googleBox:not([hidden])"); pg2.wait_for_timeout(800)
    sign_in(pg2, T_TODD); pg2.wait_for_selector("#list li", state="attached"); pg2.wait_for_timeout(800)   # the page comes back on Requests (the address still says so)
    check("signing back in loads the list again", pg2.locator("#list > li:visible").count() == 3, pg2.locator("#list > li:visible").count())
    n4 = len(gets); pg2.clock.fast_forward(21000); pg2.wait_for_timeout(600)
    check("and the 20 second check runs again", len(gets) > n4, (n4, len(gets)))
    pg2.select_option("#collPick", "home"); pg2.wait_for_timeout(300); n5 = len(gets); pg2.clock.fast_forward(45000); pg2.wait_for_timeout(600)
    check("leaving Requests stops the check", len(gets) == n5, (n5, len(gets)))
    # ---- Search and Region (S build): tags, instant narrowing, the Region chip, and a server search that reaches past the newest 200
    pg3, errs3 = new_page(b, 1100); pg3.goto(PAGE); pg3.wait_for_selector("#googleBox:not([hidden])")
    sign_in(pg3, T_TODD); pg3.wait_for_selector("#homeView:not([hidden])"); pg3.wait_for_timeout(500)
    pg3.select_option("#collPick", "requests"); pg3.wait_for_selector("#list li", state="attached"); pg3.wait_for_timeout(500)
    check("every card names its region, or says none yet", pg3.evaluate("Array.from(document.querySelectorAll('#list > li .rtag')).map(e => e.textContent).sort().join('|')") == "Region: Boulder|Region: none yet|Region: none yet")
    check("the Search box and the Region chip sit above the list", pg3.locator("#rSearch").is_visible() and pg3.locator("#rChips .cf-chip").count() == 1)
    pg3.fill("#rSearch", "dana"); pg3.wait_for_timeout(150)
    check("typing in Search narrows the list at once", pg3.locator("#list > li:visible").count() == 1 and "Dana" in pg3.locator("#list > li:visible").inner_text())
    check("the count line says how many match", "1 request matches" in pg3.locator("#countText").inner_text(), pg3.locator("#countText").inner_text())
    pg3.fill("#rSearch", "zzzz"); pg3.wait_for_timeout(700)
    check("no match says so and offers the way back", pg3.locator("#list > li:visible").count() == 0 and "No request matches" in pg3.locator("#empty").inner_text())
    pg3.fill("#rSearch", ""); pg3.wait_for_timeout(700)
    pg3.click("#rChips .cf-chip"); pg3.wait_for_selector("#rChips .cf-pop:not([hidden])")
    opts = pg3.eval_on_selector_all("#rChips .cf-pop:not([hidden]) label.cf-opt", "els => els.map(e => e.textContent.trim().replace(/\\s*\\d*$/, ''))")
    check("the Region chip lists the region and No region yet", any("Boulder" in o for o in opts) and any("No region yet" in o for o in opts), opts)
    pg3.locator("#rChips .cf-pop:not([hidden]) label.cf-opt", has_text="Boulder").click(); pg3.keyboard.press("Escape"); pg3.wait_for_timeout(700)
    shown = pg3.eval_on_selector_all("#list > li:visible", "els => els.map(e => e.innerText)")
    check("unticking Boulder hides Dana and keeps the others", len(shown) == 2 and not any("Dana" in t for t in shown), shown)
    pg3.click("#rChips .cf-clearall"); pg3.wait_for_timeout(700)
    check("Clear all brings every request back", pg3.locator("#list > li:visible").count() == 3)
    # the server reaches past the newest 200: 200 newer requests push an old one out of the first page
    for i in range(200):
        fid = "f%07d-0000-4000-8000-000000000000" % i
        store.create("registration_requests", fid, {"id": fid, "schema_version": 1, "created_at": "2026-10-23T12:%02d:%02dZ" % (i // 60, i % 60), "updated_at": "2026-10-23T12:00:00Z", "registration_type": "private",
                     "first_name": "Fill%03d" % i, "last_name": "Filler", "email": "fill%d@home.example" % i, "postal_code": "80301", "attendee_count": 1, "confirmation_number": "ICDT-FILL%03d" % i})
    OLD = "e0000000-0000-4000-8000-000000000001"
    store.create("registration_requests", OLD, {"id": OLD, "schema_version": 1, "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z", "registration_type": "private",
                 "first_name": "Olive", "last_name": "Ancient", "email": "olive@home.example", "postal_code": "99999", "attendee_count": 1, "confirmation_number": "ICDT-OLD001"})
    pg3.click("#refreshBtn"); pg3.wait_for_timeout(1200)
    check("the newest page is listed and the old request is not", pg3.locator("#list > li").count() >= 100 and "Olive" not in pg3.locator("#list").inner_text())
    pg3.fill("#rSearch", "olive"); pg3.wait_for_function("document.getElementById('list').innerText.indexOf('Olive') >= 0", timeout=5000)
    check("Search asks the server and finds the request older than the first page", pg3.locator("#list > li:visible").count() == 1 and "Region: none yet" in pg3.locator("#list > li:visible").inner_text())
    check("the old request sits at the bottom, in date order, and is not marked new", pg3.evaluate("(() => { var l = Array.from(document.querySelectorAll('#list > li')); return l[l.length - 1].innerText.indexOf('Olive') >= 0 && !l[l.length - 1].classList.contains('isnew'); })()"))
    pg3.fill("#rSearch", ""); pg3.wait_for_timeout(400)
    pg3.click("#lockBtn"); pg3.wait_for_selector("#lockView:not([hidden])")
    check("sign-out empties the search box and the Region chip", pg3.evaluate("document.getElementById('rSearch').value === '' && document.getElementById('rChips').children.length === 0"))
    errs += errs3
    check("no script errors", not errs and not errs2, errs + errs2)
    b.close()

if fails:
    print("\nFAILED:", len(fails)); sys.exit(1)
print("\nOK: all Requests template browser checks pass")

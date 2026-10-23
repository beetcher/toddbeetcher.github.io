#!/usr/bin/env python3
"""Browser test (Console step 1.3a): the shared parts in ui.js - dialog, chip, banner, empty state - and the Discard box that replaced the
browser's confirm(). Same harness as the sidebar test. Run from enjoy_router/:  python3 run_console_ui_browser_test.py"""
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
    go(pg, 1440, T_TODD)

    # ---- dialog
    pg.focus('#sideNav a[data-nav="messages"]')
    pg.evaluate(ASK % '{ title: "Delete it?", message: "This cannot be undone.", yes: "Delete", no: "Keep", danger: true }')
    pg.wait_for_selector("#uiDialog[open]")
    check("the dialog shows its title, message and button words", pg.locator("#uiTitle").inner_text() == "Delete it?" and pg.locator("#uiMsg").inner_text() == "This cannot be undone." and pg.locator("#uiYes").inner_text() == "Delete" and pg.locator("#uiNo").inner_text() == "Keep")
    check("it is a labelled modal dialog", pg.evaluate("(function(){var d=document.getElementById('uiDialog'); return d.matches(':modal') && d.getAttribute('aria-labelledby')==='uiTitle' && d.getAttribute('aria-describedby')==='uiMsg';})()"))
    check("a risky question puts focus on the safe button", pg.evaluate("document.activeElement.id") == "uiNo")
    pg.screenshot(path="/tmp/claude-0/ui_dialog_1440.png")
    for _ in range(6): pg.keyboard.press("Tab")
    check("Tab cannot leave the dialog", pg.evaluate("document.getElementById('uiDialog').contains(document.activeElement)"))
    pg.click("#uiYes"); pg.wait_for_timeout(100)
    check("Yes answers true and closes it", ans(pg) is True and not pg.locator("#uiDialog[open]").count())
    check("focus goes back to where it was", pg.evaluate("document.activeElement.dataset.nav") == "messages")
    pg.evaluate(ASK % '{ title: "Go on?" }'); pg.wait_for_selector("#uiDialog[open]")
    check("an ordinary question puts focus on Yes, and hides an empty message", pg.evaluate("document.activeElement.id") == "uiYes" and pg.locator("#uiMsg").is_hidden())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape answers false", ans(pg) is False and not pg.locator("#uiDialog[open]").count())
    pg.evaluate(ASK % '{ title: "Again?" }'); pg.wait_for_selector("#uiDialog[open]"); pg.click("#uiNo"); pg.wait_for_timeout(100)
    check("Cancel answers false", ans(pg) is False)
    pg.evaluate(ASK % '{ title: "Outside?" }'); pg.wait_for_selector("#uiDialog[open]"); pg.mouse.click(5, 400); pg.wait_for_timeout(100)
    check("a click on the dimmed area answers false", ans(pg) is False and not pg.locator("#uiDialog[open]").count())
    pg.evaluate("window.__first = undefined; UI.confirm({ title: 'One' }).then(function (a) { window.__first = a; }); UI.confirm({ title: 'Two' }).then(function (a) { window.__ans = a; }); 0;")
    pg.wait_for_timeout(100)
    check("a second question closes the first as no and shows itself", pg.evaluate("window.__first") is False and pg.locator("#uiTitle").inner_text() == "Two")
    pg.click("#uiYes"); pg.wait_for_timeout(100)
    pg.evaluate(ASK % '{ title: "Lock test" }'); pg.wait_for_selector("#uiDialog[open]")
    pg.evaluate("document.getElementById('lockBtn').click()") if False else pg.evaluate("UI.dismiss()")
    check("dismiss() closes an open dialog as no", ans(pg) is False and not pg.locator("#uiDialog[open]").count())

    # ---- chip, banner, empty state
    r = pg.evaluate("""(function(){
      var c = UI.chip('ok', 'Placed'), e = UI.banner('err', 'Not saved'), w = UI.banner('warn', 'Careful'), em = UI.empty('Nothing here', 'Add one', document.createElement('button'));
      return { chip: [c.className, c.textContent], err: [e.className, e.getAttribute('role'), e.textContent], warn: [w.getAttribute('role')], empty: [em.className, em.children.length, em.querySelector('button') !== null] };})()""")
    check("a chip is words in a coloured pill", r["chip"] == ["chip chip-ok", "Placed"], r["chip"])
    check("an error banner is announced at once; the others politely", r["err"] == ["banner banner-err", "alert", "Not saved"] and r["warn"] == ["status"], r)
    check("an empty state has a title, a hint and an action", r["empty"] == ["empty", 3, True], r["empty"])


    # ---- filter bar, in Venues (Status, State, Region)
    pg.click('#sideNav a[data-nav="venues"]'); pg.wait_for_selector("#addBtn"); pg.wait_for_function("document.getElementById('vChecked').textContent.length > 0")
    check("Venues has one Filters button, closed by default, with its three selects tucked away", pg.locator("#vFilterBtn").inner_text() == "Filters" and pg.get_attribute("#vFilterBtn", "aria-expanded") == "false" and not pg.locator("#vFilter").is_visible() and not pg.locator("#vState").is_visible() and not pg.locator("#vRegion").is_visible())
    check("no chips and no stray panel while nothing is filtered", pg.locator("#vFilterPanel").is_hidden() and pg.locator(".fchips .chip").count() == 0)
    pg.click("#vFilterBtn")
    check("the button opens the panel with the three labelled selects", pg.get_attribute("#vFilterBtn", "aria-expanded") == "true" and pg.locator("#vFilter").is_visible() and pg.locator("#vFilterPanel label.flab").all_inner_texts() and [t.split("\n")[0] for t in pg.locator("#vFilterPanel label.flab").all_inner_texts()] == ["Status", "State", "Region"])
    pg.select_option("#vFilter", "active"); pg.wait_for_timeout(500)
    check("choosing a status shows a chip and puts the count on the button", pg.locator(".fchips .chip").inner_text().replace("\n", "").startswith("Status: Active") and pg.locator("#vFilterBtn").inner_text() == "Filters (1)", pg.locator("#vFilterBtn").inner_text())
    check("the chip's remove button names what it removes", pg.locator(".fchips .fx").get_attribute("aria-label") == "Remove filter Status: Active")
    pg.screenshot(path="/tmp/claude-0/ui_filters_1440.png")
    pg.click(".fchips .fx"); pg.wait_for_timeout(500)
    check("removing the chip puts the filter back to All and the count back to Filters", pg.input_value("#vFilter") == "" and pg.locator(".fchips .chip").count() == 0 and pg.locator("#vFilterBtn").inner_text() == "Filters")
    check("focus lands on the Filters button after a removal", pg.evaluate("document.activeElement.id") == "vFilterBtn")
    r = pg.evaluate("""(function(){
      var bar = document.createElement('div'); bar.id = 'pbar'; var b = document.createElement('button'); b.id = 'pbtn'; bar.appendChild(b);
      var a = document.createElement('select'), c = document.createElement('select'), fired = [];
      [['A', ['All', 'x', 'y']], ['C', ['Any', 'p']]].forEach(function (d, i) { var s = i ? c : a; d[1].forEach(function (t, j) { var o = document.createElement('option'); o.value = j ? t : ''; o.textContent = t; s.appendChild(o); }); s.addEventListener('change', function () { fired.push(d[0]); }); });
      document.body.appendChild(bar);
      var fb = UI.filterBar({ id: 'p', toggleBefore: b, after: bar, fields: [{ el: a, label: 'Alpha' }, { el: c, label: 'Charlie' }] });
      a.value = 'x'; c.value = 'p'; a.dispatchEvent(new Event('change')); c.dispatchEvent(new Event('change'));
      var two = { btn: document.getElementById('pFilterBtn').textContent, chips: document.querySelectorAll('#pbar + .fwrap .chip').length, clear: !!document.querySelector('#pbar + .fwrap .fclear') };
      document.querySelector('#pbar + .fwrap .fclear').click();
      return { two: two, a: a.value, c: c.value, fired: fired.slice(2), after: document.getElementById('pFilterBtn').textContent, chipsAfter: document.querySelectorAll('#pbar + .fwrap .chip').length, clearAfter: !!document.querySelector('#pbar + .fwrap .fclear') };})()""")
    check("two filters on: 'Filters (2)', two chips and a Clear all", r["two"] == {"btn": "Filters (2)", "chips": 2, "clear": True}, r["two"])
    check("Clear all sets every filter off and tells each select's own listeners", r["a"] == "" and r["c"] == "" and sorted(r["fired"]) == ["A", "C"] and r["after"] == "Filters" and r["chipsAfter"] == 0 and not r["clearAfter"], r)
    pg.set_viewport_size({"width": 390, "height": 900}); pg.wait_for_timeout(300)
    if pg.locator("#vFilterPanel").is_hidden(): pg.click("#vFilterBtn")
    pg.screenshot(path="/tmp/claude-0/ui_filters_390.png")
    check("at 390 the panel opens and nothing scrolls sideways", pg.locator("#vFilter").is_visible() and pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))

    # ---- 1.3d: a heading for every station, labelled scroll boxes, sidebar labels that are not headings
    pg.set_viewport_size({"width": 1440, "height": 900})
    check("the sidebar's group labels are not headings", pg.locator("#sideNav h2").count() == 0 and pg.locator("#sideNav .nhead").count() == 4)
    ids = ["requests", "messages", "classes", "attendance", "venues", "curriculums", "instructors", "people", "students", "organizations", "places", "discovery", "access", "activity", "performance"]
    bad = []
    for sid in ids:
        pg.click('#sideNav a[data-nav="%s"]' % sid); pg.wait_for_timeout(350)
        vid = "list" if sid == "requests" else sid; view = pg.locator("#%sView" % vid)
        n_sr = view.locator(":scope > .stnh").count()
        n_visible_h2 = pg.evaluate("Array.from(document.querySelectorAll('#%sView h2')).filter(h => h.offsetParent !== null || h.classList.contains('stnh')).length" % vid)
        if sid in ("requests", "messages", "access", "activity", "performance"):
            if n_sr != 0 or n_visible_h2 < 1: bad.append((sid, "self-titled", n_sr, n_visible_h2))
        elif n_sr != 1: bad.append((sid, "needs one", n_sr))
    check("every station has exactly one title heading (the five that draw their own keep theirs)", not bad, bad)
    check("the heading carries the station's name", pg.evaluate("document.querySelector('#venuesView > .stnh').textContent") == "Venues" and pg.evaluate("document.getElementById('reqTitle').textContent") == "Registration requests")
    check("the three dialog bodies and the manual are keyboard-reachable, named regions", all(pg.evaluate("(function(){var e=document.getElementById('%s'); return e.getAttribute('tabindex')==='0' && e.getAttribute('role')==='region' && (e.getAttribute('aria-labelledby')||e.getAttribute('aria-label'))})()" % i) for i in ("atBody", "jrBody", "wfBody", "manualScroll")))

    # ---- 1.3d: capability markers (data-needs) for four kinds of sign-in
    PROBE = """(function(){ ['pbtnA','pbtnB'].forEach(function(id){ var o=document.getElementById(id); if(o) o.remove(); });
      var a=document.createElement('button'); a.id='pbtnA'; a.textContent='Probe A'; a.setAttribute('data-needs','edit_venues'); document.body.appendChild(a);
      var b=document.createElement('button'); b.id='pbtnB'; b.textContent='Probe B'; b.setAttribute('data-needs','edit_people invite_people'); document.body.appendChild(b); })()"""
    STATE = "(function(){ var a=document.getElementById('pbtnA'), b=document.getElementById('pbtnB'); return { a: [a.hidden, a.disabled], b: [b.hidden, b.disabled], bt: b.title }; })()"
    st = {}
    pg.evaluate(PROBE); pg.wait_for_timeout(200); st["super"] = pg.evaluate(STATE)
    check("a super admin sees and can use a marked control", st["super"]["a"] == [False, False] and st["super"]["b"] == [False, False], st["super"])
    b.close() if False else None
    for label, tok in (("head", T_HEAD), ("spend", T_SPEND), ("inspector", T_INSP)):
        q, qe = new_page(b, w=1440); go(q, 1440, tok)
        q.evaluate(PROBE); q.wait_for_timeout(250); st[label] = q.evaluate(STATE)
        if label == "inspector": st["itext"] = q.inner_text("#viewOnly") if q.locator("#viewOnly").is_visible() else ""
        q.context.close()
    check("a region head with edit_venues sees the venue control, and not the people control it has no right to", st["head"]["a"] == [False, False] and st["head"]["b"] == [True, False], st["head"])
    check("a role with neither right sees neither control (hidden, not greyed)", st["spend"]["a"][0] is True and st["spend"]["b"][0] is True, st["spend"])
    check("a view-only inspector sees both, switched off, with the reason", st["inspector"]["a"] == [False, True] and st["inspector"]["b"] == [False, True] and "View only" in st["inspector"]["bt"], st["inspector"])
    check("the page made no script errors", not errs, errs)
    b.close()

if fails:
    print("\nFAILED:", len(fails)); sys.exit(1)
print("\nOK: all Console shared-parts browser checks pass")

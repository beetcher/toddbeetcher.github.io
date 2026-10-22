#!/usr/bin/env python3
"""Browser test (P-78): the Global Inspector in the real Console page. A fake Firebase stands in for Google, the real doors answer (handle_admin,
handle_console, handle_discovery with a fake engine) over an in-memory store. Headless Chromium.
Checks: the View only band, every station open (Activity, Access and Discovery too), names show and private contact reads (hidden) on screen,
the buttons that would change something are switched off, a write the page is made to send never leaves the page, the SAME write sent
straight at the server is refused, a Discovery plan over 25 cents is refused, a super admin sees none of it, and Lock clears the mode.
Screenshots go to /tmp/claude-0/shots/. Run from enjoy_router/:  python3 run_inspector_browser_test.py"""
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

with sync_playwright() as p:
    b = launch(p)
    pg, errs = new_page(b)
    pg.goto(PAGE); pg.wait_for_selector("#googleBox:not([hidden])")
    seen.clear(); sign_in(pg, T_INSP); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(600)

    check("the name and role show", "Ivy Inspector" in pg.locator("#who").inner_text() and "global inspector" in pg.locator("#who").inner_text(), pg.locator("#who").inner_text())
    check("the View only band shows, in plain words", pg.locator("#viewOnly").is_visible() and "View only" in pg.locator("#viewOnly").inner_text() and "change nothing" in pg.locator("#viewOnly").inner_text())
    check("every station is open, Access, Activity and Discovery included", len(tiles(pg)) == 15 and any("Access" in t for t in tiles(pg)) and any("Activity" in t for t in tiles(pg)) and any("Discovery" in t for t in tiles(pg)), tiles(pg))
    check("the home page made no refused calls", not [s for s in seen if s[2] in (401, 403)], [s for s in seen if s[2] in (401, 403)])
    pg.screenshot(path=str(SHOTS / "inspector_home.png"))

    # ---------- people: names show, contact is hidden
    goto(pg, "people")
    txt = pg.locator("#peopleView").inner_text()
    check("People: the name shows", "Ann Student" in txt, txt[:300])
    pg.locator("#peopleView li").first.click(); pg.wait_for_timeout(500)
    txt = pg.locator("#peopleView").inner_text()
    check("People: the details show names and read (hidden) for contact", "(hidden)" in txt and not any(s in txt for s in SECRETS), txt[:600])
    pg.screenshot(path=str(SHOTS / "inspector_people.png"))
    check("People: Change history stays usable (looking is allowed)", pg.locator("#peopleView button", has_text="Change history").first.is_enabled())
    check("People: Add person, Edit, Merge and Delete are switched off", disabled_edit_buttons(pg) >= 3 and not enabled_write_buttons(pg), (disabled_edit_buttons(pg), enabled_write_buttons(pg)))

    # ---------- venues: public contact shows
    goto(pg, "venues")
    pg.locator("#venuesView button", has_text="Details").first.click(); pg.wait_for_timeout(500)
    txt = pg.locator("#venuesView").inner_text()
    check("Venues: the venue's own ZIP, email and phone show", "Boulder Hall" in txt and "hall@venue.example" in txt and "303-555-0100" in txt and "80301" in txt, txt[:500])
    check("Venues: the edit buttons are switched off and no switch can be flipped", not enabled_write_buttons(pg) and pg.locator("#venuesView .stoggle:not([disabled])").count() == 0, enabled_write_buttons(pg))
    pg.screenshot(path=str(SHOTS / "inspector_venues.png"))

    # ---------- requests (the records door)
    goto(pg, "requests")
    txt = pg.locator("#listView").inner_text()
    check("Requests: the name shows and no private value does", "Mel" in txt and not any(s in txt for s in SECRETS), txt[:400])
    pg.locator("#listView li, #listView .card").first.click(); pg.wait_for_timeout(500)
    txt = pg.locator("#listView").inner_text()
    check("Requests: opened, contact reads (hidden), notes are gone", "(hidden)" in txt and not any(s in txt for s in SECRETS), txt[:600])
    check("Requests: Put in a class and Delete are switched off", not enabled_write_buttons(pg), enabled_write_buttons(pg))
    pg.screenshot(path=str(SHOTS / "inspector_requests.png"))

    # ---------- Access: staff emails in full, nothing to press
    goto(pg, "access", 1400)
    txt = pg.locator("#accessView").inner_text()
    check("Access: staff emails show in full", "inspector@example.com" in txt and "todd@example.com" in txt, txt[:500])
    check("Access: Invite, Edit, Switch and Resend are switched off", not enabled_write_buttons(pg), enabled_write_buttons(pg))
    check("Access: the Inspector's own row says what the role is, not that they see nothing", "Inspector: sees everything, changes nothing" in txt and "sees nothing in any region" not in txt, txt[:700])
    check("Access: it is the full view (not the limited one a person who may invite sees)", pg.locator("#accessView h2", has_text="Roles").count() == 1 and "looked after by a super admin" not in txt, txt[:300])
    pg.screenshot(path=str(SHOTS / "inspector_access.png"))

    # ---------- messages, activity, discovery open
    goto(pg, "messages"); check("Messages opens", pg.locator("#messagesView").is_visible())
    goto(pg, "activity"); check("Activity opens (it was super admin only)", pg.locator("#activityView").is_visible() and "could not" not in pg.locator("#activityView").inner_text().lower(), pg.locator("#activityView").inner_text()[:200])
    goto(pg, "discovery", 1200); check("Discovery opens", pg.locator("#discoveryView").is_visible())
    pg.screenshot(path=str(SHOTS / "inspector_discovery.png"))

    # ---------- a write forced from inside the page never leaves the page; the same write sent straight at the server is refused
    seen.clear()
    res = pg.evaluate("ConsoleKit.admin('update', {id: '%s', changes: {name: 'Hacked'}}, 'venues').then(r => ({status: r.status, code: r.body.error && r.body.error.code}))" % VID)
    check("a write made from the page is stopped in the page, in plain words", res["status"] == 403 and res["code"] == "view_only" and not [s for s in seen if s[1] == "update"], (res, seen))
    tok = pg.evaluate("ConsoleKit.key()")
    res = pg.evaluate("""(a) => fetch('https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_admin', {method: 'POST', headers: {Authorization: 'Bearer ' + a.tok, 'Content-Type': 'application/json'},
        body: JSON.stringify({collection: 'venues', op: 'update', args: {id: a.vid, changes: {name: 'Hacked'}}})}).then(r => r.status)""", {"tok": tok, "vid": VID})
    check("the same write sent straight to the server is refused (403)", res == 403, res)
    check("...and the venue is unchanged", store.get("venues", VID)["name"] == "Boulder Hall")
    res = pg.evaluate("""(a) => fetch('https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_admin', {method: 'POST', headers: {Authorization: 'Bearer ' + a.tok, 'Content-Type': 'application/json'},
        body: JSON.stringify({collection: 'access_persons', op: 'send_invite', args: {id: a.id}})}).then(r => r.status)""", {"tok": tok, "id": PE.find_live_by_email(store, "todd@example.com")["id"]})
    check("an invitation email cannot be sent by an inspector, even by hand (403)", res == 403, res)

    # ---------- Discovery cap
    area_ids = [REGION]
    res = pg.evaluate("""(a) => fetch('https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_discovery', {method: 'POST', headers: {Authorization: 'Bearer ' + a.tok, 'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'plan', args: {finder_key: 'venue', model_id: 'm', area_ids: a.areas, type_keys: ['t'], max_results: 3, spend_cap_cents: a.cap}})}).then(r => r.json().then(j => ({s: r.status, c: j.error && j.error.code})))""", {"tok": tok, "areas": area_ids, "cap": 26})
    check("a Discovery plan over 25 cents is refused with its own code", res["s"] == 400 and res["c"] == "inspector_cap" and ("plan", 26) not in eng.calls, res)
    res = pg.evaluate("""(a) => fetch('https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_discovery', {method: 'POST', headers: {Authorization: 'Bearer ' + a.tok, 'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'plan', args: {finder_key: 'venue', model_id: 'm', area_ids: a.areas, type_keys: ['t'], max_results: 3, spend_cap_cents: a.cap}})}).then(r => r.status)""", {"tok": tok, "areas": area_ids, "cap": 10})
    check("a plan at 10 cents goes through", res == 200 and ("plan", 10) in eng.calls, (res, eng.calls))
    check("the page made no script errors", not errs, errs)

    # ---------- Lock clears the mode; a super admin sees none of it
    pg.evaluate("location.hash = '#/home'"); pg.wait_for_timeout(300)
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("after Lock the band is gone and the page is no longer in view-only mode", not pg.locator("#viewOnly").is_visible() and not pg.evaluate("document.body.classList.contains('viewonly')"))
    sign_in(pg, T_TODD); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(500)
    check("a super admin has no band and no switched-off buttons", not pg.locator("#viewOnly").is_visible() and not pg.evaluate("document.body.classList.contains('viewonly')"))
    goto(pg, "venues"); pg.locator("#venuesView button", has_text="Details").first.click(); pg.wait_for_timeout(400)
    check("...and can still edit (the Edit button works)", pg.locator("#venuesView button", has_text="Edit").first.is_enabled())
    txt = pg.locator("#venuesView").inner_text(); goto(pg, "people"); pg.locator("#peopleView li").first.click(); pg.wait_for_timeout(500)
    check("...and sees the real contact details", "ann.private@home.example" in pg.locator("#peopleView").inner_text(), pg.locator("#peopleView").inner_text()[:300])
    # the edit form for a person with the view-only role says territory is not needed (no "No territory yet", no Add territory form), and follows the role picker
    goto(pg, "access"); pg.locator("#accessView .acrow", has_text="Ivy Inspector").first.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox"); pg.wait_for_timeout(200)
    box = pg.locator("#agBox").inner_text()
    check("Edit form, view-only role: says territory is not needed", "Territory: not needed. A view-only role sees everywhere and changes nothing." in box, box)
    check("Edit form, view-only role: no 'No territory yet' and no Add territory form", "No territory yet" not in box and "Add territory" not in box and pg.locator("#agKind").count() == 0, box)
    pg.select_option("#apRole", value=sup_role["id"]); pg.wait_for_timeout(200)
    check("...switching the picker to super admin shows the super admin text", "A super admin works everywhere" in pg.locator("#agBox").inner_text())
    pg.select_option("#apRole", value=insp_role["id"]); pg.wait_for_timeout(200)
    check("...and back to the view-only role shows the view-only text again", "Territory: not needed. A view-only role" in pg.locator("#agBox").inner_text())
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")

    # ---------- phone width
    pg2, e2 = new_page(b, w=390)
    pg2.goto(PAGE); pg2.wait_for_selector("#googleBox:not([hidden])"); sign_in(pg2, T_INSP); pg2.wait_for_selector("#homeView:not([hidden])"); pg2.wait_for_timeout(500)
    check("phone width: the band fits and nothing scrolls sideways", pg2.locator("#viewOnly").is_visible() and pg2.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg2.evaluate("document.documentElement.scrollWidth"))
    pg2.screenshot(path=str(SHOTS / "inspector_phone.png"))
    check("phone width: no script errors", not e2, e2)
    b.close()

print("\nOK: all Inspector browser checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

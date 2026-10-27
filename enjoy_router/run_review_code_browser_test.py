#!/usr/bin/env python3
"""Browser test: the Access > Sign-in box "Review access code" (set, replace, refuse) and signing in with the code (view only).
Real doors with an in-memory store, a fake Firebase for the Google path, headless Chromium.
Run from enjoy_router/:  python3 run_review_code_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud import access_persons_crud as PE, access_roles_crud as RO, console_settings_crud as CS
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
A = "user:admin"
REGION_ID = "a0000000-0000-4000-8000-000000000002"; STATE_ID = "a0000000-0000-4000-8000-000000000001"
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
H = {"store": None, "fail_settings": False, "setting_writes": 0}
def role(st, key, caps=None, sup=False):
    r = RO.create(st, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps})}, A); assert r.ok, r.problems; return r.data
def person(st, email, r, name, grants=None):
    p = PE.create(st, {"email": email, "display_name": name, "role_id": r["id"], **({"grants": grants} if grants else {})}, A); assert p.ok, p.problems
    tok = f"tok.{email.split('@')[0]}.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    V.tokens[tok] = {"uid": "uid-" + email, "email": email, "email_verified": True, "provider": "google.com", "name": name}; return tok
def new_store(minutes=None):
    st = MemoryDocStore("")
    st.create("discovery_areas", STATE_ID, {"id": STATE_ID, "kind": "state", "state_code": "CO", "name": "Colorado", "is_active": True})
    st.create("discovery_areas", REGION_ID, {"id": REGION_ID, "kind": "region", "state_code": "CO", "name": "Boulder", "zip_codes": ["80301"], "is_active": True})
    import seed_access
    sup = role(st, "super_admin", sup=True); lead = role(st, "lead_role", ["view_console", "view_spend"])
    role(st, "global_inspector", {r["key"]: r for r in seed_access.ROLES}["global_inspector"]["capabilities"])   # seeded in production (P-78)
    toks = {"todd": person(st, "todd@example.com", sup, "Todd Beetcher"),
            "lead": person(st, "lead@example.com", lead, "Lena Lead", [{"kind": "regions", "state_code": "CO", "region_ids": [REGION_ID], "capabilities": ["manage_requests", "invite_people"]}])}
    if minutes is not None:
        r = CS.create(st, {"session_timeout_minutes": minutes}, A); assert r.ok, r.problems
    return st, toks

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
limiter = make_failure_limiter()
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    body = json.loads(q.post_data or "{}")
    if body.get("collection") == "console_settings" and body.get("op") in ("create", "update"): H["setting_writes"] += 1
    if H["fail_settings"] and body.get("collection") == "console_settings":
        route.fulfill(status=500, headers=CORS, body=json.dumps({"ok": False, "error": {"code": "server_error"}})); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", H["store"], limiter, datetime.now(timezone.utc), verifier=V)
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def records_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}}))

FAKE_FIREBASE = """
(function () {
  try { Object.defineProperty(window, "CONSOLE_FIREBASE", { value: { apiKey: "test-key", projectId: "p" }, writable: false }); } catch (e) {}
  var listeners = [], cur = null;
  function user(t) { return { getIdToken: function () { return Promise.resolve(t); } }; }
  try { var kept = sessionStorage.getItem("fakeTok"); if (kept) cur = user(kept); } catch (e) {}
  var auth = {
    get currentUser() { return cur; },
    onIdTokenChanged: function (cb) { listeners.push(cb); setTimeout(function () { cb(cur); }, 0); },
    signInWithPopup: function () { return new Promise(function (ok, no) { var t = window.__NEXT; if (!t) { no({ code: "auth/popup-closed-by-user" }); return; }
        cur = user(t); try { sessionStorage.setItem("fakeTok", t); } catch (e) {} listeners.forEach(function (cb) { cb(cur); }); ok({ user: cur }); }); },
    signOut: function () { cur = null; window.__signedOut = (window.__signedOut || 0) + 1; try { sessionStorage.removeItem("fakeTok"); } catch (e) {} listeners.forEach(function (cb) { cb(null); }); return Promise.resolve(); }
  };
  var fb = { apps: [], initializeApp: function () { fb.apps.push(1); }, auth: function () { return auth; } };
  fb.auth.GoogleAuthProvider = function () { this.setCustomParameters = function () {}; };
  window.firebase = fb;
})();
"""
def launch(p):
    exe = "/opt/pw-browsers/chromium"
    return p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
ERRS = []
def page(b, fake_clock=True, google=False, init="", w=900):
    pg = b.new_context(viewport={"width": w, "height": 900}).new_page()
    pg.on("pageerror", lambda e: ERRS.append(str(e)))
    if init: pg.add_init_script(init)
    if google: pg.add_init_script(FAKE_FIREBASE)
    if fake_clock: pg.clock.install()
    pg.route("**/enjoy_admin", admin_route); pg.route("**/enjoy_console_records*", records_route)
    pg.route("**/enjoy_discovery", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    return pg
def key_in(pg):
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(150)
def advance(pg, seconds):
    pg.clock.run_for(int(seconds * 1000)); pg.wait_for_timeout(120)
def signed_in(pg): return pg.locator("#homeView").is_visible() and not pg.locator("#lockView").is_visible()
def locked(pg): return pg.locator("#lockView").is_visible()
def warn_visible(pg): return pg.locator("#idleWarn").is_visible()
def store_dump(pg): return pg.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage).filter(e => e[0] !== 'fakeTok')])")


CODE, CODE2 = "council review 2026", "second funny phrase"
def read_status(pg): return pg.inner_text("#acReviewStatus")
with sync_playwright() as p:
    b = launch(p)
    # ---------- R1: the super admin sets a code, then replaces it
    H["store"], toks = new_store()
    pg = page(b, fake_clock=False); key_in(pg); pg.goto(PAGE + "#/access"); pg.wait_for_selector("#acReview"); pg.wait_for_timeout(200)
    check("R1 the super admin sees the Review access code box, with no code active", "No code is active." in read_status(pg) and "view only" in pg.inner_text("#acReview").lower())
    pg.fill("#acReviewCode", "abc"); pg.click("#acReviewSave"); pg.wait_for_function("document.querySelector('#acReviewMsg').innerText.length > 0")
    check("R1 a short code is refused in plain words, nothing is set", "at least 8" in pg.inner_text("#acReviewMsg") and "No code is active." in read_status(pg), pg.inner_text("#acReviewMsg"))
    pg.fill("#acReviewCode", CODE); pg.click("#acReviewSave"); pg.wait_for_selector("#acReviewShown")
    msg = pg.inner_text("#acReviewMsg")
    check("R1 setting a code says when it ends and that it cannot be shown again", "Code set." in msg and __import__("re").search(r"(AM|PM) [A-Z]{2,5}\b", msg) and "cannot be shown again" in msg, msg)
    check("R1 the code is on its own line after 'Give them exactly this:'", pg.inner_text("#acReviewShown") == CODE and "Give them exactly this:" in pg.inner_text(".acgive"), pg.inner_text(".acgive"))
    c_msg, c_code = pg.evaluate("getComputedStyle(document.querySelector('#acReviewMsg')).color"), pg.evaluate("getComputedStyle(document.querySelector('#acReviewShown')).color")
    fam = pg.evaluate("getComputedStyle(document.querySelector('#acReviewShown')).fontFamily").lower()
    check("R1 the code is in a different colour from the message, bold and monospace", c_msg != c_code and ("mono" in fam or "menlo" in fam or "consolas" in fam), (c_msg, c_code, fam))
    check("R1 the code is not inside the message line itself", CODE not in msg)
    check("R1 the status line now says a code is active until a time", "A code is active until" in read_status(pg) and __import__("re").search(r"(AM|PM) [A-Z]{2,5}\b", read_status(pg)), read_status(pg))
    check("R1 the page itself does not hold the code once the box is redrawn (the input is empty)", pg.input_value("#acReviewCode") == "")
    pg.fill("#acReviewCode", CODE2); pg.click("#acReviewSave"); pg.wait_for_function("document.querySelector('#acReviewShown') && document.querySelector('#acReviewShown').innerText === '%s'" % CODE2)
    check("R1 a second code replaces the first (the line now shows the new one, the old one is gone from the box)", CODE not in pg.inner_text("#acReview"), pg.inner_text("#acReview"))
    pg.fill("#acReviewCode", "abc"); pg.click("#acReviewSave"); pg.wait_for_function("document.querySelector('#acReviewMsg').innerText.includes('at least 8')")
    check("R1 a refused code takes the shown code away", pg.locator("#acReviewShown").count() == 0)
    pg.fill("#acReviewCode", CODE2); pg.click("#acReviewSave"); pg.wait_for_selector("#acReviewShown")
    # ---------- Z1: places with no time zone (super admin): check, fill the Colorado ones, list the rest
    import uuid as _uuid
    def _loc(name, region, zip_):   # saved straight into the store with no zone, the way older places were
        i = str(_uuid.uuid4())
        H["store"].create("locations", i, {"id": i, "name": name, "kind": "site", "status": "active", "schema_version": 1, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z", "addresses": [{"usage": "civic", "street_number": "1", "street": "Main St", "locality": "Town", "region": region, "postal_code": zip_, "country": "US"}]}); return i
    zco, zaz = _loc("Boulder Library", "CO", "80301"), _loc("Phoenix Hall", "AZ", "85001")
    zno = _loc("Nowhere Hall", "ZZ", "00000")
    pg.goto(PAGE + "#/access"); pg.wait_for_selector("#acZones"); pg.wait_for_timeout(200)
    check("Z1 the super admin sees the Places with no time zone box", "Places with no time zone" in pg.inner_text("#acZones") and pg.locator("#acZoneFill").count() == 0)
    pg.click("#acZoneCheck"); pg.wait_for_selector("#acZoneList")
    check("Z1 checking says how many, and lists the places a person must fix", "3 places have no time zone: 2 can be filled from their ZIP" in pg.inner_text("#acZones") and "Nowhere Hall (ZZ)" in pg.inner_text("#acZoneList") and "Boulder" not in pg.inner_text("#acZoneList") and "Phoenix" not in pg.inner_text("#acZoneList"), pg.inner_text("#acZones"))
    check("Z1 checking alone changes nothing", not H["store"].get("locations", zco).get("time_zone"))
    pg.click("#acZoneFill"); pg.wait_for_function("document.querySelector('#acZones').innerText.indexOf('filled just now') >= 0")
    check("Z1 Fill gives Colorado Mountain time and Arizona its own zone, and never guesses for a place the ZIP table does not know", H["store"].get("locations", zco).get("time_zone") == "America/Denver" and H["store"].get("locations", zaz).get("time_zone") == "America/Phoenix" and not H["store"].get("locations", zno).get("time_zone"))
    check("R1 the stored record holds no plain code", CODE not in json.dumps(H["store"].query("review_codes", [], limit=5)) and CODE2 not in json.dumps(H["store"].query("review_codes", [], limit=5)) and len(H["store"].query("review_codes", [], limit=5)) == 1)
    check("R1 the box is readable on a desktop: input at least 44 px high", pg.locator("#acReviewCode").bounding_box()["height"] >= 44 and pg.locator("#acReviewSave").bounding_box()["height"] >= 44)
    pg.screenshot(path="/tmp/review_code_box.png", full_page=True)
    pg.close()

    # ---------- R2: a reviewer signs in with the new code
    pg = page(b, fake_clock=False); pg.goto(PAGE)
    pg.fill("#keyInput", CODE)
    check("R2 the Key box hides what you type to begin with, with a Show button beside it", pg.get_attribute("#keyInput", "type") == "password" and pg.inner_text("#keyShow") == "Show")
    pg.click("#keyShow")
    check("R2 Show reveals the typed key (the button now says Hide)", pg.get_attribute("#keyInput", "type") == "text" and pg.inner_text("#keyShow") == "Hide" and pg.input_value("#keyInput") == CODE)
    pg.click("#keyShow")
    check("R2 Hide covers it again", pg.get_attribute("#keyInput", "type") == "password" and pg.inner_text("#keyShow") == "Show")
    bx, ub = pg.locator("#keyShow").bounding_box(), pg.locator("#unlockBtn").bounding_box()
    check("R2 the Show button is at least 44 px tall and does not overlap Unlock", bx["height"] >= 44 and (bx["x"] + bx["width"] <= ub["x"] + 1 or ub["x"] + ub["width"] <= bx["x"] + 1), (bx, ub))
    pg.screenshot(path="/tmp/review_code_lock.png")
    pg.click("#unlockBtn"); pg.wait_for_timeout(500)
    check("R2 the OLD code is refused on the sign-in screen", "did not work" in pg.inner_text("#lockMsg") and not pg.locator("#homeView").is_visible(), pg.inner_text("#lockMsg"))
    pg.fill("#keyInput", CODE2); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(300)
    check("R2 the NEW code signs in and the View only band shows", pg.locator("#viewOnly").is_visible() and "View only." in pg.inner_text("#viewOnly"))
    check("R2 the band does not promise Discovery runs to a review code", "Discovery run" not in pg.inner_text("#viewOnly") and "ends on its own" in pg.inner_text("#viewOnly"), pg.inner_text("#viewOnly"))
    check("R2 the page names the reviewer 'Review access' with the Inspector role, not 'Admin key'", "Review access" in pg.inner_text("#who") and "global inspector" in pg.inner_text("#who").lower(), pg.inner_text("#who"))
    pg.goto(PAGE + "#/access"); pg.wait_for_timeout(600)
    check("R2 the reviewer does NOT see the Review access code box (nor can read the status)", pg.locator("#acReview").count() == 0 and pg.locator("#acReviewCode").count() == 0)
    pg.screenshot(path="/tmp/review_code_reviewer.png")
    pg.close()

    # ---------- R3: a lead (Google) does not see the box either
    H["store"], toks = new_store()
    pg = page(b, fake_clock=False, google=True); pg.goto(PAGE); pg.wait_for_selector("#googleBtn")
    pg.evaluate("t => { window.__NEXT = t; }", toks["lead"]); pg.click("#googleBtn"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(150)
    pg.goto(PAGE + "#/access"); pg.wait_for_selector("#accessView:not([hidden])"); pg.wait_for_timeout(400)
    check("R3 a lead does not see the Review access code box", pg.locator("#acReview").count() == 0)
    pg.close()

    # ---------- R4: phone width
    H["store"], toks = new_store()
    pg = page(b, fake_clock=False, w=390); key_in(pg); pg.goto(PAGE + "#/access"); pg.wait_for_selector("#acReview"); pg.wait_for_timeout(200)
    bx, bs = pg.locator("#acReviewCode").bounding_box(), pg.locator("#acReviewSave").bounding_box()
    check("R4 the box and button fit a phone screen", bx["x"] >= 0 and bx["x"] + bx["width"] <= 391 and bs["x"] + bs["width"] <= 391, (bx, bs))
    pg.screenshot(path="/tmp/review_code_phone.png", full_page=True)
    pg.close()
    check("R5 no script errors in any page", not ERRS, ERRS)
    b.close()
print("\nOK: all review code browser checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Browser test: the Console's automatic sign-out after inactivity (console_setting.session_timeout_minutes) and the Access > Sign-in box.
Real doors with an in-memory store, a fake Firebase for the Google paths, headless Chromium with a FAKE CLOCK so minutes pass at once.
Checks: default 10 minutes; the warning in the last 60 seconds; activity and "Stay signed in" reset it; the super admin's number is used;
a Discovery run in progress holds the sign-out; an unreadable setting falls back to the last known number, then 10; Lock clears the saved
clock; a remembered key and a restored Google session that sat idle too long are dropped at load, a deliberate sign-in never is; Google is
signed out too; the Sign-in box saves, refuses bad numbers, applies at once, and is hidden from an inviting lead; phone width; no script errors.
Run from enjoy_router/:  python3 run_console_timeout_browser_test.py"""
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
    sup = role(st, "super_admin", sup=True); lead = role(st, "lead_role", ["view_console", "view_spend"])
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

with sync_playwright() as p:
    b = launch(p)

    # ---------- T1: no setting saved: 10 minutes, warning in the last minute, then locked
    H["store"], toks = new_store()
    pg = page(b); key_in(pg)
    advance(pg, 8 * 60 + 50)
    check("T1 nothing set: still signed in at 8:50, no warning", signed_in(pg) and not warn_visible(pg))
    advance(pg, 20)
    check("T1 the warning shows in the last minute (9:10)", warn_visible(pg) and "second" in pg.inner_text("#idleWarn"), pg.inner_text("#idleWarn"))
    pg.screenshot(path="/tmp/timeout_warning.png")
    pg.click("#idleStay"); pg.wait_for_timeout(100)
    check("T1 Stay signed in clears the warning", not warn_visible(pg) and signed_in(pg))
    advance(pg, 8 * 60 + 30)
    check("T1 ...and the clock started over (8:30 later, still in, no warning)", signed_in(pg) and not warn_visible(pg))
    advance(pg, 95)
    check("T1 after 10 minutes of nothing the Console is locked", locked(pg) and not signed_in(pg))
    msg = pg.inner_text("#lockMsg")
    check("T1 it says why, in plain words, with the number", "10 minutes without activity" in msg and "Sign in again" in msg, msg)
    check("T1 the key and the saved clock are gone from the browser", "console_key_launch" not in store_dump(pg) and "console_last_active" not in store_dump(pg), store_dump(pg))
    check("T1 the warning is gone too", not warn_visible(pg))
    pg.screenshot(path="/tmp/timeout_locked.png")
    pg.close()

    # ---------- T2: a super admin's number is used
    H["store"], toks = new_store(minutes=2)
    pg = page(b); key_in(pg)
    advance(pg, 50)
    check("T2 set to 2 minutes: fine at 0:50", signed_in(pg) and not warn_visible(pg))
    advance(pg, 20)
    check("T2 ...warning from 1:00", warn_visible(pg))
    advance(pg, 60)
    check("T2 ...locked after 2 minutes, saying 2", locked(pg) and "after 2 minutes" in pg.inner_text("#lockMsg"), pg.inner_text("#lockMsg"))
    pg.close()
    H["store"], toks = new_store(minutes=1)
    pg = page(b); key_in(pg); advance(pg, 61)
    check("T2 one minute is allowed and says '1 minute' (not minutes)", locked(pg) and "after 1 minute without" in pg.inner_text("#lockMsg"), pg.inner_text("#lockMsg"))
    pg.close()

    # ---------- T3: activity resets the clock
    H["store"], toks = new_store()
    pg = page(b); key_in(pg)
    advance(pg, 9 * 60 + 30)
    check("T3 (set up) the warning is showing at 9:30", warn_visible(pg))
    pg.keyboard.press("Shift"); pg.wait_for_timeout(100)
    check("T3 a key press clears the warning at once", not warn_visible(pg))
    advance(pg, 9 * 60)
    check("T3 ...and 9 minutes later the person is still in", signed_in(pg))
    pg.mouse.click(300, 300); advance(pg, 9 * 60)
    check("T3 a click resets it too", signed_in(pg))
    pg.mouse.wheel(0, 200); advance(pg, 9 * 60)
    check("T3 a scroll resets it too", signed_in(pg))
    advance(pg, 70)
    check("T3 and then 10 quiet minutes lock it", locked(pg))
    pg.close()

    # ---------- T4: a Discovery run in progress holds the sign-out
    H["store"], toks = new_store()
    pg = page(b); key_in(pg)
    pg.evaluate("window.DiscoveryStation.busy = function () { return true; }")
    advance(pg, 15 * 60)
    check("T4 a Discovery run in progress: 15 quiet minutes and still signed in", signed_in(pg) and not warn_visible(pg))
    pg.evaluate("window.DiscoveryStation.busy = function () { return false; }")
    advance(pg, 9 * 60)
    check("T4 ...the run ends, the clock counts from then (9 minutes: still in)", signed_in(pg))
    advance(pg, 70)
    check("T4 ...and 10 minutes after the run ended it locks", locked(pg))
    pg.close()

    # ---------- T5: the setting cannot be read
    H["store"], toks = new_store(minutes=30); H["fail_settings"] = True
    pg = page(b); key_in(pg); advance(pg, 9 * 60 + 30)
    check("T5 setting unreadable and never known: 10 minutes (the warning shows at 9:30)", warn_visible(pg))
    advance(pg, 40)
    check("T5 ...and it locks at 10 (fails closed, not open)", locked(pg))
    pg.close()
    pg = page(b, init="try { localStorage.setItem('console_timeout_minutes', '3'); } catch (e) {}"); key_in(pg); advance(pg, 181)
    check("T5 setting unreadable but a last known number of 3 exists: it uses 3", locked(pg) and "after 3 minutes" in pg.inner_text("#lockMsg"), pg.inner_text("#lockMsg"))
    pg.close()
    pg = page(b, init="try { localStorage.setItem('console_timeout_minutes', '9999'); } catch (e) {}"); key_in(pg); advance(pg, 10 * 60 + 5)
    check("T5 an out-of-range last known number (9999) is not trusted: it uses 10", locked(pg) and "after 10 minutes" in pg.inner_text("#lockMsg"), pg.inner_text("#lockMsg"))
    pg.close(); H["fail_settings"] = False
    H["store"], toks = new_store(minutes=30)
    pg = page(b, init="try { localStorage.setItem('console_timeout_minutes', '3'); } catch (e) {}"); key_in(pg); advance(pg, 181)
    check("T5 a readable setting (30) wins over the stored last known number (3)", signed_in(pg))
    pg.close()

    # ---------- T6: a saved session that sat idle is dropped at load (real clock; the saved time is set in the page before it starts)
    H["store"], toks = new_store()
    def saved(minutes_ago):
        return ("try { localStorage.setItem('console_key_launch', %s); localStorage.setItem('console_last_active', String(Date.now() - %d)); } catch (e) {}"
                % (json.dumps(KEY), minutes_ago * 60000))
    pg = page(b, fake_clock=False, init=saved(11)); pg.goto(PAGE); pg.wait_for_selector("#lockView:not([hidden])"); pg.wait_for_timeout(300)
    check("T6 a remembered key idle for 11 minutes is NOT used: the lock screen shows", locked(pg) and not pg.locator("#homeView").is_visible())
    check("T6 ...with the reason", "after 10 minutes without activity" in pg.inner_text("#lockMsg"), pg.inner_text("#lockMsg"))
    check("T6 ...and the key is gone from the browser", "console_key_launch" not in store_dump(pg), store_dump(pg))
    pg.close()
    pg = page(b, fake_clock=False, init=saved(5)); pg.goto(PAGE); pg.wait_for_selector("#homeView:not([hidden])")
    check("T6 a remembered key idle for 5 minutes signs in as before", signed_in(pg))
    pg.close()
    pg = page(b, fake_clock=False, init="try { localStorage.setItem('console_key_launch', %s); } catch (e) {}" % json.dumps(KEY)); pg.goto(PAGE); pg.wait_for_selector("#homeView:not([hidden])")
    check("T6 a remembered key from before this feature (no saved clock) signs in, and the clock starts", signed_in(pg) and "console_last_active" in store_dump(pg))
    pg.close()

    # ---------- T7: Google
    H["store"], toks = new_store()
    pg = page(b, google=True); pg.goto(PAGE); pg.wait_for_selector("#googleBtn")
    pg.evaluate("t => { window.__NEXT = t; }", toks["todd"]); pg.click("#googleBtn"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(150)
    check("T7 (set up) signed in with Google", signed_in(pg) and "Todd Beetcher" in pg.inner_text("#who"))
    advance(pg, 10 * 60 + 5)
    check("T7 Google: locked after 10 minutes", locked(pg) and "without activity" in pg.inner_text("#lockMsg"))
    check("T7 ...and signed out of Google as well", (pg.evaluate("window.__signedOut || 0") or 0) >= 1)
    pg.close()
    stale_g = "try { sessionStorage.setItem('fakeTok', %s); localStorage.setItem('console_last_active', String(Date.now() - 11 * 60000)); } catch (e) {}" % json.dumps(toks["todd"])
    pg = page(b, fake_clock=False, google=True, init=stale_g); pg.goto(PAGE); pg.wait_for_selector("#lockView:not([hidden])"); pg.wait_for_timeout(400)
    check("T7 a restored Google session idle for 11 minutes is dropped at load", locked(pg) and not pg.locator("#homeView").is_visible() and "without activity" in pg.inner_text("#lockMsg"), pg.inner_text("#lockMsg"))
    check("T7 ...and Google is signed out", (pg.evaluate("window.__signedOut || 0") or 0) >= 1)
    pg.evaluate("t => { window.__NEXT = t; }", toks["todd"]); pg.click("#googleBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("T7 a DELIBERATE sign-in after that is never dropped as stale", signed_in(pg))
    pg.close()
    only_stale = "try { localStorage.setItem('console_last_active', String(Date.now() - 11 * 60000)); } catch (e) {}"
    pg = page(b, fake_clock=False, google=True, init=only_stale); pg.goto(PAGE); pg.wait_for_selector("#googleBtn"); pg.wait_for_timeout(300)
    pg.evaluate("t => { window.__NEXT = t; }", toks["todd"]); pg.click("#googleBtn"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(300)
    check("T7 a deliberate Google sign-in on a page that loaded with an old saved clock stays signed in", signed_in(pg))
    pg.close()
    fresh_g = "try { sessionStorage.setItem('fakeTok', %s); localStorage.setItem('console_last_active', String(Date.now() - 4 * 60000)); } catch (e) {}" % json.dumps(toks["todd"])
    pg = page(b, fake_clock=False, google=True, init=fresh_g); pg.goto(PAGE); pg.wait_for_selector("#homeView:not([hidden])")
    check("T7 a restored Google session idle for 4 minutes carries on", signed_in(pg))
    pg.close()

    # ---------- T8: the Access > Sign-in box
    H["store"], toks = new_store()
    pg = page(b, fake_clock=False); key_in(pg); pg.goto(PAGE + "#/access"); pg.wait_for_selector("#acSignIn"); pg.wait_for_timeout(200)
    check("T8 the super admin sees the Sign-in box with 10 (nothing saved yet)", pg.input_value("#acMinutes") == "10" and "Not set yet" in pg.inner_text("#acSignIn"))
    pg.fill("#acMinutes", "5"); pg.click("#acMinutesSave"); pg.wait_for_function("document.querySelector('#acMinutesMsg').innerText.includes('Saved')")
    rec = CS.list(H["store"]).data["records"]
    check("T8 saving 5 creates the record", len(rec) == 1 and rec[0]["session_timeout_minutes"] == 5, rec)
    check("T8 the message says what happens next", "5 minutes" in pg.inner_text("#acMinutesMsg") and "reloads" in pg.inner_text("#acMinutesMsg"))
    check("T8 this window uses the new number at once", pg.evaluate("window.ConsoleKit.sessionMinutes()") == 5)
    pg.fill("#acMinutes", "7"); pg.click("#acMinutesSave"); pg.wait_for_function("document.querySelector('#acMinutesMsg').innerText.includes('7 minutes')")
    rec = CS.list(H["store"]).data["records"]
    check("T8 saving again changes the same record (no second one)", len(rec) == 1 and rec[0]["session_timeout_minutes"] == 7)
    writes_before = H["setting_writes"]
    for bad in ("0", "481", "1e2", "7.5", "", "-3"):
        pg.fill("#acMinutes", bad); pg.click("#acMinutesSave"); pg.wait_for_function("document.querySelector('#acMinutesMsg').innerText.includes('whole number')"); pg.wait_for_timeout(250)
    check("T8 0, 481, 1e2, a fraction, nothing and a negative are all refused with a plain message", CS.list(H["store"]).data["records"][0]["session_timeout_minutes"] == 7 and H["setting_writes"] == writes_before, (H["setting_writes"], writes_before))
    pg.screenshot(path="/tmp/timeout_access_box.png", full_page=True)
    pg.close()

    H["store"], toks = new_store()
    pg = page(b, fake_clock=False, google=True); pg.goto(PAGE); pg.wait_for_selector("#googleBtn")
    pg.evaluate("t => { window.__NEXT = t; }", toks["lead"]); pg.click("#googleBtn"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(150)
    pg.goto(PAGE + "#/access"); pg.wait_for_selector("#accessView:not([hidden])"); pg.wait_for_timeout(300)
    check("T8 a lead who may invite people does NOT see the Sign-in box", pg.locator("#acSignIn").count() == 0)
    pg.close()

    # ---------- T9: phone width
    H["store"], toks = new_store()
    pg = page(b, w=390); key_in(pg); advance(pg, 9 * 60 + 20)
    box = pg.locator("#idleWarn").bounding_box()
    check("T9 the warning fits a phone screen", box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390 + 1, box)
    check("T9 the Stay signed in button is big enough to tap (44 px)", pg.locator("#idleStay").bounding_box()["height"] >= 44)
    pg.screenshot(path="/tmp/timeout_phone.png")
    pg.close()
    check("T10 no script errors in any page", not ERRS, ERRS)
    b.close()
print("\nOK: all timeout browser checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

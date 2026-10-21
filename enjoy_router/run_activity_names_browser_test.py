#!/usr/bin/env python3
"""Browser test (P-46 follow-up): the Activity station shows WHO as a name. Real doors, in-memory store wrapped in the ActivityStore, headless
Chromium, signed in with the admin key. Changes are made as different actors (a named person, a person with no name, a person who is no longer
on file, the admin key) and the station must show: the person's name; the user id when no name can be found (never a role, never a vague label);
"Admin key" for the key; names inside "Deleted by"-style fields; the id on hover; the Person-or-source filter by name; the search by name; one
lookup per load (and none when nothing new); a failed lookup leaves ids showing and breaks nothing.
Run from enjoy_router/:  python3 run_activity_names_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud import venues_crud as VEN
from crud.activity_store import ActivityStore
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SHOTS = pathlib.Path(os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="activity_names_shots_")); SHOTS.mkdir(parents=True, exist_ok=True)
inner = MemoryDocStore(""); store = ActivityStore(inner); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
state = {"people_calls": 0, "people_fail": False, "people_abort": False, "key_only": False}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    body = json.loads(q.post_data or "{}")
    if body.get("collection") == "access_persons" and body.get("op") == "list":
        state["people_calls"] += 1
        if state["people_abort"]:
            route.abort(); return
        if state["people_fail"]:
            route.fulfill(status=500, headers=CORS, body=json.dumps({"ok": False, "error": "server"})); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    if state["key_only"] and body.get("collection") == "activity_events" and body.get("op") == "list" and not (body.get("args") or {}).get("filters"):
        r.body["data"]["records"] = [e for e in r.body["data"]["records"] if e.get("created_by") == "user:admin"]      # a log whose newest entries are all the key's
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

def new_id(n): return "00000000-0000-4000-8000-%012d" % n
PA, PB, PC = new_id(901), new_id(902), new_id(903)     # named person; person with no name on file; person no longer on file
NOW = "2026-10-21T12:00:00Z"
def person(pid, name):
    d = {"id": pid, "schema_version": 1, "created_at": NOW, "created_by": "user:admin", "updated_at": NOW, "updated_by": "user:admin", "source": "dashboard",
         "email": "someone%s@example.org" % pid[-3:], "role_id": new_id(10), "is_active": True}
    if name: d["display_name"] = name
    inner.create("access_persons", pid, d)               # straight into the inner store: not part of the history under test
PD, PE = new_id(904), new_id(905)                       # two people who share a name
person(PA, "Ada Lovelace"); person(PB, ""); person(PD, "Sam Same"); person(PE, "Sam Same")

def mkvenue(name, slug, actor):
    r = VEN.create(store, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": True}, actor); assert r.ok, r.problems; return r.data
va = mkvenue("Ada Venue", "ada_venue", "user:" + PA)
vb = mkvenue("Blank Venue", "blank_venue", "user:" + PB)
vc = mkvenue("Gone Venue", "gone_venue", "user:" + PC)
vk = mkvenue("Key Venue", "key_venue", "user:admin")
vd = mkvenue("Sam One Venue", "sam_one", "user:" + PD)
ve = mkvenue("Sam Two Venue", "sam_two", "user:" + PE)
r = VEN.soft_delete(store, va["id"], "user:" + PA); assert r.ok, r.problems          # a delete: "Deleted by" holds the actor

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 1000}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.__rej = []; window.addEventListener('unhandledrejection', function (e) { window.__rej.push(String(e.reason)); });")
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "activity"); pg.wait_for_selector("#activityView .avrow")
    pg.wait_for_function("document.querySelector('#avList').innerText.includes('Ada Lovelace')")
    def card(venue_name, action):
        return pg.locator("#activityView .avrow", has_text=venue_name).filter(has_text=action).first
    ada = card("Ada Venue", "Created").inner_text()
    check("N1 a named person's entry shows the name", "Ada Lovelace" in ada, ada)
    check("N1b ...and not the long id", PA not in ada)
    blank = card("Blank Venue", "Created").inner_text()
    check("N2 a person with no name on file shows the user id", PB in blank, blank)
    gone = card("Gone Venue", "Created").inner_text()
    check("N3 a person no longer on file shows the user id", PC in gone, gone)
    key = card("Key Venue", "Created").inner_text()
    check("N4 the admin key still reads Admin key", "Admin key" in key and "user:admin" not in key, key)
    dele = card("Ada Venue", "Deleted").inner_text()
    check("N5 a Deleted-by field inside an entry shows the name too", "Deleted by:" in dele and "Ada Lovelace" in dele.split("Deleted by:")[1] and PA not in dele, dele)
    alltxt = pg.inner_text("#avList")
    check("N6 no role label stands in for a person anywhere", "super admin" not in alltxt.lower() and "signed-in person" not in alltxt.lower() and "unknown" not in alltxt.lower())
    check("N7 hovering the byline gives the stored id", card("Ada Venue", "Created").locator(".avm").first.get_attribute("title") == "user:" + PA)
    check("N8 one name lookup for the whole load", state["people_calls"] == 1, state["people_calls"])
    pg.screenshot(path=str(SHOTS / "10_names.png"), full_page=True)

    # a refresh with nothing new asks nothing more
    pg.get_by_role("button", name="Refresh").click(); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length >= 5")
    check("N9 refresh with nothing new makes no new lookup", state["people_calls"] == 1, state["people_calls"])

    # search by name
    pg.fill("#avSearch", "lovelace"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 2")
    check("N10 searching a name finds that person's entries", all("Ada Venue" in t for t in pg.locator("#activityView .avrow").all_inner_texts()))
    pg.fill("#avSearch", "")

    # the Person-or-source filter by name
    pg.select_option("#avMode", "created_by"); pg.fill("#avValue", "Ada Lovelace"); pg.press("#avValue", "Enter")
    pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 2")
    check("N11 filtering by a person's name finds that person's entries", all("Ada Venue" in t for t in pg.locator("#activityView .avrow").all_inner_texts()))
    pg.fill("#avValue", "ada lovelace"); pg.press("#avValue", "Enter"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 2")
    check("N11b ...whatever the capital letters", True)
    pg.fill("#avValue", "Admin key"); pg.press("#avValue", "Enter"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 1")
    check("N12 filtering by 'Admin key' finds the key's entries", "Key Venue" in pg.inner_text("#avList"))
    pg.fill("#avValue", "user:" + PB); pg.press("#avValue", "Enter"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 1")
    check("N13 an id still works in the filter", "Blank Venue" in pg.inner_text("#avList"))
    pg.fill("#avValue", "Nobody Atall"); pg.press("#avValue", "Enter"); pg.wait_for_selector("#avList >> text=Nothing has been recorded")
    check("N14 a name nobody has gives an empty list, not an error", True)
    pg.fill("#avValue", "Sam Same"); pg.press("#avValue", "Enter"); pg.wait_for_selector("#activityView .avmsg:has-text('More than one person')")
    check("N14b two people with one name: no guess, a plain message, and the id is the way", pg.locator("#activityView .avrow").count() == 0)
    pg.select_option("#avMode", "all"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length >= 5")

    # a lookup that fails leaves ids showing
    pg.select_option("#collPick", "home")
    state["people_fail"] = True; state["people_calls"] = 0
    pg.evaluate("window.ActivityStation.reset()")           # a fresh station: nothing cached
    pg.select_option("#collPick", "activity"); pg.wait_for_selector("#activityView .avrow")
    pg.wait_for_function("window.__t = 1, document.querySelectorAll('#activityView .avrow').length >= 5")
    t = card("Ada Venue", "Created").inner_text()
    check("N15 when the lookup fails the user id is shown and the list still works", PA in t and "Ada Lovelace" not in t, t)
    # names not known yet when the person types one: the station fetches them first
    state["people_fail"] = False; state["key_only"] = True; state["people_calls"] = 0
    pg.select_option("#collPick", "home"); pg.evaluate("window.ActivityStation.reset()")
    pg.select_option("#collPick", "activity"); pg.wait_for_selector("#activityView .avrow")
    check("N17 (set up) the first load held only the key's entries and asked for no names", pg.locator("#activityView .avrow").count() == 1 and state["people_calls"] == 0, state["people_calls"])
    pg.select_option("#avMode", "created_by"); pg.fill("#avValue", "Ada Lovelace"); pg.press("#avValue", "Enter")
    pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 2")
    check("N17 a name typed before any name is known still finds the person (names are fetched first)", all("Ada Venue" in t for t in pg.locator("#activityView .avrow").all_inner_texts()))
    check("N16 no script errors", not errs, errs)
    pg.screenshot(path=str(SHOTS / "11_lookup_failed.png"), full_page=True)
    # ...and a lookup that never reaches the server at all
    pg.select_option("#collPick", "home"); state["people_fail"] = False; state["people_abort"] = True; state["key_only"] = False
    pg.evaluate("window.ActivityStation.reset()"); pg.select_option("#collPick", "activity"); pg.wait_for_selector("#activityView .avrow")
    pg.wait_for_timeout(500)
    t = card("Ada Venue", "Created").inner_text()
    check("N15b when the lookup cannot even reach the server the id is shown and nothing breaks", PA in t and pg.locator("#activityView .avrow").count() >= 5, t)
    check("N15c ...and no unhandled error is left behind", pg.evaluate("window.__rej.length") == 0, pg.evaluate("window.__rej"))
    state["people_abort"] = False
    b.close()

print("screenshots:", SHOTS)
print("\nOK: all name checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

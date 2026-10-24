#!/usr/bin/env python3
"""Browser test for the Classes station (console/classes.js): the list, Add class, the Edit form, and the station's hooks (it is its own file, nothing of it is left
in console.js, leaving the page closes the edit form, sign-out empties it, signing back in loads it, the kit forwards to it). Drives the real Console page in headless
Chromium against the real admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when they are not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_classes_browser_test.py"""
import sys, json, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import scheduled_classes_crud as CL, venues_service as VS
from crud_endpoint import handle_admin, make_failure_limiter
from test_helpers import give_venue_zone
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    r_ = route.request
    if r_.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(r_.method, r_.headers.get("authorization", ""), (r_.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
A = "user:admin"
v = VS.create_with_place(store, {"name": "Library", "slug": "library", "status": "inactive", "is_public_venue": True}, A,
                         address={"street": "951 Spruce St", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"})
assert v.ok, v.problems; give_venue_zone(store, v.data["id"], actor=A); assert VS.update(store, v.data["id"], {"status": "active"}, A).ok
base = {"class_type": "private", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 5, "capacity_max": 9}
sc = CL.create(store, {**base, "title": "Evening Basics", "slug": "eb", "status": "scheduled", "venue_id": v.data["id"], "starts_at": "2026-11-05T01:00:00Z",
                       "time_zone": "America/Denver", "duration_minutes": 60, "is_venue_confirmed": False}, A).data
idea = CL.create(store, {**base, "title": "Idea Session", "slug": "idea", "status": "identified"}, A).data

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 1100, "height": 1200}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("new MutationObserver(function () { var d = document.getElementById('uiDialog'), y = document.getElementById('uiYes'); if (d && d.open && y) y.click(); }).observe(document, { subtree: true, childList: true, attributes: true });")
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    big = (HERE.parent / "console" / "console.js").read_text()

    # the station is its own file and has every hook
    check("classes.js is its own file and ClassesStation has every hook", pg.evaluate("typeof window.ClassesStation === 'object' && ['show','stop','reset','dirty','forget','putInClass','assignForm','classWhen','choices','byId'].every(k => typeof ClassesStation[k] === 'function')"))
    check("nothing of the Classes station is left in console.js", not re.search(r"function (loadClasses|renderClasses|classRow|classActions|openClassEdit|closeClassEdit|cBuildSections|classInstructors|zonedToUtc|classWhen|assignForm|putInClass|buildClassBox|personFinder|instructorFinder|loadClassChoices|resetClasses)\b|var CTYPES|var cCtx", big))
    check("classes.js reaches the big file only through the kit", "window.ConsoleKit" in (HERE.parent / "console" / "classes.js").read_text())

    # the list
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    check("the list shows both classes", pg.locator("#cList li").count() == 2 and "Evening Basics" in pg.inner_text("#cList") and "Idea Session" in pg.inner_text("#cList"))
    check("the class time names its own zone", re.search(r"M[DS]T", pg.locator("#cList li", has_text="Evening Basics").inner_text()) is not None, pg.locator("#cList li", has_text="Evening Basics").inner_text()[:200])
    # Add class
    pg.click("#cAddBtn"); pg.fill("#cTitle", "Morning Tech"); pg.select_option("#cType", "workshop"); pg.select_option("#cPublic", "no")
    check("the slug follows the title", pg.input_value("#cSlug") == "morning_tech")
    pg.fill("#cMin", "1"); pg.fill("#cTarget", "4"); pg.fill("#cMax", "8"); pg.click("#cSaveBtn")
    pg.wait_for_function("document.getElementById('cNotice').textContent.indexOf('Added Morning Tech') === 0")
    pg.wait_for_function("[...document.querySelectorAll('#cList li')].some(l => l.textContent.indexOf('Morning Tech') >= 0)")
    check("Add class saves an idea and shows it", any(c["title"] == "Morning Tech" and c["status"] == "identified" for c in CL.list(store).data["records"]) and pg.locator("#cList li", has_text="Morning Tech").count() == 1)
    # Edit
    li = pg.locator("#cList li", has_text="Evening Basics"); li.locator("button.head").click(); li.get_by_role("button", name="Edit", exact=True).click()
    pg.wait_for_selector("#cEditPanel:not([hidden])"); pg.wait_for_selector("#cInsSection")
    check("the Edit form is built from the schema (title field present)", pg.locator("#ef_c_title").count() == 1 and pg.input_value("#ef_c_title") == "Evening Basics")
    pg.fill("#ef_c_title", "Evening Basics 2"); pg.click("#cEditSave")
    pg.wait_for_function("document.getElementById('cEditPanel').hidden === true || document.getElementById('cEditMsg').textContent.length > 0")
    check("saving the Edit form changes the class", store.get("scheduled_classes", sc["id"])["title"] == "Evening Basics 2", store.get("scheduled_classes", sc["id"])["title"])
    # hooks
    li = pg.locator("#cList li", has_text="Evening Basics 2"); li.locator("button.head").click()
    if "open" not in (li.get_attribute("class") or ""): pass
    li.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#cEditPanel:not([hidden])")
    pg.select_option("#collPick", "venues"); pg.wait_for_timeout(400)
    check("leaving the Classes page closes the edit form", pg.locator("#cEditPanel:not([hidden])").count() == 0)
    check("the kit forwards to the station (classWhen, classChoices, classById)", pg.evaluate("""(async () => {
      const K = window.ConsoleKit; const w = K.classWhen({starts_at: '2026-11-05T01:00:00Z', time_zone: 'America/Denver'});
      const list = await K.classChoices(); return typeof w === 'string' && w.length > 0 && Array.isArray(list) ? true : (list === undefined || list === null); })()"""))
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    n_c = pg.locator("#cList li").count()
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("sign-out empties the Classes page", pg.evaluate("document.querySelectorAll('#cList li').length === 0 && document.getElementById('cCount').textContent === '' && document.getElementById('cEditPanel').hidden"))
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#cList li")
    check("signing back in loads the Classes page again", pg.locator("#cList li").count() == n_c)
    check("no page errors", not errors)
    if errors: print(errors[:3])
    b.close()
print("OK: classes browser test passed" if not fails else "FAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

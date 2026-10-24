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
    li = pg.locator("#cList li", has_text="Evening Basics"); li.get_by_role("button", name="Edit", exact=True).click()
    pg.wait_for_selector("#cEditPanel:not([hidden])"); pg.wait_for_selector("#ef_c_title")
    check("the Edit form is built from the schema (title field present)", pg.locator("#ef_c_title").count() == 1 and pg.input_value("#ef_c_title") == "Evening Basics")
    pg.fill("#ef_c_title", "Evening Basics 2"); pg.click("#cEditSave")
    pg.wait_for_function("document.getElementById('cEditPanel').hidden === true || document.getElementById('cEditMsg').textContent.length > 0")
    check("saving the Edit form changes the class", store.get("scheduled_classes", sc["id"])["title"] == "Evening Basics 2", store.get("scheduled_classes", sc["id"])["title"])
    # the class page (hub): four tabs
    li = pg.locator("#cList li", has_text="Evening Basics 2"); li.locator("button.head").click()
    pg.wait_for_selector("#cHub:not([hidden])")
    check("tapping a class opens its page with four tabs", pg.locator("#cTabs [role=tab]").count() == 4 and pg.locator("#cMain").is_hidden() and pg.inner_text("#cHubTitle") == "Evening Basics 2")
    check("Overview is selected first and shows the class details", pg.get_attribute("#cTabBtnOverview", "aria-selected") == "true" and pg.locator("#cTabOverview .detail").count() == 1)
    ov = pg.inner_text("#cTabOverview .detail")
    check("Overview reads in plain words (status, when, where, people, price) with no raw field names",
          all(w in ov for w in ("Status:", "Kind:", "When:", "Where:", "People:")) and not any(r in ov for r in ("starts_at", "venue_id", "class_type", "capacity_max")), ov[:300])
    check("the full field list is still there, folded under All fields",
          pg.locator("#cTabOverview details.allfields").count() == 1 and pg.locator("#cTabOverview details.allfields[open]").count() == 0 and "starts_at" in (pg.text_content("#cTabOverview .rawfields") or ""))
    pg.click("#cTabBtnPeople"); pg.wait_for_selector("#cInstructors")
    check("People tab shows instructors and the add form", pg.locator("#cTabPeople #cPeopleAdd").count() == 1 and pg.locator("#cTabOverview").is_hidden())
    pg.click("#cTabBtnAttendance"); pg.wait_for_selector("#cTabAttendance #atOnlyTab")
    check("Attendance tab draws the roster inline (dialog stays closed)", pg.locator("#atDlg[open]").count() == 0 and pg.locator("#cTabAttendance section.stu").count() == 1)
    pg.focus("#cTabBtnAttendance"); pg.keyboard.press("ArrowRight"); pg.wait_for_selector("#ef_c_title")
    check("arrow keys move between tabs (Edit opens the form)", pg.get_attribute("#cTabBtnEdit", "aria-selected") == "true" and pg.locator("#cTabEdit #cEditPanel:not([hidden])").count() == 1)
    pg.fill("#ef_c_title", "Evening Basics 3")
    check("an edited form counts as unsaved", pg.evaluate("window.ClassesStation.dirty()") is True)
    pg.click("#cTabBtnOverview"); pg.wait_for_selector("#cTabOverview .detail")
    check("leaving Edit asks, then drops the change without saving", pg.get_attribute("#cTabBtnOverview", "aria-selected") == "true" and pg.evaluate("window.ClassesStation.dirty()") is False and store.get("scheduled_classes", sc["id"])["title"] == "Evening Basics 2")
    pg.click("#cTabBtnEdit"); pg.wait_for_selector("#ef_c_title")
    pg.fill("#ef_c_title", "Evening Basics 2"); pg.click("#cHubBack"); pg.wait_for_selector("#cMain:not([hidden])")
    check("Back returns to the list and closes the page", pg.locator("#cHub").is_hidden() and pg.locator("#cList li").count() >= 2)
    ids = pg.evaluate("[...document.querySelectorAll('[id]')].map(e=>e.id).filter((x,i,a)=>a.indexOf(x)!==i).length")
    check("no duplicate ids on the page", ids == 0, ids)
    # hooks
    li = pg.locator("#cList li", has_text="Evening Basics 2")
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

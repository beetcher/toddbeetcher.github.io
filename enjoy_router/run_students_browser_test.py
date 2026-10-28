"""Browser test for the Students station stations: drives the real Console page in headless Chromium against the real
admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_students_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
PAGE = (HERE.parent / "console" / "index.html").as_uri()
from datetime import datetime, timezone
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_service as IS
from crud_endpoint import handle_admin, make_failure_limiter
from test_helpers import give_address
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore("")
limiter = make_failure_limiter()
fails = []
def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok: fails.append(label)

def admin_route(route):
    req = route.request
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}, body=json.dumps(r.body))

def cors(route):
    if route.request.method == "OPTIONS":
        route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    else:
        admin_route(route)

def people(): return IS.list(store, None, limit=200).data["records"]

def status_is(pg, pre, *vals):
    """Tick exactly these statuses in the Status chip (the old drop-down is gone)."""
    pg.locator("#%sChips .cf-chip" % pre, has_text="Status").click()
    for v in ("active", "inactive"):
        box = pg.locator("#%sChips .cf-pop input[type=checkbox][value=%s]" % (pre, v))
        if box.is_checked() != (v in vals): box.click()
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)

def status_ticked(pg, pre):
    pg.locator("#%sChips .cf-chip" % pre, has_text="Status").click()
    got = [v for v in ("active", "inactive") if pg.locator("#%sChips .cf-pop input[type=checkbox][value=%s]" % (pre, v)).is_checked()]
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    return got

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", cors)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE)
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    for n in ("Instructors", "Students"):
        check(n + " tile on Home", pg.locator("#stationTiles .tile", has_text=n).count() == 1)
    red = pg.evaluate("Array.from(document.querySelectorAll('#collPick option')).filter(o => o.style.color).map(o => o.textContent)")
    check("Access, Activity, Discovery, Performance, People and Places are red in the station menu", sorted(red) == ["Access (admin)", "Activity (admin)", "Discovery (admin)", "People (admin)", "Performance (admin)", "Places (admin)"])
    check("Access, Activity, Discovery, Performance, People and Places tiles are red on Home", pg.locator("#stationTiles .tile.adm").count() == 6)
    pg.click("#helpOpen")
    check("manual buttons for both rosters", pg.locator("#overlayBtns button", has_text="Instructors").count() == 1 and pg.locator("#overlayBtns button", has_text="Students").count() == 1)
    pg.click("#manualClose")

    give_address(store, IS.create(store, {"given_name": "Ann", "family_name": "Lee", "email": "ann@example.com"}, "user:admin").data["id"])
    people = lambda: list(store.data.get("individuals", {}).values())
    check("Students tile on Home", pg.locator("#stationTiles .tile", has_text="Students").count() == 1)
    pg.select_option("#collPick", "students")
    pg.wait_for_selector("#studentsView:not([hidden])")
    pg.wait_for_function("document.getElementById('rsChecked').textContent.length > 0")
    check("student roster starts empty", pg.locator("#rsEmpty").is_visible())
    check("the add button says Add student and the form has a note but no bio", pg.locator("#rsAddBtn").inner_text() == "Add student" and pg.locator("#rsA_bio").count() == 0)
    pg.click("#rsAddBtn"); pg.click("#rsSaveBtn")
    check("saving with nobody picked asks to pick someone", "Pick someone" in pg.locator("#rsEPick").inner_text())
    pg.fill("#rsQ", "ann"); pg.wait_for_selector("#rsOpts button")
    pg.locator("#rsOpts button", has_text="Ann Lee").click(); pg.fill("#rsA_notes", "Brings her husband.")
    pg.click("#rsSaveBtn"); pg.wait_for_selector("#rsList li")
    check("an existing person is added to the roster", "Ann Lee" in pg.locator("#rsList").inner_text() and "Added Ann Lee to the students" in pg.locator("#rsNotice").inner_text())
    pg.click("#rsAddBtn"); pg.fill("#rsQ", "cy day"); pg.wait_for_selector("#rsOpts button"); pg.locator("#rsOpts button").last.click()
    pg.click("#rsSaveBtn"); pg.wait_for_function("document.querySelectorAll('#rsList li').length == 2")
    check("someone new makes a new person", any((x.get("given_name") or "").lower() == "cy" for x in people()))
    pg.click("#rsAddBtn"); pg.fill("#rsQ", "ann"); pg.wait_for_selector("#rsOpts button")
    check("a duplicate is marked 'already a student'", "already a student" in pg.locator("#rsOpts").inner_text())
    pg.click("#rsCancelBtn")
    li = pg.locator("#rsList li", has_text="Ann Lee"); li.locator("button.head").click()
    check("the card shows the note", "Brings her husband." in li.inner_text())
    li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    check("a student's edit form has no hours, curricula or regions", form.locator("input[type=time]").count() == 0 and form.locator("input[type=checkbox]").count() == 0)
    form.locator("textarea[id$='_notes']").fill("Brings her husband and a friend.")
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('rsNotice').textContent.indexOf('Saved') === 0")
    check("edit saved", any(r.get("notes") == "Brings her husband and a friend." for r in store.data.get("student_rosters", {}).values()))
    li = pg.locator("#rsList li", has_text="Cy"); li.locator("button.head").click()
    li.get_by_role("button", name="Remove from students", exact=True).click(); li.get_by_role("button", name="Remove", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('#rsList li').length == 1")
    check("removed from the students", "Removed" in pg.locator("#rsNotice").inner_text())
    pg.select_option("#collPick", "students"); pg.click("#studentsView .manualBtn")
    check("Students manual opens", pg.locator("#manual h2", has_text="Students").is_visible())
    # the station is its own file (the Roster extraction, RO-2)
    import re
    big = (HERE.parent / "console" / "console.js").read_text(); mine = (HERE.parent / "console" / "students.js").read_text()
    check("students.js is its own file and StudentsStation has every hook", pg.evaluate("typeof window.StudentsStation === 'object' && ['show','reset','forget'].every(k => typeof window.StudentsStation[k] === 'function')"))
    check("nothing of the Students station is left in console.js", not re.search(r"student_rosters|rsAddBtn|rsList|StudentsStation\.(load|all)", big))
    check("students.js is only its settings", "ConsoleRoster.build" in mine and len(mine.split("\n")) < 20)
    pg.select_option("#collPick", "students"); pg.wait_for_selector("#rsList li")
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("sign-out empties the Students page", pg.evaluate("document.querySelectorAll('#rsList li').length === 0 && document.getElementById('rsCount').textContent === '' && document.getElementById('rsChecked').textContent === '' && document.getElementById('rsAddForm').hidden"))
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_function("document.getElementById('rsChecked').textContent.length > 0")
    check("signing back in loads the Students page again", pg.locator("#rsCount").inner_text() != "")
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("\n%s" % ("FAILED: " + ", ".join(fails) if fails else "OK: all student browser checks passed"))
sys.exit(1 if fails else 0)

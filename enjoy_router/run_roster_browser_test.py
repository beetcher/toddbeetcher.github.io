"""Browser test for the Instructors and Students stations: drives the real Console page in headless Chromium against the real
admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_roster_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
PAGE = (HERE.parent / "console" / "index.html").as_uri()
from datetime import datetime, timezone
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_service as IS
from crud_endpoint import handle_admin, make_failure_limiter
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
    check("People and Places are red in the station menu", sorted(red) == ["People", "Places"])
    check("manual buttons for both rosters", pg.locator("#homeManualBtns button", has_text="Instructors").count() == 1 and pg.locator("#homeManualBtns button", has_text="Students").count() == 1)

    bob = IS.create(store, {"given_name": "Bob", "family_name": "Ray", "email": "bob@example.com"}, "user:admin").data

    pg.select_option("#collPick", "instructors")
    pg.wait_for_selector("#instructorsView:not([hidden])")
    pg.wait_for_function("document.getElementById('riChecked').textContent.length > 0")
    check("empty state", pg.locator("#riEmpty").is_visible())

    # nothing picked: refused with a plain message
    pg.click("#riAddBtn"); pg.click("#riSaveBtn")
    check("must pick a person or say new", "Pick a person" in pg.locator("#riEPick").inner_text())
    # a new person
    pg.fill("#riQ", "Ann Lee")
    pg.wait_for_selector("#riOpts button")
    check("typed name offers only 'new person' when nobody matches", pg.locator("#riOpts button").count() == 1)
    pg.click("#riOpts button")
    check("new person boxes prefilled from what was typed", pg.input_value("#riN_given_name") == "Ann" and pg.input_value("#riN_family_name") == "Lee")
    pg.fill("#riN_given_name", "")
    pg.click("#riSaveBtn")
    check("new person needs a given name", pg.locator("#riN_given_name + .ferr").inner_text() == "Required.")
    pg.fill("#riN_given_name", "Ann"); pg.fill("#riN_email", "ANN@Example.com"); pg.fill("#riN_phone", "303-555-0142")
    pg.fill("#riA_bio", "Retired nurse."); pg.fill("#riA_capabilities", "prompting basics, large rooms")
    pg.click("#riSaveBtn")
    pg.wait_for_selector("#riList li")
    txt = pg.locator("#riList").inner_text()
    check("new instructor listed with contact", "Ann Lee" in txt and "ann@example.com" in txt and "prompting basics, large rooms" in txt)
    check("added notice", "Added Ann Lee to the instructors" in pg.locator("#riNotice").inner_text())
    check("the new person exists in People", any(x.get("given_name") == "Ann" and x.get("email") == "ann@example.com" for x in people()))
    check("add form closed", pg.locator("#riAddForm").is_hidden())

    # an existing person
    pg.click("#riAddBtn"); pg.fill("#riQ", "bob")
    pg.wait_for_selector("#riOpts button")
    check("existing person offered with contact", "bob@example.com" in pg.locator("#riOpts").inner_text())
    pg.locator("#riOpts button", has_text="Bob Ray").click()
    check("chosen line shown", "Adding Bob Ray" in pg.locator("#riChosen").inner_text())
    pg.click("#riSaveBtn")
    pg.wait_for_function("document.querySelectorAll('#riList li').length == 2")
    check("existing person added; no extra person made", len([x for x in people() if x.get("given_name") == "Bob"]) == 1)
    # already an instructor
    pg.click("#riAddBtn"); pg.fill("#riQ", "ann")
    pg.wait_for_selector("#riOpts button")
    check("already-on-roster is marked", "already an instructor" in pg.locator("#riOpts").inner_text())
    pg.locator("#riOpts button", has_text="already an instructor").click()
    pg.wait_for_selector("#riList li.open")
    check("opens the existing card", "Ann Lee" in pg.locator("#riList li.open").inner_text() and pg.locator("#riAddForm").is_hidden())

    # edit: person and roster fields together
    li = pg.locator("#riList li", has_text="Ann Lee")
    form_open = li.locator("form.eform")
    li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    form.locator("input[id$='_phone']").fill("303-555-0199")
    form.locator("input[id$='_service_area']").fill("Denver metro")
    tt = form.locator("input[type=time]")
    tt.nth(2).fill("09:00"); tt.nth(3).fill("15:00")
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('riNotice').textContent.indexOf('Saved') === 0")
    pg.wait_for_function("document.querySelectorAll('#riList li').length == 2")
    li = pg.locator("#riList li", has_text="Ann Lee"); li.locator("button.head").click()
    check("hours and area shown", "Tue 09:00–15:00" in li.inner_text() and "Denver metro" in li.inner_text())
    check("phone changed in People too", any(x.get("given_name") == "Ann" and x.get("phone", "").endswith("0199") for x in people()))
    # bad hours
    li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform"); tt = form.locator("input[type=time]")
    tt.nth(0).fill("10:00"); tt.nth(1).fill("09:00")
    form.get_by_role("button", name="Save changes").click()
    check("start-after-end is explained", "before the end" in form.inner_text())
    form.get_by_role("button", name="Cancel").click()
    # nothing changed
    li.get_by_role("button", name="Edit", exact=True).click()
    li.locator("form.eform").get_by_role("button", name="Save changes").click()
    check("nothing changed says so", "Nothing changed" in pg.locator("#riNotice").inner_text())
    # inactive filter (opening a card from the add window switched the list to All, as designed)
    check("opening an existing card switches the list to All", pg.input_value("#riFilter") == "")
    pg.select_option("#riFilter", "active")
    li = pg.locator("#riList li", has_text="Ann Lee"); li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    li.locator("form.eform select").select_option("inactive")
    li.locator("form.eform").get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.querySelectorAll('#riList li').length == 1")
    check("inactive leaves the Active list", "Ann Lee" not in pg.locator("#riList").inner_text())
    pg.select_option("#riFilter", "")
    check("All shows both", pg.locator("#riList li").count() == 2)
    pg.select_option("#riFilter", "active")
    # remove, then add back
    li = pg.locator("#riList li", has_text="Bob Ray"); li.locator("button.head").click()
    li.get_by_role("button", name="Remove from instructors").click()
    li.get_by_role("button", name="Remove", exact=True).click()
    pg.wait_for_function("document.getElementById('riNotice').textContent.indexOf('Removed') === 0")
    check("removed from list", pg.locator("#riList li", has_text="Bob Ray").count() == 0)
    check("Bob is still in People", any(x.get("given_name") == "Bob" for x in people()))
    pg.click("#riAddBtn"); pg.fill("#riQ", "bob"); pg.wait_for_selector("#riOpts button")
    check("removed person is not marked as already on", "already" not in pg.locator("#riOpts").inner_text())
    pg.locator("#riOpts button", has_text="Bob Ray").click(); pg.click("#riSaveBtn")
    pg.wait_for_function("document.querySelectorAll('#riList li').length == 1")
    check("added back", pg.locator("#riList li", has_text="Bob Ray").count() == 1)

    # students
    pg.select_option("#collPick", "students")
    pg.wait_for_selector("#studentsView:not([hidden])")
    pg.wait_for_function("document.getElementById('rsChecked').textContent.length > 0")
    check("student roster starts empty", pg.locator("#rsEmpty").is_visible())
    check("student add form has a note but no bio", pg.locator("#rsAddBtn").inner_text() == "Add student")
    pg.click("#rsAddBtn"); pg.fill("#rsQ", "ann"); pg.wait_for_selector("#rsOpts button")
    pg.locator("#rsOpts button", has_text="Ann Lee").click(); pg.fill("#rsA_notes", "Brings her husband.")
    pg.click("#rsSaveBtn"); pg.wait_for_selector("#rsList li")
    check("a person can be an instructor and a student", "Ann Lee" in pg.locator("#rsList").inner_text())
    pg.click("#rsAddBtn"); pg.fill("#rsQ", "cy day"); pg.wait_for_selector("#rsOpts button"); pg.locator("#rsOpts button").last.click()
    pg.click("#rsSaveBtn"); pg.wait_for_function("document.querySelectorAll('#rsList li').length == 2")
    check("new student made a new person", any(x.get("given_name") == "cy" or x.get("given_name") == "Cy" for x in people()))
    pg.click("#rsAddBtn"); pg.fill("#rsQ", "ann"); pg.wait_for_selector("#rsOpts button")
    check("student duplicate is marked 'already a student'", "already a student" in pg.locator("#rsOpts").inner_text())
    pg.click("#rsCancelBtn")

    # People list reloaded with the people made here
    pg.select_option("#collPick", "people"); pg.wait_for_selector("#peopleView:not([hidden])")
    pg.wait_for_function("document.querySelectorAll('#pList li').length >= 3")
    check("People station shows the people added from the rosters", "Ann Lee" in pg.locator("#pList").inner_text())
    # manual opens
    pg.select_option("#collPick", "instructors"); pg.click("#instructorsView .manualBtn")
    check("Instructors manual opens", pg.locator("#manual h2", has_text="Instructors").is_visible())
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("\n%s" % ("FAILED: " + ", ".join(fails) if fails else "OK: all roster browser checks passed"))
sys.exit(1 if fails else 0)

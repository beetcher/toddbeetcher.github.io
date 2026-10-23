"""Browser test for attendance in the Console (class Attendance dialog, person History, Put in a class on a request): drives the real Console page in headless Chromium against the real
admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_attendance_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
PAGE = (HERE.parent / "console" / "index.html").as_uri()
from datetime import datetime, timezone
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_service as IS
from crud import scheduled_classes_crud as CL
from crud import attendances_service as AT
from crud import curriculums_crud as CU
from crud import venues_crud as VS
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
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
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


A = "user:admin"
cl = CL.create(store, {"title": "Evening Basics", "slug": "evening_basics", "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
                       "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2, "starts_at": "2026-11-05T01:00:00Z", "time_zone": "America/Denver"}, A)
assert cl.ok, cl.problems
cls = cl.data
ann = IS.create(store, {"given_name": "Ann", "family_name": "Able"}, A).data
ina = IS.create(store, {"given_name": "Ina", "family_name": "Teach"}, A).data
give_address(store, ina["id"])   # an instructor needs an address (slice B)
cu = CU.create(store, {"title": "Intro to AI", "slug": "intro_ai", "session_count": 3, "minutes_per_session": 90}, A).data
ven = VS.create(store, {"name": "Library", "slug": "library", "status": "active", "is_public_venue": True, "email": "pat@example.com", "contact_individual_id": "5b1f0c2e-7a4d-4c3b-9e6f-1a2b3c4d5e6f", "is_accessible": True, "allows_minors": True, "allows_animals": False, "rooms": [{"label": "Room A", "max_occupancy": 10}]}, A)
assert ven.ok, ven.problems
REQ = {"id": "11111111-1111-4111-8111-111111111111", "confirmation_number": "LCH-0001", "registration_type": "private", "attendee_count": 1, "created_at": "2026-10-10T12:00:00Z",
       "first_name": "Chuck", "last_name": "Norris", "email": "chuck@example.com", "processing_status": "received"}
REQ2 = {**REQ, "id": "22222222-2222-4222-8222-222222222222", "confirmation_number": "LCH-0002", "first_name": "Dana", "last_name": "Fox", "email": "dana@example.com", "created_at": "2026-10-10T13:00:00Z"}
# the server looks the request up to copy its confirmation number
store.create(AT.REQUESTS.name, REQ["id"], dict(REQ))
store.create(AT.REQUESTS.name, REQ2["id"], dict(REQ2))

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", cors)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": [REQ, REQ2]}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE)
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    pg.wait_for_function("document.getElementById('attnBadge').textContent === '2'")
    check("Home lists the unplaced request", "Chuck Norris" in pg.locator("#attnBody").inner_text() and "waiting to be placed" in pg.locator("#attnBox").inner_text().lower(), pg.locator("#attnBox").inner_text())
    check("no Assignments station any more", pg.locator("#stationTiles .tile .tname", has_text="Assignments").count() == 0 and pg.locator("#collPick option", has_text="Assignments").count() == 0)
    # ---- class Attendance dialog
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    li = pg.locator("#cList li", has_text="Evening Basics")
    li.get_by_role("button", name="Attendance", exact=True).click()
    pg.wait_for_selector("#atDlg[open] #atBody .bandname")
    check("dialog titled with the class", "Attendance: Evening Basics" in pg.locator("#atTitle").inner_text())
    check("empty class says so", "No instructor yet." in pg.locator("#atBody").inner_text() and "No students yet." in pg.locator("#atBody").inner_text())
    pg.locator("#atAddBox summary").click()
    def add_existing(role, query, name):
        f = pg.locator("#atBody form")
        f.locator("select[id$='_role']").select_option(role)
        f.locator("select[id$='_who']").select_option("existing")
        f.locator("input[placeholder='Search by name']").fill(query)
        pg.locator("#atBody form button", has_text=name).first.click()
        f.get_by_role("button", name="Add to class").click()
    add_existing("primary_instructor", "ina", "Ina Teach")
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Ina Teach') === 0")
    check("lead instructor added and joins the instructor list", "lead instructor" in pg.locator("#atMsg").inner_text() and "Added to the instructor list" in pg.locator("#atMsg").inner_text())
    check("instructor row marked lead", "Ina Teach (lead)" in pg.locator("#atBody").inner_text())
    check("three bands in order: Show, Instructors, Students", pg.eval_on_selector_all("#atBody > section.atband", "els => els.map(e => e.className.replace('atband ', ''))") == ["show", "inst", "stu"])
    check("student band holds the seat summary and the add form", pg.locator("#atBody section.stu .rsum").count() == 1 and pg.locator("#atBody section.stu #atAddBox").count() == 1)
    fz = pg.eval_on_selector_all("#atBody > section.atband", "els => els.map(e => parseFloat(getComputedStyle(e).fontSize))")
    check("Show and Instructors are smaller than Students", fz[0] < fz[2] * 0.8 and fz[1] < fz[2] * 0.8, fz)
    check("rows show their own reference number", "ICDT-A-" in pg.locator("#atBody section.inst").inner_text(), pg.locator("#atBody section.inst").inner_text())
    pg.locator("#atAddBox summary").click()
    add_existing("student", "ann", "Ann Able")
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Ann Able') === 0")
    pg.locator("#atAddBox summary").click()
    f = pg.locator("#atBody form")
    f.locator("select[id$='_who']").select_option("new")
    f.locator("input[id$='_given_name']").fill("Bob"); f.locator("input[id$='_family_name']").fill("Brown")
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Bob Brown') === 0")
    check("new student added to the student list", "student list" in pg.locator("#atMsg").inner_text())
    pg.locator("#atAddBox summary").click()
    f = pg.locator("#atBody form")
    f.locator("select[id$='_who']").select_option("new")
    f.locator("input[id$='_given_name']").fill("Cy")
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Cy') === 0")
    check("third student goes to the waiting list", "on the waiting list" in pg.locator("#atMsg").inner_text())
    try:
        pg.wait_for_function("document.getElementById('atBody').innerText.indexOf('2 of up to 2 seats taken, 1 waiting') >= 0", timeout=5000)
    except Exception:
        pass
    check("seat summary", "2 of up to 2 seats taken, 1 waiting" in pg.locator("#atBody").inner_text(), pg.locator("#atBody").inner_text())
    pg.locator("#atAddBox summary").click()
    f = pg.locator("#atBody form")
    f.locator("select[id$='_who']").select_option("existing")
    f.locator("input[placeholder='Search by name']").fill("ann")
    pg.locator("#atBody form button", has_text="Ann Able").first.click()
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.querySelector('#atBody form .msg') && document.querySelector('#atBody form .msg').textContent.length > 0")
    check("same person twice is refused in plain words", "already in this class" in pg.locator("#atBody form .msg").inner_text())
    ann_row = pg.locator("#atBody .arow", has_text="Ann Able")
    ann_row.locator("select").select_option("attended")
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Ann Able: attended') === 0")
    check("a status that is not a leaving (attended) says nothing about emails", "emailed" not in pg.locator("#atMsg").inner_text(), pg.locator("#atMsg").inner_text())
    bob_row = pg.locator("#atBody .arow", has_text="Bob Brown")
    bob_row.get_by_role("button", name="Remove").click()
    check("remove asks twice", pg.locator("#atBody .arow", has_text="Bob Brown").get_by_role("button", name="Really remove?").count() == 1)
    pg.locator("#atBody .arow", has_text="Bob Brown").get_by_role("button", name="Really remove?").click()
    pg.wait_for_function("document.getElementById('atBody').innerText.indexOf('Bob Brown') < 0")
    check("removed student gone, record kept", "record is kept" in pg.locator("#atMsg").inner_text())
    check("removing a seated student says they and the instructors were emailed", "They were emailed, and so were the instructors" in pg.locator("#atMsg").inner_text(), pg.locator("#atMsg").inner_text())
    pg.click("#atClose")
    # ---- person History
    pg.select_option("#collPick", "people"); pg.wait_for_selector("#pList li")
    li = pg.locator("#pList li", has_text="Ann Able"); li.locator("button.head").click()
    li.get_by_role("button", name="History", exact=True).click()
    pg.wait_for_function("document.querySelector('#pList li.open .rhead') !== null")
    t = pg.locator("#pList li", has_text="Ann Able").inner_text()
    check("history shows class, role and status", "Evening Basics" in t and "Student" in t and "Attended" in t, t)
    li = pg.locator("#pList li", has_text="Ina Teach"); li.locator("button.head").click()
    li.get_by_role("button", name="History", exact=True).click()
    pg.wait_for_function("document.querySelector('#pList li.open .rhead') !== null")
    try: pg.wait_for_function("document.querySelector('#pList li.open').innerText.indexOf('Lead instructor') >= 0", timeout=8000)
    except Exception: pass
    check("instructor history shows the lead role", "Lead instructor" in pg.locator("#pList li", has_text="Ina Teach").inner_text())
    # ---- request card
    pg.select_option("#collPick", "requests"); pg.wait_for_selector("#list li", state="attached")
    li = pg.locator("#list li", has_text="Chuck Norris")
    li.get_by_role("button", name="Put in a class…").click()
    pg.wait_for_selector("#list li .putbox form")
    f = li.locator(".putbox form")
    check("request details prefill the new person", f.locator("input[id$='_given_name']").input_value() == "Chuck" and f.locator("input[id$='_email']").input_value() == "chuck@example.com")
    f.get_by_role("button", name="Cancel", exact=True).click()
    check("Cancel backs out of the form", not pg.locator("#list li", has_text="Chuck Norris").locator(".putbox").first.is_visible())
    li.get_by_role("button", name="Put in a class…").click()
    pg.wait_for_selector("#list li .putbox form")
    f = li.locator(".putbox form")
    f.get_by_role("button", name="Add to class").click()
    check("class is required", "Choose a class" in f.locator(".msg").inner_text())
    f.locator("select[id$='_cls']").select_option(label=pg.locator("select[id$='_cls'] option").nth(2).inner_text())
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.getElementById('reqDone').hidden === false")
    t = pg.locator("#reqDone").inner_text()
    check("request closed with its number, class named", "LCH-0001 is closed" in t and "Chuck Norris is in" in t, t)
    check("the form closed, no repeat adds", not pg.locator("#list li .putbox form").count() or not pg.locator("#list li .putbox").first.is_visible())
    pg.wait_for_function("document.getElementById('countText').innerText.indexOf('1 open request') === 0")
    check("closed request leaves the open list", not pg.locator("#list li", has_text="Chuck Norris").is_visible() and pg.locator("#list li", has_text="Dana Fox").is_visible(), pg.locator("#countText").inner_text())
    pg.click('#reqSeg [data-v="closed"]')
    check("Closed filter shows it with a Closed chip", pg.locator("#list li", has_text="Chuck Norris").is_visible() and "Closed" in pg.locator("#list li", has_text="Chuck Norris").locator(".qrow .qchip").inner_text(), pg.locator("#countText").inner_text())
    pg.click('#reqSeg [data-v="open"]')
    placed = AT.list(store, {"request_id": REQ["id"]})
    check("attendance records the request", placed.ok and placed.data["count"] == 1 and placed.data["records"][0]["role"] == "student", placed.problems if not placed.ok else "")
    check("attendance carries the confirmation number", placed.data["records"][0].get("confirmation_number") == "LCH-0001", placed.data["records"][0])
    check("no old Assign button or roster chips", pg.locator("#list li .qrow .go").count() == 0)
    # ---- build a class from the request
    li2 = pg.locator("#list li", has_text="Dana Fox")
    li2.get_by_role("button", name="Put in a class…").click()
    pg.wait_for_selector("#list li:has-text('Dana Fox') .putbox form")
    f = li2.locator(".putbox form")
    f.locator("select[id$='_cls']").select_option(label="+ A new class (build it now)")
    check("build box appears", f.locator(".addbox").first.is_visible())
    f.locator("select[id$='_n_cur']").select_option(index=1)
    check("title fills from curriculum and requester", f.locator("input[id$='_n_title']").input_value() == "Intro to AI for Dana Fox", f.locator("input[id$='_n_title']").input_value())
    f.locator("select[id$='_n_ven']").select_option(label="Library")
    f.locator("select[id$='_n_room']").select_option("Room A")
    f.locator("input[id$='_n_date']").fill("2026-11-12"); f.locator("input[id$='_n_time']").fill("18:00")
    f.locator(".addbox input[placeholder='Search instructors by name']").fill("ina")
    f.locator(".addbox button", has_text="Ina Teach").first.click()
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.getElementById('reqDone').innerText.indexOf('LCH-0002 is closed') >= 0")
    t = pg.locator("#reqDone").inner_text()
    check("class built from the request, request closed", "Dana Fox is in Intro to AI for Dana Fox" in t, t)
    built = [c for c in CL.list(store).data["records"] if c["title"] == "Intro to AI for Dana Fox"]
    c0 = built[0] if built else {}
    check("built class is scheduled with curriculum, series and session 1", c0.get("status") == "scheduled" and c0.get("curriculum_id") == cu["id"] and c0.get("session_number") == 1 and c0.get("series_id") and c0.get("venue_room_label") == "Room A" and c0.get("duration_minutes") == 90, c0)
    n_att = AT.list(store, {"scheduled_class_id": c0.get("id")}).data["count"] if c0 else 0
    check("two attendance records on the built class", n_att == 2, n_att)
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    check("class cards have no Registered chip", "Registered:" not in pg.locator("#cList").inner_text())
    pg.select_option("#collPick", "home")
    pg.wait_for_function("document.getElementById('attnBody').innerText.indexOf('All clear') >= 0")
    check("Home is clear once placed", True)
    # ---- class edit form: curriculum, series, session number
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    li = pg.locator("#cList li", has_text="Evening Basics"); li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    pg.wait_for_selector("#ef_c_curriculum_id")
    check("edit form offers the curriculum", pg.locator("#ef_c_curriculum_id option", has_text="Intro to AI").count() == 1)
    pg.select_option("#ef_c_curriculum_id", cu["id"])
    check("a series pick offers the built series", pg.locator("#ef_c_series_id option", has_text="Series of Intro to AI for Dana Fox").count() == 1)
    pg.select_option("#ef_c_series_id", label="Series of Intro to AI for Dana Fox (1 class)")
    pg.fill("#ef_c_session_number", "1"); pg.click("#cEditSave")
    pg.wait_for_function("document.getElementById('ee_c_session_number').textContent.length > 0")
    check("taken session number shown on its field", "already has that number" in pg.locator("#ee_c_session_number").inner_text(), pg.locator("#ee_c_session_number").inner_text() + " | " + pg.locator("#cEditMsg").inner_text() + " | " + pg.locator("#ee_c_series_id").inner_text())
    pg.fill("#ef_c_session_number", "2"); pg.click("#cEditSave")
    pg.wait_for_function("document.getElementById('cNotice').textContent.indexOf('Saved') === 0")
    ev = [c for c in CL.list(store).data["records"] if c["title"] == "Evening Basics"][0]
    check("edit saved curriculum, series and session 2", ev.get("curriculum_id") == cu["id"] and ev.get("session_number") == 2 and ev.get("series_id") == c0.get("series_id"), ev)
    check("a save that does not change the when or where does not claim anyone is emailed", "emailed" not in pg.locator("#cNotice").inner_text(), pg.locator("#cNotice").inner_text())
    li = pg.locator("#cList li", has_text="Evening Basics"); li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#ef_c_venue_notes")
    pg.fill("#ef_c_venue_notes", "Use the side door"); pg.click("#cEditSave")
    pg.wait_for_function("document.getElementById('cNotice').textContent.indexOf('emailed') >= 0")
    check("a change to the venue notes says everyone placed is being emailed", "Everyone placed in it is being emailed what changed" in pg.locator("#cNotice").inner_text(), pg.locator("#cNotice").inner_text())
    # ---- journal, workflows, cancel cascade
    pg.select_option("#collPick", "home")
    pg.click("#helpHomeW"); pg.wait_for_selector("#manual:not([hidden])")
    check("Help lists the workflows", pg.locator("#wfBody details.wfcard").count() == 4, pg.locator("#wfBody").inner_text())
    pg.locator("#wfBody details", has_text="When a class is cancelled").locator("summary").click()
    pg.locator("#wfBody details", has_text="When a class is cancelled").get_by_role("button", name="Open Classes").click()
    pg.wait_for_selector("#cList li")
    check("a workflow jump button goes to the station", pg.locator("#collPick").input_value() == "classes")
    li = pg.locator("#cList li", has_text="Intro to AI for Dana Fox"); li.get_by_role("button", name="Journal").click()
    pg.wait_for_function("document.getElementById('jrBody').innerText.indexOf('Placed in a class') >= 0")
    jt = pg.locator("#jrBody").inner_text()
    check("class Journal shows who was placed", "Dana Fox" in jt and "Placed in a class" in jt, jt)
    pg.click("#jrClose")
    pg.select_option("#collPick", "requests"); pg.wait_for_selector("#list li", state="attached"); pg.click('#reqSeg [data-v="all"]')
    pg.locator("#list li", has_text="Chuck Norris").get_by_role("button", name="Journal").click()
    pg.wait_for_function("document.getElementById('jrBody').innerText.indexOf('Placed in a class') >= 0")
    check("request Journal opens", True); pg.click("#jrClose")
    pg.click("#reqInfo"); pg.wait_for_selector("#manual:not([hidden]) #wfBody")
    check("the info button opens the workflows", pg.locator("#wfBody details.wfcard").count() >= 2)
    pg.locator("#wfBody details").first.locator("summary").click()
    pg.locator("#wfBody").get_by_role("button", name="Open Classes").first.click()
    pg.wait_for_selector("#cList li")
    check("a step button jumps and closes the help", pg.locator("#collPick").input_value() == "classes" and pg.locator("#manual:not([hidden])").count() == 0)
    li = pg.locator("#cList li", has_text="Intro to AI for Dana Fox")
    check("Edit, Cancel class and Delete are on the tile, no need to open it", li.get_by_role("button", name="Edit", exact=True).is_visible() and li.get_by_role("button", name="Cancel class").is_visible() and li.get_by_role("button", name="Delete", exact=True).is_visible())
    li.get_by_role("button", name="Cancel class").click()
    check("the cancel dialog says everyone is emailed", "also emailed that it is cancelled" in li.locator(".confirm").inner_text(), li.locator(".confirm").inner_text())
    li.get_by_placeholder("Why? (optional)").fill("Student sick")
    li.locator(".confirm").get_by_role("button", name="Cancel class").click()
    pg.wait_for_function("document.getElementById('cNotice').textContent.indexOf('Cancelled') === 0")
    check("the notice after a cancel says they were emailed", "cancelled and emailed" in pg.locator("#cNotice").inner_text(), pg.locator("#cNotice").inner_text())
    gone = [a["status"] for a in AT.list(store, {"scheduled_class_id": c0["id"]}).data["records"]]
    check("cancelling the class cancels everyone in it", gone and all(x == "cancelled" for x in gone), gone)
    pg.select_option("#collPick", "requests"); pg.wait_for_selector("#list li", state="attached"); pg.click('#reqSeg [data-v="all"]')
    pg.wait_for_function("Array.from(document.querySelectorAll('#list li')).some(function (l) { return l.innerText.indexOf('Dana Fox') >= 0 && l.querySelector('.qrow').innerText.indexOf('Open') >= 0; })")
    check("cancelling the class reopens the request", True)
    check("the other request stays closed", "Closed" in pg.locator("#list li", has_text="Chuck Norris").locator(".qrow .qchip").inner_text())
    pg.click('#reqSeg [data-v="open"]')
    check("reopened request is back in the open list", pg.locator("#list li", has_text="Dana Fox").is_visible() and not pg.locator("#list li", has_text="Chuck Norris").is_visible())
    pg.select_option("#collPick", "home")
    pg.wait_for_function("document.getElementById('attnBody').innerText.toLowerCase().indexOf('dana') >= 0")
    check("with no live placement the request is back in Waiting to be placed", True)
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    pg.locator("#cList li", has_text="Intro to AI for Dana Fox").get_by_role("button", name="Journal").click()
    pg.wait_for_function("document.getElementById('jrBody').innerText.indexOf('Class cancelled') >= 0")
    jt = pg.locator("#jrBody").inner_text()
    check("Journal records the class cancelled, and no back-to-waiting while the request has another placement", "Class cancelled" in jt and "Request back to waiting" in jt, jt)
    pg.click("#jrClose")
    pg.locator("#cList li", has_text="Intro to AI for Dana Fox").get_by_role("button", name="Attendance").click()
    pg.wait_for_selector("#atOnly")
    pg.select_option("#atOnly", "assigned")
    pg.wait_for_function("document.getElementById('atBody').innerText.indexOf('No students yet') >= 0")
    check("status filter inside a class", True)
    pg.click("#atClose")
    # ---- Attendance station: tick-box filters apply on Refresh
    pg.select_option("#collPick", "attendance"); pg.wait_for_selector("#aList li")
    n_all = pg.locator("#aList li").count()
    check("Attendance station lists every record", n_all >= 4 and "Chuck Norris" in pg.locator("#aList").inner_text(), n_all)
    check("rows show reference numbers", "ICDT-A-" in pg.locator("#aList").inner_text())
    pg.locator("#aFilters input[data-f=status][value=assigned]").uncheck()
    check("ticking does nothing until Refresh", pg.locator("#aList li").count() == n_all)
    pg.click("#aApply")
    pg.wait_for_function("document.querySelectorAll('#aList li').length < %d" % n_all)
    st = pg.eval_on_selector_all("#aList li select", "els => els.map(e => e.value)")
    check("Refresh applies the status filter", "assigned" not in st and len(st) > 0, st)
    check("summary says some records are hidden", "hidden" in pg.locator("#aFilterSummary").inner_text())
    pg.click("#aShowAll"); pg.wait_for_function("document.querySelectorAll('#aList li').length === %d" % n_all)
    pg.fill("#aSearch", "chuck"); pg.press("#aSearch", "Enter")
    pg.wait_for_function("Array.from(document.querySelectorAll('#aList li')).every(function (l) { return /chuck/i.test(l.innerText); }) && document.querySelectorAll('#aList li').length > 0")
    check("search finds a person", True)
    pg.locator("#aFilters input[data-f=role][value=student]").uncheck(); pg.click("#aApply")
    pg.wait_for_function("document.getElementById('aEmpty').hidden === false || document.querySelectorAll('#aList li').length === 0")
    check("role filter hides students", pg.locator("#aList li").count() == 0)
    pg.click("#aShowAll"); pg.wait_for_function("document.querySelectorAll('#aList li').length === %d" % n_all)
    pg.locator("#aList li").first.locator("button.chiplink").click()
    pg.wait_for_selector("#atDlg[open]")
    check("class name opens that class's attendance", "Attendance:" in pg.locator("#atTitle").inner_text())
    pg.click("#atClose")
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("\n%s" % ("FAILED: " + ", ".join(fails) if fails else "OK: all attendance browser checks passed"))
sys.exit(1 if fails else 0)

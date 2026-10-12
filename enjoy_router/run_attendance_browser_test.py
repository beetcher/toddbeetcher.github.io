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
from crud_endpoint import handle_admin, make_failure_limiter
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
REQ = {"id": "11111111-1111-4111-8111-111111111111", "confirmation_number": "LCH-0001", "registration_type": "private", "attendee_count": 1, "created_at": "2026-10-10T12:00:00Z",
       "first_name": "Chuck", "last_name": "Norris", "email": "chuck@example.com", "processing_status": "received"}

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", cors)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": [REQ]}})))
    pg.goto(PAGE)
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    # ---- class Attendance dialog
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    li = pg.locator("#cList li", has_text="Evening Basics")
    li.get_by_role("button", name="Attendance", exact=True).click()
    pg.wait_for_selector("#atDlg[open] #atBody .rhead")
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
    pg.locator("#atAddBox summary").click()
    add_existing("student", "ann", "Ann Able")
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Ann Able') === 0")
    pg.locator("#atAddBox summary").click()
    f = pg.locator("#atBody form")
    f.locator("select[id$='_who']").select_option("new")
    f.locator("input[id$='_given_name']").fill("Bob"); f.locator("input[id$='_family_name']").fill("Brown")
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Bob Brown') === 0")
    check("new person created and put on the student list", "They were new" in pg.locator("#atMsg").inner_text() and "student list" in pg.locator("#atMsg").inner_text())
    pg.locator("#atAddBox summary").click()
    f = pg.locator("#atBody form")
    f.locator("select[id$='_who']").select_option("new")
    f.locator("input[id$='_given_name']").fill("Cy")
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Cy') === 0")
    check("third student goes to the waiting list", "on the waiting list" in pg.locator("#atMsg").inner_text())
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
    bob_row = pg.locator("#atBody .arow", has_text="Bob Brown")
    bob_row.get_by_role("button", name="Remove").click()
    check("remove asks twice", pg.locator("#atBody .arow", has_text="Bob Brown").get_by_role("button", name="Really remove?").count() == 1)
    pg.locator("#atBody .arow", has_text="Bob Brown").get_by_role("button", name="Really remove?").click()
    pg.wait_for_function("document.getElementById('atBody').innerText.indexOf('Bob Brown') < 0")
    check("removed student gone but still a person", "still in People" in pg.locator("#atMsg").inner_text())
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
    check("instructor history shows the lead role", "Lead instructor" in pg.locator("#pList li", has_text="Ina Teach").inner_text())
    # ---- request card
    pg.select_option("#collPick", "requests"); pg.wait_for_selector("#list li")
    li = pg.locator("#list li", has_text="Chuck Norris")
    li.get_by_role("button", name="Put in a class…").click()
    pg.wait_for_selector("#list li .putbox form")
    f = li.locator(".putbox form")
    check("request details prefill the new person", f.locator("input[id$='_given_name']").input_value() == "Chuck" and f.locator("input[id$='_email']").input_value() == "chuck@example.com")
    f.get_by_role("button", name="Add to class").click()
    check("class is required", "Choose a class" in f.locator(".msg").inner_text())
    f.locator("select[id$='_cls']").select_option(label=pg.locator("select[id$='_cls'] option").nth(1).inner_text())
    f.get_by_role("button", name="Add to class").click()
    pg.wait_for_function("document.querySelector('#list li .putbox .note') !== null")
    t = pg.locator("#list li .putbox").inner_text()
    check("requester placed, new person created", "Added Chuck Norris" in t and "They were new" in t and "Placed from this request" in t, t)
    placed = AT.list(store, {"request_id": REQ["id"]})
    check("attendance records the request", placed.ok and placed.data["count"] == 1 and placed.data["records"][0]["role"] == "student", placed.problems if not placed.ok else "")
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("\n%s" % ("FAILED: " + ", ".join(fails) if fails else "OK: all attendance browser checks passed"))
sys.exit(1 if fails else 0)

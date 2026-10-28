#!/usr/bin/env python3
"""Browser test (roster look combo): Instructors, Students and Curriculum: head, chips, paging, rows, button cues, plain words, states, forms, phone.
Run from enjoy_router/:  python3 run_roster_look_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_crud as I, instructor_rosters_service as INS, student_rosters_service as STU, curriculums_crud as CU, locations_crud as L, location_links_service as LKS
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
INS.R.needs_address = False
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []; A = "user:admin"
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def person(g, f): return I.create(store, {"given_name": g, "family_name": f}, A).data
def home(p):
    loc = L.create(store, {"name": p["given_name"] + " home", "addresses": [{"usage": "civic", "street_number": "1", "street": "Main St", "locality": "Town", "region": "CO", "postal_code": "80027", "country": "US"}]}, A).data
    assert LKS.create(store, {"subject_type": "individual", "subject_id": p["id"], "location_id": loc["id"], "relationship": "resides_at", "is_primary": True}, A).ok
# curricula
cids = []
for i, (t, sl, n, m) in enumerate([("Intro to AI", "intro_ai", 3, 90), ("Everyday AI", "everyday_ai", 1, 60), ("Voice and images", "voice_images", 2, 45), ("Old course", "old_course", 1, 30)]):
    r = CU.create(store, {"title": t, "slug": sl, "session_count": n, "minutes_per_session": m}, A); assert r.ok, r.problems; cids.append(r.data["id"])
CU.update(store, cids[3], {"status": "inactive"}, A)
# instructors: 5 with address (two with a curriculum), 1 without address, 1 inactive
names = ["Ann Lee", "Bob Ray", "Cy Dunn", "Di Fox", "Ed Gray", "Flo Hill", "Gus Ito"]
for i, nm in enumerate(names):
    g, f = nm.split(); p = person(g, f)
    if i != 5: home(p)
    d = {"individual_id": p["id"]}
    if i < 2: d["curriculum_ids"] = [cids[0]]
    r = INS.create(store, d, A); assert r.ok, r.problems
    if i == 6: INS.update(store, r.data["id"], {"status": "inactive"}, A)
# students: 55, the last 3 inactive
for i in range(55):
    p = person("Stu%02d" % i, "Pupil")
    r = STU.create(store, {"individual_id": p["id"]}, A); assert r.ok, r.problems
    if i >= 52: STU.update(store, r.data["id"], {"status": "inactive"}, A)
def chip_open(pg, pre, label): pg.locator("#%sChips .cf-chip" % pre, has_text=label).click()
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")

    # ===== Instructors
    pg.evaluate("location.hash='#/instructors'"); pg.wait_for_selector("#riList li")
    check("INS head: title, orange Add, Manual and Refresh as links", pg.inner_text("#riTitle") == "Instructors" and "btn-primary" in pg.get_attribute("#riAddBtn", "class") and "btn-link" in pg.get_attribute("#riRefresh", "class") and pg.locator("#instructorsView .manualBtn.btn-link").count() == 1)
    check("INS old drop-down gone, Status chip present", pg.locator("#riFilter").count() == 0 and pg.locator("#riChips .cf-chip", has_text="Status").count() == 1)
    check("INS count in plain words, active only", pg.inner_text("#riCount") == "6 instructors" and pg.locator("#riList > li").count() == 6, pg.inner_text("#riCount"))
    check("INS sorted by name", pg.evaluate("(function(){var t=[].map.call(document.querySelectorAll('#riList > li .vname'),function(e){return e.textContent});return JSON.stringify(t)===JSON.stringify(t.slice().sort())})()"))
    check("INS two across at 1440", pg.evaluate("(function(){var l=document.querySelectorAll('#riList > li');return l[0].getBoundingClientRect().top === l[1].getBoundingClientRect().top})()"))
    pg.locator("#riChips .cf-chip", has_text="Needs an address").click(); pg.wait_for_timeout(250)
    check("INS Needs an address narrows to the one without", pg.locator("#riList > li").count() == 1 and "Flo Hill" in pg.inner_text("#riList"))
    pg.locator("#riChips .cf-chip", has_text="Needs an address").click(); pg.wait_for_timeout(200)
    pg.locator("#riChips .cf-chip", has_text="No curriculum yet").click(); pg.wait_for_timeout(250)
    check("INS No curriculum yet narrows to those without", pg.locator("#riList > li").count() == 4)
    pg.locator("#riChips .cf-chip", has_text="No curriculum yet").click(); pg.wait_for_timeout(200)
    pg.fill("#riSearch", "zzzz"); pg.wait_for_timeout(250)
    check("INS no-match with a Clear link", pg.evaluate("document.getElementById('riNoMatch').hidden === false") and pg.locator("#riClear").count() == 1)
    pg.click("#riClear"); pg.wait_for_timeout(300)
    check("INS clearing restores the list", pg.locator("#riList > li").count() == 6 and pg.input_value("#riSearch") == "")
    li = pg.locator("#riList > li", has_text="Ann Lee").first; li.locator("button.head").click()
    cls = lambda t: li.get_by_role("button", name=t, exact=True).first.get_attribute("class")
    check("INS cues: Edit orange, Add address outlined, Remove red", "btn-primary" in cls("Edit") and "btn-secondary" in cls("Replace address") and "btn-danger" in cls("Remove from instructors"))
    li.get_by_role("button", name="Edit", exact=True).click()
    check("INS edit form has sections", li.locator(".eform .fsec").count() >= 4)
    li.get_by_role("button", name="Cancel", exact=True).first.click()
    pg.click("#riAddBtn")
    check("INS add form: sections, star, orange Save, outlined Cancel", pg.locator("#riAddForm .fsec").count() >= 1 and pg.locator("#riAddForm .req").count() >= 1 and "btn-primary" in pg.get_attribute("#riSaveBtn", "class") and "btn-secondary" in pg.get_attribute("#riCancelBtn", "class"))
    pg.click("#riCancelBtn")

    # ===== Students
    pg.evaluate("location.hash='#/students'"); pg.wait_for_selector("#rsList li")
    check("STU first page is 50 of 52 active, with Load more", pg.locator("#rsList > li").count() == 50 and pg.locator("#rsMore .morebar").count() == 1 and "52" in pg.inner_text("#rsMore"), pg.inner_text("#rsMore"))
    pg.locator("#rsMore button").first.click(); pg.wait_for_timeout(300)
    check("STU Load more shows the rest", pg.locator("#rsList > li").count() == 52)
    check("STU count and title", pg.inner_text("#rsCount") == "52 students" and pg.inner_text("#rsTitle") == "Students")

    # ===== Curriculum
    pg.evaluate("location.hash='#/curriculums'"); pg.wait_for_selector("#rcList li")
    txt = pg.locator("#rcList").inner_text()
    check("CUR rows: plain words, no identifier, inactive hidden", "3 sessions · 90 minutes each" in txt and "1 session · 60 minutes" in txt and "intro_ai" not in txt and "Old course" not in txt, txt)
    check("CUR head and chips", pg.inner_text("#rcTitle") == "Curriculum" and "btn-primary" in pg.get_attribute("#rcAddBtn", "class") and pg.locator("#rcChips .cf-chip", has_text="Status").count() == 1 and pg.locator("#rcFilter").count() == 0)
    pg.fill("#rcSearch", "voice"); pg.wait_for_timeout(250)
    check("CUR search narrows by title", pg.locator("#rcList > li").count() == 1)
    pg.fill("#rcSearch", "zzzz"); pg.wait_for_timeout(250)
    pg.click("#rcClear"); pg.wait_for_timeout(300)
    check("CUR Clear restores", pg.locator("#rcList > li").count() == 3)
    li = pg.locator("#rcList > li", has_text="Intro to AI").first; li.locator("button.head").click()
    check("CUR opened card shows the identifier", "intro_ai" in li.locator(".detail").inner_text())
    cls = lambda t: li.get_by_role("button", name=t, exact=True).first.get_attribute("class")
    check("CUR cues: Edit orange, Delete red", "btn-primary" in cls("Edit") and "btn-danger" in cls("Delete"))
    pg.click("#rcAddBtn")
    check("CUR add form: sections, stars, cues", pg.locator("#rcAddForm .fsec").count() >= 2 and pg.locator("#rcAddForm .req").count() == 2 and "btn-primary" in pg.get_attribute("#rcSaveBtn", "class") and "btn-secondary" in pg.get_attribute("#rcCancelBtn", "class"))
    pg.click("#rcCancelBtn")

    # ===== phone
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    for route, v in (("instructors", "instructorsView"), ("students", "studentsView"), ("curriculums", "curriculumsView")):
        pg.evaluate("location.hash='#/%s'" % route); pg.wait_for_timeout(500)
        check("PHONE %s: no sideways scroll, header one row, buttons tall enough" % route, pg.evaluate("document.documentElement.scrollWidth <= 391") and pg.evaluate("document.getElementById('topbar').getBoundingClientRect().height") <= 64
              and pg.evaluate("[].filter.call(document.querySelectorAll('#%s .phead button'), function(b){return b.offsetParent && b.getBoundingClientRect().height < 40 && !b.classList.contains('btn-link')}).length" % v) == 0)
    check("no page errors", not errs, errs)
    b.close()
print("ALL OK" if not fails else "FAILED: %d" % len(fails)); sys.exit(1 if fails else 0)

"""Browser test for the Curriculum station and the instructor card's curricula: drives the real Console page in headless Chromium against the real
admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_curriculum_browser_test.py"""
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
    check("Curriculum tile on Home", pg.locator("#stationTiles .tile .tname", has_text="Curriculum").count() == 1)
    IS.create(store, {"given_name": "Ina", "family_name": "Teach"}, "user:admin")
    pg.select_option("#collPick", "curriculums")
    pg.wait_for_selector("#curriculumsView:not([hidden])")
    pg.wait_for_function("document.getElementById('rcChecked').textContent.length > 0")
    check("empty state", pg.locator("#rcEmpty").is_visible())
    pg.click("#rcAddBtn"); pg.click("#rcSaveBtn")
    check("title and identifier required", pg.locator("#rcA_title ~ .ferr").inner_text() == "Required." and pg.locator("#rcA_slug ~ .ferr").inner_text() == "Required.")
    pg.fill("#rcA_title", "Introduction to AI Use")
    check("identifier fills itself in", pg.input_value("#rcA_slug") == "introduction_to_ai_use")
    pg.fill("#rcA_session_count", "x")
    pg.click("#rcSaveBtn")
    check("sessions must be a whole number", "whole number" in pg.locator("#rcA_session_count ~ .ferr").inner_text())
    pg.fill("#rcA_session_count", "1"); pg.fill("#rcA_minutes_per_session", "60"); pg.fill("#rcA_slug", "intro_ai_use")
    pg.click("#rcSaveBtn"); pg.wait_for_selector("#rcList li")
    txt = pg.locator("#rcList").inner_text()
    check("listed with identifier, sessions and minutes", "Introduction to AI Use" in txt and "intro_ai_use" in txt and "1 session of 60 min" in txt, txt)
    check("added notice", "Added Introduction to AI Use" in pg.locator("#rcNotice").inner_text())
    pg.click("#rcAddBtn"); pg.fill("#rcA_title", "Dup"); pg.fill("#rcA_slug", "intro_ai_use"); pg.click("#rcSaveBtn")
    pg.wait_for_function("document.querySelector('#rcA_slug ~ .ferr').textContent.length > 0")
    check("duplicate identifier shown on its field", "already used" in pg.locator("#rcA_slug ~ .ferr").inner_text())
    pg.fill("#rcA_title", "AI for Everyday Life"); pg.fill("#rcA_slug", "everyday"); pg.fill("#rcA_session_count", "3"); pg.fill("#rcA_minutes_per_session", "90"); pg.click("#rcSaveBtn")
    pg.wait_for_function("document.querySelectorAll('#rcList li').length == 2")
    check("series shows 3 sessions of 90 min", "3 sessions of 90 min" in pg.locator("#rcList").inner_text())
    li = pg.locator("#rcList li", has_text="Everyday Life") if False else pg.locator("#rcList li", has_text="AI for Everyday Life")
    li.locator("button.head").click(); li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    check("identifier is not editable", form.locator("input[id$='_slug']").count() == 0)
    form.locator("input[id$='_minutes_per_session']").fill("45")
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('rcNotice').textContent.indexOf('Saved') === 0")
    pg.wait_for_function("document.getElementById('rcList').innerText.indexOf('45 min') >= 0")
    check("edit saved", True)
    # instructor can-teach
    pg.select_option("#collPick", "instructors"); pg.wait_for_selector("#instructorsView:not([hidden])")
    pg.wait_for_function("document.getElementById('riChecked').textContent.length > 0")
    pg.click("#riAddBtn"); pg.fill("#riQ", "ina"); pg.wait_for_selector("#riOpts button")
    pg.locator("#riOpts button", has_text="Ina Teach").click(); pg.click("#riSaveBtn"); pg.wait_for_selector("#riList li")
    li = pg.locator("#riList li", has_text="Ina Teach"); li.locator("button.head").click(); li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    check("both curricula offered as tick boxes", form.locator("input[type=checkbox]").count() == 2)
    form.locator("label", has_text="Introduction to AI Use").locator("input").check()
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('riList').innerText.indexOf('Can teach: Introduction to AI Use') >= 0")
    check("instructor card shows what they can teach", True)
    # inactive curricula are not offered; delete
    pg.select_option("#collPick", "curriculums"); pg.wait_for_selector("#curriculumsView:not([hidden])")
    li = pg.locator("#rcList li", has_text="AI for Everyday Life"); li.locator("button.head").click(); li.get_by_role("button", name="Edit", exact=True).click()
    li.locator("form.eform select").select_option("inactive"); li.locator("form.eform").get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.querySelectorAll('#rcList li').length == 1")
    check("inactive leaves the Active list", "Everyday" not in pg.locator("#rcList").inner_text())
    li = pg.locator("#rcList li", has_text="Introduction"); li.locator("button.head").click()
    li.get_by_role("button", name="Delete", exact=True).click(); li.get_by_role("button", name="Delete curriculum").click()
    pg.wait_for_function("document.querySelectorAll('#rcList li').length == 0")
    check("deleted", "Deleted" in pg.locator("#rcNotice").inner_text())
    pg.select_option("#collPick", "instructors"); pg.click("#riRefresh")
    pg.wait_for_function("document.getElementById('riList').innerText.indexOf('removed curriculum') >= 0")
    check("a deleted curriculum shows as removed on the instructor", True)
    pg.select_option("#collPick", "curriculums"); pg.click("#curriculumsView .manualBtn")
    check("Curriculum manual opens", pg.locator("#manual h2", has_text="Curriculum").is_visible())
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("\n%s" % ("FAILED: " + ", ".join(fails) if fails else "OK: all curriculum browser checks passed"))
sys.exit(1 if fails else 0)

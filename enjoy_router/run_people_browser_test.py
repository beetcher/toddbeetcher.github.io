"""Browser test for the People station: drives the real Console page in headless Chromium against the real admin endpoint
code with an in-memory store. Needs playwright and a Chromium (skips when they are not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_people_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
PAGE = (HERE.parent / "console" / "index.html").as_uri()
from datetime import datetime, timezone
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore("")   # the real collections, in memory
limiter = make_failure_limiter()
fails = []
def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok: fails.append(label)

def admin_route(route):
    req = route.request
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers={**{k: v for k, v in (r.headers or {}).items()}, "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}, body=json.dumps(r.body))

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
    check("People tile on Home", pg.locator("#stationTiles .tile", has_text="People").count() == 1)
    pg.select_option("#collPick", "people")
    pg.wait_for_selector("#peopleView:not([hidden])")
    pg.wait_for_function("document.getElementById('pChecked').textContent.length > 0")
    check("empty state", pg.locator("#pEmpty").is_visible())

    def add(given, family="", birth=""):
        pg.click("#pAddBtn"); pg.fill("#paGiven", given); pg.fill("#paFamily", family); pg.fill("#paBirth", birth); pg.click("#pSaveBtn")
    pg.click("#pAddBtn"); pg.click("#pSaveBtn")
    check("given name required message", pg.locator("#epaGiven").inner_text() == "Required.")
    pg.click("#pCancelBtn")
    add("Ann", "Lee", "04-17-1961"); pg.wait_for_selector("#pList li")
    check("American date shown back as Apr 17, 1961", "Born Apr 17, 1961" in pg.locator("#pList").inner_text())
    check("added Ann", "Added Ann Lee" in pg.locator("#pNotice").inner_text())
    pg.click("#pAddBtn"); pg.fill("#paGiven", "Bad"); pg.fill("#paBirth", "13-45-1961"); pg.click("#pSaveBtn")
    pg.wait_for_function("document.getElementById('epaBirth').textContent.length > 0")
    check("bad birth date shown on its field", "month first" in pg.locator("#epaBirth").inner_text())
    pg.click("#pCancelBtn")
    add("Annie", "Lee"); pg.wait_for_function("document.querySelectorAll('#pList li').length == 2")
    check("two people listed", pg.locator("#pCount").inner_text() == "2 people")
    pg.fill("#pSearch", "annie")
    check("search narrows", pg.locator("#pList li").count() == 1)
    pg.fill("#pSearch", "zzz"); check("no match message", pg.locator("#pNoMatch").is_visible())
    pg.fill("#pSearch", "")

    li = pg.locator("#pList li", has_text="Annie")
    li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    li.locator("input[id$='_given_name']") if False else None
    form = li.locator("form.eform")
    form.locator("input").nth(5).fill("4/5/1961")    # birth_date, typed with slashes and one-digit parts
    pass
    form.locator("input").nth(3).fill("Annie L")      # name_to_use
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Saved') === 0")
    check("edit saved", True)
    pg.wait_for_function("document.querySelectorAll('#pList li').length == 2")
    check("4/5/1961 stored as April 5", "Born Apr 5, 1961" in pg.locator("#pList").inner_text())
    li = pg.locator("#pList li", has_text="Annie L")
    check("name_to_use shows as display name", li.count() == 1)
    li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    li.locator("form.eform input").nth(5).fill("19x1")
    li.locator("form.eform").get_by_role("button", name="Save changes").click()
    pg.wait_for_function("Array.from(document.querySelectorAll('.eform .ferr')).some(e => e.textContent.length)")
    check("bad edit refused with a message", "month first" in li.locator("form.eform").inner_text())
    li.locator("form.eform").get_by_role("button", name="Cancel").click()

    # merge Annie L into Ann Lee
    li.get_by_role("button", name="Merge into another person").click()
    li.get_by_role("button", name="Merge", exact=True).click()
    check("merge needs a choice and a reason", li.locator(".mergebox .ferr").first.inner_text() == "Choose one.")
    li.locator(".mergebox select").select_option(label="Ann Lee (born Apr 17, 1961)")
    li.locator(".mergebox input").fill("same birth year and family, confirmed")
    li.get_by_role("button", name="Merge", exact=True).click()
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Merged') === 0")
    check("merge notice", "into Ann Lee" in pg.locator("#pNotice").inner_text())
    check("duplicate left the active list", pg.locator("#pList li").count() == 1)
    pg.click("#pHist summary"); pg.wait_for_selector("#pHList li")
    pg.wait_for_function("document.getElementById('pHList').textContent.indexOf('merged into') >= 0")
    check("merge history lists it", "merged into" in pg.locator("#pHList").inner_text())
    pg.get_by_role("button", name="Undo this merge").click()
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Undone') === 0")
    pg.wait_for_function("document.querySelectorAll('#pList li').length == 2")
    check("undo brings the person back", pg.locator("#pList li", has_text="Annie L").count() == 1)
    pg.wait_for_function("document.querySelector('#pHList li') && document.querySelector('#pHList li').textContent.indexOf('unmerged') >= 0")
    check("history now says unmerged, no undo button", pg.get_by_role("button", name="Undo this merge").count() == 0)

    # delete
    li = pg.locator("#pList li", has_text="Annie L"); li.locator("button.head").click()
    li.get_by_role("button", name="Delete", exact=True).click(); li.get_by_role("button", name="Delete person").click()
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Deleted') === 0")
    pg.wait_for_function("document.querySelectorAll('#pList li').length == 1")
    check("deleted person gone", pg.locator("#pList li").count() == 1)
    pg.select_option("#pFilter", "inactive"); pg.wait_for_function("document.getElementById('pEmpty').hidden === false")
    check("inactive filter empty", True)

    # contact: how to reach the person
    people_rows = lambda: list(store.data.get("individuals", {}).values())
    pg.select_option("#pFilter", "active"); pg.wait_for_function("document.querySelectorAll('#pList li').length == 1")
    pg.click("#pAddBtn"); pg.fill("#paGiven", "Cy"); pg.fill("#paEmail", "nope"); pg.click("#pSaveBtn")
    pg.wait_for_function("document.getElementById('epaEmail').textContent.length > 0")
    check("bad email shown on its own box", "email address does not look right" in pg.locator("#epaEmail").inner_text())
    pg.fill("#paEmail", "Cy@Example.COM"); pg.fill("#paPhone", "call me"); pg.click("#pSaveBtn")
    pg.wait_for_function("document.getElementById('epaPhone').textContent.length > 0")
    check("bad phone shown on its own box", "phone number does not look right" in pg.locator("#epaPhone").inner_text())
    pg.fill("#paPhone", "303-555-0142"); pg.click("#pSaveBtn")
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Added Cy') === 0")
    cy = next(x for x in people_rows() if x["given_name"] == "Cy")
    check("added with email lowercased and phone, no preference stored", cy["email"] == "cy@example.com" and cy["phone"] == "303-555-0142" and "prefers_email" not in cy)
    li = pg.locator("#pList li", has_text="Cy"); li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    check("contact boxes are on the edit form", all(form.get_by_label(t, exact=True).count() == 1 for t in ("Email", "Backup email", "Backup phone")))
    form.get_by_label("Backup email", exact=True).fill("Cy2@Example.org")
    form.get_by_label("How do they want to hear from us?", exact=True).select_option(label="Text message")
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Saved') === 0")
    cy = next(x for x in people_rows() if x["given_name"] == "Cy")
    check("backup email lowercased and preference stored as text (false)", cy["backup_email"] == "cy2@example.org" and cy["prefers_email"] is False)
    li = pg.locator("#pList li", has_text="Cy"); li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    check("the edit form shows the stored preference", form.get_by_label("How do they want to hear from us?", exact=True).input_value() == "text")
    form.get_by_label("How do they want to hear from us?", exact=True).select_option(label="Not said (the one they gave, or email if both)")
    form.get_by_label("Backup email", exact=True).fill("")
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Saved') === 0")
    cy = next(x for x in people_rows() if x["given_name"] == "Cy")
    check("clearing removes the preference and the backup email", "prefers_email" not in cy and "backup_email" not in cy)

    # the Console cannot reach protected details
    resp = pg.evaluate("""key => fetch('https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_admin', {method:'POST', headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'}, body: JSON.stringify({collection:'individual_restricted_details', op:'list', args:{}})}).then(r=>r.status)""", KEY)
    check("protected details refused on the Console door", resp == 400)
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("FAILED:" if fails else "ALL OK", fails)
sys.exit(1 if fails else 0)

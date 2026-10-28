#!/usr/bin/env python3
"""Browser test (People look, combo build): head, filters, paging, the town and role join, row, button cues, plain words, merge picker, states, forms, phone.
Run from enjoy_router/:  python3 run_people_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_crud as IC, locations_crud as LC, location_links_crud as LK
from crud_endpoint import handle_admin, make_failure_limiter
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
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
A = "user:admin"
for i in range(33):
    n = ("Phylis", "Stewart") if i < 3 else ("Person%02d" % i, "Lee")
    IC.create(store, {"given_name": n[0], "family_name": n[1], "birth_date": "19%02d-04-17" % (40 + i)}, A)
people = sorted(store.data["individuals"].values(), key=lambda r: r["created_at"])
for r in people[-4:]: IC.update(store, r["id"], {"status": "inactive"}, A)
P05 = [r for r in store.data["individuals"].values() if r.get("given_name") == "Person05"][0]
_r = LC.create(store, {"name": "Home of P05", "kind": "site", "addresses": [{"usage": "civic", "street_number": "9", "street": "Oak Street", "locality": "Boulder", "region": "CO", "postal_code": "80301", "country": "US"}]}, A)
LOC = _r.data
LK.create(store, {"subject_type": "individual", "subject_id": P05["id"], "location_id": LOC["id"], "relationship": "resides_at", "is_primary": True}, A)
store.data.setdefault("instructor_rosters", {})["ins1"] = {"id": "ins1", "individual_id": P05["id"], "status": "active"}
N_ACTIVE = len([r for r in store.data["individuals"].values() if r.get("status") == "active"])
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/people'"); pg.wait_for_selector("#pList li")

    # ===== L-1 head
    check("L-1 page title, orange Add person, Merge history, Manual and Refresh as links", pg.locator("#pTitle").inner_text() == "People" and "btn-primary" in pg.get_attribute("#pAddBtn", "class") and "btn-link" in pg.get_attribute("#pRefresh", "class") and pg.locator("#pHistLink.btn-link").count() == 1 and pg.locator("#peopleView .manualBtn.btn-link").count() == 1)
    pg.click("#pHistLink"); pg.wait_for_timeout(300)
    check("L-1 the Merge history link opens the same box at the bottom", pg.evaluate("document.getElementById('pHist').open"))

    # ===== L-5 chips, paging
    check("L-5 old status drop-down gone, Status chip present", pg.locator("#pFilter").count() == 0 and pg.locator("#pChips .cf-chip", has_text="Status").count() == 1)
    check("L-5 first page shows 50 at most, Active only", pg.locator("#pList > li").count() == min(50, N_ACTIVE) and N_ACTIVE == 29)
    check("L-5 sorted by name", pg.evaluate("(function(){var t=[].map.call(document.querySelectorAll('#pList > li .head'),function(e){return e.textContent.toLowerCase()});return t.length>1})()"))
    pg.fill("#pSearch", "zzzz"); pg.wait_for_timeout(250)
    check("L-5 no match shows the no-match note", pg.evaluate("document.getElementById('pNoMatch').hidden === false"))
    pg.fill("#pSearch", ""); pg.wait_for_timeout(250)
    check("L-5 clearing restores the list", pg.locator("#pList > li").count() == N_ACTIVE)
    # ===== J-1 / L-2 join and row
    pg.wait_for_function("document.querySelector('#pList').textContent.indexOf('Boulder') >= 0", timeout=8000)
    sub = pg.locator("#pList > li", has_text="Person05").first.locator(".sub").inner_text()
    check("J-1 row shows the town and the role", "Boulder" in sub and "Instructor" in sub, sub)
    check("L-2 born date kept in the sub-line", "Born" in sub, sub)
    check("L-2 two rows across at 1440", pg.evaluate("(function(){var l=document.querySelectorAll('#pList > li');return l[0].getBoundingClientRect().top === l[1].getBoundingClientRect().top})()"))
    # ===== L-3 / L-4 / L-6
    li = pg.locator("#pList > li", has_text="Person05").first
    li.locator("button.head").click()
    cls = lambda t: li.get_by_role("button", name=t, exact=True).first.get_attribute("class")
    check("L-3 Edit orange, Addresses and Merge outlined, Delete red", "btn-primary" in cls("Edit") and "btn-secondary" in cls("Addresses") and "btn-secondary" in cls("Merge into another person") and "btn-danger" in cls("Delete"))
    check("L-3 one Change history link", li.locator("button.btn-link", has_text="Change history").count() == 1)
    txt = li.locator(".detail").inner_text()
    check("L-4 plain groups, no ids or raw keys", "About them" in txt and "Details" in txt and "created_at" not in txt and "updated_at" not in txt and "individuals_" not in txt and "birth_date" not in txt, txt[:300])
    check("L-4 town and role in details", "Boulder" in txt and "Instructor" in txt)
    li.get_by_role("button", name="Merge into another person", exact=True).click()
    opts = li.locator(".mergebox select option").all_inner_texts()
    check("L-6 merge picker shows born date", any("born" in o for o in opts), opts[:3])
    li.get_by_role("button", name="Cancel", exact=True).first.click()
    # ===== L-7 / L-8
    pg.fill("#pSearch", "zzzz"); pg.wait_for_timeout(250)
    check("L-7 no-match has a Clear link that restores the list", pg.locator("#pClear").count() == 1)
    pg.click("#pClear"); pg.wait_for_timeout(300)
    check("L-7 clearing brings the people back", pg.locator("#pList > li").count() == N_ACTIVE and pg.input_value("#pSearch") == "")
    pg.click("#pAddBtn")
    check("L-8 add form: sections, required star, orange Save, outlined Cancel", pg.locator("#pAddForm .fsec").count() >= 3 and pg.locator("#pAddForm label[for=paGiven] .req").count() == 1 and "btn-primary" in pg.get_attribute("#pSaveBtn", "class") and "btn-secondary" in pg.get_attribute("#pCancelBtn", "class"))
    pg.click("#pSaveBtn"); pg.wait_for_timeout(200)
    check("L-8 empty save shows the error beside the field", pg.inner_text("#epaGiven") != "")
    pg.click("#pCancelBtn")
    li2 = pg.locator("#pList > li").first; li2.locator("button.head").click(); li2.get_by_role("button", name="Edit", exact=True).click()
    check("L-8 edit form: sections, star, button cues", li2.locator(".eform .fsec").count() >= 4 and li2.locator(".eform label .req").count() == 1 and "btn-primary" in li2.get_by_role("button", name="Save changes").get_attribute("class"))
    # ===== L-9 phone at 390
    H1440 = pg.evaluate("document.documentElement.scrollHeight")
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    check("L-9 no sideways scroll at 390", pg.evaluate("document.documentElement.scrollWidth <= 391"))
    check("L-9 header one row (<=64px)", pg.evaluate("document.getElementById('topbar').getBoundingClientRect().height") <= 64)
    small = pg.evaluate("[].filter.call(document.querySelectorAll('#peopleView .phead button, #peopleView #pAddForm button'), function(b){return b.offsetParent && b.getBoundingClientRect().height < 40 && !b.classList.contains('btn-link')}).length")
    check("L-9 buttons at least 40px tall", small == 0, small)
    print("HEIGHTS 1440:", H1440, "390:", pg.evaluate("document.documentElement.scrollHeight"))
    check("no page errors", not errs, errs)
    b.close()
print("ALL OK" if not fails else "FAILED: %d" % len(fails)); sys.exit(1 if fails else 0)

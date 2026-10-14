#!/usr/bin/env python3
"""Browser test for the lean private request: name + email + (optional) curriculum + consent is enough; 'Add details now' holds the rest;
unanswered questions are never sent; the Console shows 'Interested in: <title>'. Headless Chromium, in-memory store, nothing touches Firebase.
Run from enjoy_router/:  python3 run_curriculum_pick_browser_test.py"""
import sys, json, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import attendances_service as AT
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

FORM = (HERE.parent / "enjoy" / "register" / "private" / "index.html").as_uri()
GROUP = (HERE.parent / "enjoy" / "register" / "group" / "index.html").as_uri()
CONSOLE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)

CUR1 = "a1b2c3d4-0000-4000-8000-000000000201"; CUR2 = "a1b2c3d4-0000-4000-8000-000000000202"
NOW = "2026-10-10T12:00:00Z"
for cid, slug, title in ((CUR1, "start_here", "Start here with AI"), (CUR2, "photos", "Photos and memories")):
    store.create("curriculums", cid, {"id": cid, "slug": slug, "title": title, "status": "active", "session_count": 1, "minutes_per_session": 120, "created_at": NOW, "updated_at": NOW})
REQ = {"id": "11111111-1111-4111-8111-111111111111", "confirmation_number": "ICDT-AAAAAA", "registration_type": "private",
       "created_at": NOW, "first_name": "Chuck", "last_name": "Norris", "email": "chuck@example.com", "processing_status": "not_processed", "curriculum_id": CUR2}
store.create(AT.REQUESTS.name, REQ["id"], dict(REQ))
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
LIST = {"ok": True, "data": {"curriculums": [{"id": CUR1, "title": "Start here with AI"}, {"id": CUR2, "title": "Photos and memories"}]}}
def admin_route(route):
    req = route.request
    if req.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    sent = []
    def reg_route(route):
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=201, headers=CORS, body=json.dumps({"ok": True, "data": {"confirmation_number": "ICDT-TESTZZ", "registration_type": "private"}}))
    def page(url, curr=LIST, errs=None, width=420):
        pg = b.new_page(viewport={"width": width, "height": 1000})
        if errs is not None: pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/enjoy_public_venues*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": []}})))
        if curr is None: pg.route("**/enjoy_public_curriculums*", lambda r: r.abort())
        else: pg.route("**/enjoy_public_curriculums*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps(curr)))
        pg.route(re.compile(r"enjoy-registration-request"), reg_route)
        pg.goto(url); return pg
    def basics(pg):
        pg.fill("input[name=first_name]", "Pat"); pg.fill("input[name=last_name]", "Lee"); pg.fill("input[name=email]", "pat+test3@example.com")
        pg.check("input[name=consent_to_contact]", force=True)
    def send(pg):
        pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")

    # ---- the small ask
    errs = []; pg = page(FORM, errs=errs)
    pg.wait_for_selector("select[name=curriculum_id] option[value]:not([value=''])", state="attached")
    opts = pg.eval_on_selector_all("select[name=curriculum_id] option", "els => els.map(e => e.textContent)")
    check("the dropdown starts 'Not sure yet / any' then lists active curriculums by title", opts == ["Not sure yet / any", "Start here with AI", "Photos and memories"], opts)
    check("the dropdown is visible at the top", pg.locator("select[name=curriculum_id]").is_visible())
    need = pg.locator("#rf-need li").all_inner_texts()
    check("the checklist has three items: name, email, OK to contact", len(need) == 3, need)
    check("the details section is closed and called 'Add details now'", pg.evaluate("document.querySelector('details.rf__more').open") is False and "Add details now" in pg.inner_text("details.rf__more summary"))
    check("count, minors and where are not in the top block", pg.locator("section, fieldset").first.locator("input[name=attendee_count]").count() == 0 or not pg.locator("input[name=attendee_count]").is_visible())
    basics(pg); send(pg)
    keys = set(sent[0].keys()) if sent else set()
    check("name + email + consent alone sends successfully", len(sent) == 1)
    check("nothing unanswered is sent (no count, no minors answer, no attending answer, no venue)", not ({"attendee_count", "has_minors_present", "is_requester_attending", "curriculum_id", "location_type", "preferred_venue_id"} & keys), sorted(keys))
    # ---- a curriculum pick
    sent.clear(); pg = page(FORM, errs=errs); pg.wait_for_selector("select[name=curriculum_id] option[value]:not([value=''])", state="attached")
    basics(pg); pg.select_option("select[name=curriculum_id]", CUR1); send(pg)
    check("a curriculum pick sends curriculum_id", sent and sent[0].get("curriculum_id") == CUR1, sent)
    # ---- details filled in
    sent.clear(); pg = page(FORM, errs=errs); pg.wait_for_selector("select[name=curriculum_id] option[value]:not([value=''])", state="attached")
    basics(pg); pg.click("details.rf__more summary")
    pg.check("input[name=is_requester_attending][value=yes]", force=True); pg.fill("input[name=attendee_count]", "2"); pg.check("input[name=has_minors_present][value=no]", force=True)
    send(pg)
    s0 = sent[0] if sent else {}
    check("details given are sent as given", s0.get("attendee_count") == 2 and s0.get("is_requester_attending") is True and s0.get("has_minors_present") is False, s0)
    # ---- a teen listed forces minors
    sent.clear(); pg = page(FORM, errs=errs); basics(pg); pg.click("details.rf__more summary")
    pg.click("text=+ Add a person"); pg.locator(".rf__person-body input").first.fill("Kid"); pg.locator(".rf__person-body select").first.select_option("teen")
    pg.get_by_role("button", name="Done").click(); send(pg)
    check("listing a teen sends has_minors_present true", sent and sent[0].get("has_minors_present") is True and sent[0]["participants"][0]["age_band"] == "teen", sent)
    # ---- list fails
    sent.clear(); pg = page(FORM, curr=None, errs=errs); pg.wait_for_timeout(800)
    check("an unreachable curriculum list hides the dropdown", not pg.locator("select[name=curriculum_id]").is_visible())
    basics(pg); send(pg)
    check("the form still sends without it", len(sent) == 1 and "curriculum_id" not in sent[0])
    sent.clear(); pg = page(FORM, curr={"ok": True, "data": {"curriculums": []}}, errs=errs); pg.wait_for_timeout(800)
    check("an empty list hides the dropdown", not pg.locator("select[name=curriculum_id]").is_visible())
    # ---- group is unchanged
    gp = page(GROUP, errs=errs); gp.wait_for_timeout(500)
    check("the group page keeps its required count, no dropdown", gp.locator("input[name=attendee_count]").is_visible() and gp.locator("select[name=curriculum_id]").count() == 0)
    gneed = gp.locator("#rf-need li").all_inner_texts()
    check("the group checklist keeps its longer list", len(gneed) == 7, gneed)
    check("no script errors on the forms", not errs, errs)

    # ---- the Console
    c = b.new_page(viewport={"width": 420, "height": 900}); cerr = []
    c.on("pageerror", lambda e: cerr.append(str(e)))
    c.route("**/enjoy_admin", admin_route)
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": [REQ]}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    c.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    c.goto(CONSOLE); c.fill("#keyInput", KEY); c.click("#unlockBtn")
    c.wait_for_selector("#homeView:not([hidden])")
    c.select_option("#collPick", "requests") if c.locator("#collPick option[value=requests]").count() else None
    c.wait_for_selector("#list li", state="attached")
    li = c.locator("#list li", has_text="Chuck Norris")
    c.wait_for_function("document.querySelector('.curchip') && document.querySelector('.curchip').textContent.indexOf('Photos and memories') >= 0", timeout=8000)
    check("the card shows 'Interested in:' with the real title", "Interested in: Photos and memories" in li.inner_text(), li.inner_text())
    check("the card does not claim a head count it never got", "People: —" in li.inner_text(), li.inner_text())
    li.locator("button.head").click(); li.get_by_role("button", name="Put in a class…").click()
    c.wait_for_selector(".putbox select[id$='_cls']")
    li.locator("select[id$='_cls']").select_option(label="+ A new class (build it now)")
    check("building a class starts from the curriculum asked for", li.locator("select[id$='n_cur']").input_value() == CUR2, li.locator("select[id$='n_cur']").input_value())
    check("a hint says who chose it", "Chosen by the requester" in li.locator(".putbox").inner_text())
    check("no script errors in the Console", not cerr, cerr)
    b.close()

print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all curriculum-pick browser checks pass")); sys.exit(1 if fails else 0)

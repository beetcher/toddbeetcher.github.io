#!/usr/bin/env python3
"""Browser test for the venue pick: the public form shows 'At a home', 'A public place' and 'Name, Town' venues, falls back to the
two plain choices when the list fails, and sends preferred_venue_id; the Console shows the venue asked for and pre-selects it when
building the class. Headless Chromium, in-memory store, nothing touches Firebase.
Run from enjoy_router/:  python3 run_venue_pick_browser_test.py"""
import sys, json, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import venues_service as VS
from crud import attendances_service as AT
from crud_endpoint import handle_admin, make_failure_limiter
from public_venues import public_list
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

FORM = (HERE.parent / "enjoy" / "register" / "private" / "index.html").as_uri()
CONSOLE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)

A = "user:admin"
def venue(name, slug, town, public=True, active=True):
    r = VS.create_with_place(store, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": public}, A,
                             address={"street": "1 Main St", "locality": town, "region": "CO", "postal_code": "80027", "country": "US"})
    assert r.ok, r.problems
    if active: assert VS.update(store, r.data["id"], {"status": "active"}, A).ok
    return r.data
lib = venue("Louisville Library", "lou_lib", "Louisville"); hall = venue("Boulder Hall", "bou_hall", "Boulder"); venue("Private Den", "den", "Boulder", public=False)
LIST = public_list(store)
REQ = {"id": "11111111-1111-4111-8111-111111111111", "confirmation_number": "ICDT-AAAAAA", "registration_type": "private", "attendee_count": 1,
       "created_at": "2026-10-10T12:00:00Z", "first_name": "Chuck", "last_name": "Norris", "email": "chuck@example.com", "processing_status": "not_processed",
       "location_type": "off_site", "preferred_venue_id": lib["id"]}
REQ2 = {**REQ, "id": "22222222-2222-4222-8222-222222222222", "confirmation_number": "ICDT-BBBBBB", "first_name": "Dana", "last_name": "Fox", "email": "dana@example.com", "preferred_venue_id": hall["id"]}
store.create(AT.REQUESTS.name, REQ["id"], dict(REQ)); store.create(AT.REQUESTS.name, REQ2["id"], dict(REQ2))
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}

def admin_route(route):
    req = route.request
    if req.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    # ---------- the public form ----------
    sent = []
    def reg_route(route):
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=201, headers=CORS, body=json.dumps({"ok": True, "data": {"confirmation_number": "ICDT-TESTZZ", "registration_type": "private"}}))
    def fill_form(pg):
        pg.fill("input[name=first_name]", "Pat"); pg.fill("input[name=last_name]", "Lee"); pg.fill("input[name=email]", "pat@example.com")
        pg.check("input[name=is_requester_attending][value=yes]", force=True); pg.fill("input[name=attendee_count]", "1")
        pg.check("input[name=has_minors_present][value=no]", force=True)
        pg.check("input[name=consent_to_contact]", force=True)
    pg = b.new_page(viewport={"width": 1280, "height": 1000}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_public_venues", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": LIST}})))
    pg.route(re.compile(r"enjoy-registration-request"), reg_route)
    pg.goto(FORM)
    pg.wait_for_selector("input[name=location_type][value^='venue:']", state="attached")
    labels = pg.eval_on_selector_all("input[name=location_type]", "els => els.map(e => e.parentElement.textContent.trim())")
    check("order: home, public place, then venues as 'Name, Town'", len(labels) == 4 and labels[0] == "At a home" and labels[1].startswith("A public place")
          and labels[2:] == ["Boulder Hall, Boulder", "Louisville Library, Louisville"], labels)
    check("a private venue is not offered", not any("Den" in l for l in labels))
    fill_form(pg); pg.check("input[name=location_type][value^='venue:'] >> nth=1", force=True)
    pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("a venue pick sends off_site and the venue id", sent and sent[0].get("location_type") == "off_site" and sent[0].get("preferred_venue_id") == lib["id"], sent)
    check("no other venue fields sent", sent and "venue:" not in json.dumps(sent[0]))
    # plain choices send no venue id
    sent.clear(); pg2 = b.new_page(viewport={"width": 1280, "height": 1000})
    pg2.route("**/enjoy_public_venues", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": LIST}})))
    pg2.route(re.compile(r"enjoy-registration-request"), reg_route); pg2.goto(FORM)
    pg2.wait_for_selector("input[name=location_type][value^='venue:']", state="attached")
    fill_form(pg2); pg2.check("input[name=location_type][value=off_site]", force=True)
    pg2.click("button[type=submit]"); pg2.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("'A public place' sends off_site only", sent and sent[0].get("location_type") == "off_site" and "preferred_venue_id" not in sent[0], sent)
    # list fails: two plain choices
    pg3 = b.new_page(viewport={"width": 420, "height": 900})
    pg3.route("**/enjoy_public_venues", lambda r: r.fulfill(status=500, headers=CORS, body="{}")); pg3.goto(FORM); pg3.wait_for_timeout(800)
    check("a failed list leaves the two plain choices", pg3.locator("input[name=location_type]").count() == 2)
    pg4 = b.new_page(viewport={"width": 420, "height": 900})
    pg4.route("**/enjoy_public_venues", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": []}}))); pg4.goto(FORM); pg4.wait_for_timeout(800)
    check("an empty list leaves the two plain choices", pg4.locator("input[name=location_type]").count() == 2)
    pg5 = b.new_page(viewport={"width": 420, "height": 900}); pg5.route("**/enjoy_public_venues", lambda r: r.abort()); pg5.goto(FORM); pg5.wait_for_timeout(800)
    check("an unreachable list leaves the two plain choices", pg5.locator("input[name=location_type]").count() == 2)
    check("no script errors on the form", not errors, errors)

    # ---------- the Console ----------
    c = b.new_page(viewport={"width": 420, "height": 900}); cerr = []
    c.on("pageerror", lambda e: cerr.append(str(e)))
    c.route("**/enjoy_admin", admin_route)
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": [REQ, REQ2]}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    c.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    c.goto(CONSOLE); c.fill("#keyInput", KEY); c.click("#unlockBtn")
    c.wait_for_selector("#homeView:not([hidden])")
    c.select_option("#collPick", "requests") if c.locator("#collPick option[value=requests]").count() else None
    c.wait_for_selector("#list li", state="attached")
    li = c.locator("#list li", has_text="Chuck Norris")
    check("the card shows the venue asked for", "Venue asked for" in li.inner_text(), li.inner_text())
    li.locator("button.head").click()
    li.get_by_role("button", name="Put in a class…").click()
    c.wait_for_selector(".putbox select[id$='_cls']")
    check("the Put in a class box names the venue asked for", "Louisville Library, Louisville" in li.locator(".putbox").inner_text(), li.locator(".putbox").inner_text())
    li.locator("select[id$='_cls']").select_option(label="A new class (build it now)")
    sel = li.locator("select[id$='n_ven']")
    check("the build step has the requested venue selected", sel.input_value() == lib["id"], sel.input_value())
    check("a hint says who chose it", "Chosen by the requester" in li.locator(".putbox").inner_text())
    sel.select_option(hall["id"])
    check("the operator can change it", sel.input_value() == hall["id"])
    check("no script errors in the Console", not cerr, cerr)
    b.close()

print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all venue-pick browser checks pass")); sys.exit(1 if fails else 0)

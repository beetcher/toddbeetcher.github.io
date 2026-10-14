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
REQ_ZIP = "80027"
REQ = {"id": "11111111-1111-4111-8111-111111111111", "confirmation_number": "ICDT-AAAAAA", "registration_type": "private", "attendee_count": 1,
       "created_at": "2026-10-10T12:00:00Z", "first_name": "Chuck", "last_name": "Norris", "email": "chuck@example.com", "processing_status": "not_processed",
       "location_type": "off_site", "preferred_venue_id": lib["id"], "postal_code": "80027"}
REQ2 = {**REQ, "id": "22222222-2222-4222-8222-222222222222", "confirmation_number": "ICDT-BBBBBB", "first_name": "Dana", "last_name": "Fox", "email": "dana@example.com", "preferred_venue_id": hall["id"]}
store.create(AT.REQUESTS.name, REQ["id"], dict(REQ)); store.create(AT.REQUESTS.name, REQ2["id"], dict(REQ2))
def OPEN(pg):   # the optional details sit in a closed section; these tests are about what is inside it
    pg.add_init_script("document.addEventListener('DOMContentLoaded', function () { var d = document.querySelector('details.rf__more'); if (d) d.open = true; })")
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
    def venues_route(route):
        m = re.search(r"[?&]zip=(\d+)", route.request.url)
        route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": public_list(store, m.group(1) if m else None)}}))
    pg = b.new_page(viewport={"width": 1280, "height": 1000}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_public_venues", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": LIST}})))
    pg.route(re.compile(r"enjoy-registration-request"), reg_route)
    OPEN(pg); pg.goto(FORM)
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
    pg2.route(re.compile(r"enjoy-registration-request"), reg_route); OPEN(pg2); pg2.goto(FORM)
    pg2.wait_for_selector("input[name=location_type][value^='venue:']", state="attached")
    fill_form(pg2); pg2.check("input[name=location_type][value=off_site]", force=True)
    pg2.click("button[type=submit]"); pg2.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("'A public place' sends off_site only", sent and sent[0].get("location_type") == "off_site" and "preferred_venue_id" not in sent[0], sent)
    # list fails: two plain choices
    pg3 = b.new_page(viewport={"width": 420, "height": 900})
    pg3.route("**/enjoy_public_venues", lambda r: r.fulfill(status=500, headers=CORS, body="{}")); OPEN(pg3); pg3.goto(FORM); pg3.wait_for_timeout(800)
    check("a failed list leaves the two plain choices", pg3.locator("input[name=location_type]").count() == 2)
    pg4 = b.new_page(viewport={"width": 420, "height": 900})
    pg4.route("**/enjoy_public_venues", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": []}}))); OPEN(pg4); pg4.goto(FORM); pg4.wait_for_timeout(800)
    check("an empty list leaves the two plain choices", pg4.locator("input[name=location_type]").count() == 2)
    pg5 = b.new_page(viewport={"width": 420, "height": 900}); pg5.route("**/enjoy_public_venues", lambda r: r.abort()); OPEN(pg5); pg5.goto(FORM); pg5.wait_for_timeout(800)
    check("an unreachable list leaves the two plain choices", pg5.locator("input[name=location_type]").count() == 2)
    check("no script errors on the form", not errors, errors)

    # ---------- ZIP: five closest plus a dropdown, and the device memory ----------
    for nm_, tn, z in (("Denver Hall", "Denver", "80202"), ("Golden Hall", "Golden", "80401"), ("Longmont Hall", "Longmont", "80501"), ("Pueblo Hall", "Pueblo", "81003"), ("Durango Hall", "Durango", "81301")):
        venue(nm_, nm_.lower().replace(" ", "_"), tn)
    # (the helper puts every venue in the town named, but the ZIP is fixed at 80027 for all; give these their own ZIP centres)
    from crud import locations_crud as LC, location_links_crud as LK
    Z = {"Denver Hall": "80202", "Golden Hall": "80401", "Longmont Hall": "80501", "Pueblo Hall": "81003", "Durango Hall": "81301", "Louisville Library": "80027", "Boulder Hall": "80301"}
    for v in VS.list(store, {"status": "active"}).data["records"]:
        pv = VS._place_view(store, v["id"])
        if pv and v["name"] in Z:
            addr = dict(pv["address"]); addr["postal_code"] = Z[v["name"]]
            assert LC.update(store, pv["location_id"], {"addresses": [addr]}, A).ok
    z1 = b.new_context(viewport={"width": 1280, "height": 1000})
    zp = z1.new_page(); zerr = []
    zp.on("pageerror", lambda e: zerr.append(str(e)))
    zp.route("**/enjoy_public_venues*", venues_route); zp.route(re.compile(r"enjoy-registration-request"), reg_route)
    OPEN(zp); zp.goto(FORM)
    zp.wait_for_selector("select[aria-label^='Choose a place']", state="attached")
    check("no ZIP, seven venues: only home, public place and one dropdown", zp.locator("input[name=location_type]:visible").count() == 2 and zp.locator("select[aria-label^='Choose a place'] option").count() == 8, zp.locator("select[aria-label^='Choose a place'] option").count())
    check("the ZIP field starts empty on a first visit", zp.input_value("input[name=postal_code]") == "")
    zp.fill("input[name=postal_code]", "80027")
    zp.wait_for_selector("select[aria-label^='More places']", state="attached")
    shown = zp.eval_on_selector_all("input[name=location_type]", "els => els.filter(e => !e.parentElement.hidden).map(e => e.parentElement.textContent.trim())")
    check("with a ZIP: home, public place, then the 5 nearest with miles", len(shown) == 7 and shown[2].startswith("Louisville Library, Louisville (") and "mile" in shown[2], shown)
    check("nearest first", shown[2].startswith("Louisville") and shown[3].startswith("Boulder"), shown)
    opts = zp.eval_on_selector_all("select[aria-label^='More places'] option", "els => els.map(o => o.textContent)")
    check("the rest sit in a More places dropdown, nearest first, farthest last", opts[0] == "More places…" and len(opts) == 3 and opts[-1].startswith("Durango Hall"), opts)
    zp.select_option("select[aria-label^='More places']", index=2)
    check("choosing from the dropdown picks that venue", zp.eval_on_selector("input[name=location_type]:checked", "e => e.value.indexOf('venue:') === 0"))
    zp.check("input[name=location_type]:visible >> nth=0", force=True)
    check("choosing a visible choice rests the dropdown", zp.input_value("select[aria-label^='More places']") == "")
    zp.select_option("select[aria-label^='More places']", index=1)
    fill_form(zp)
    zp.click("button[type=submit]"); zp.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("the request carries the ZIP and a venue from the dropdown", sent and sent[-1].get("postal_code") == "80027" and sent[-1].get("preferred_venue_id") and sent[-1].get("location_type") == "off_site", sent[-1:] )
    # a bad ZIP is stopped on the form
    zq = z1.new_page(); zq.route("**/enjoy_public_venues*", venues_route); zq.route(re.compile(r"enjoy-registration-request"), reg_route)
    OPEN(zq); zq.goto(FORM)
    check("the next visit remembers the ZIP on this device", zq.input_value("input[name=postal_code]") == "80027")
    zq.wait_for_selector("select[aria-label^='More places']", state="attached")
    check("and loads the nearby list straight away", "Louisville Library" in zq.eval_on_selector_all("input[name=location_type]", "els => els.filter(e => !e.parentElement.hidden).map(e => e.parentElement.textContent)")[2])
    zq.fill("input[name=postal_code]", "")
    zq.wait_for_selector("select[aria-label^='Choose a place']", state="attached")
    OPEN(zq); zq.goto(FORM)
    check("clearing the field forgets it", zq.input_value("input[name=postal_code]") == "")
    zr = z1.new_page(); zr.route("**/enjoy_public_venues*", venues_route); zr.route(re.compile(r"enjoy-registration-request"), reg_route); sent.clear()
    OPEN(zr); zr.goto(FORM); fill_form(zr); zr.check("input[name=location_type][value=home]", force=True); zr.fill("input[name=postal_code]", "90210")
    zr.click("button[type=submit]"); zr.wait_for_timeout(500)
    check("a ZIP outside Colorado is stopped on the form", not sent and "Colorado ZIP" in zr.locator("form").inner_text())
    zr.fill("input[name=postal_code]", "80301"); zr.click("button[type=submit]"); zr.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("a home request can carry a ZIP", sent and sent[-1].get("postal_code") == "80301" and "preferred_venue_id" not in sent[-1] and sent[-1].get("location_type") == "home", sent[-1:])
    # storage blocked: still works
    z2 = b.new_context(viewport={"width": 1280, "height": 1000}); z2.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } })")
    zs = z2.new_page(); serr = []; zs.on("pageerror", lambda e: serr.append(str(e))); zs.route("**/enjoy_public_venues*", venues_route); OPEN(zs); zs.goto(FORM)
    zs.fill("input[name=postal_code]", "80027"); zs.wait_for_selector("select[aria-label^='More places']", state="attached")
    check("blocked storage: the form still works", not serr and zs.locator("select[aria-label^='More places']").count() == 1, serr)
    check("no script errors in the ZIP pages", not zerr, zerr)

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
    c.wait_for_function("document.querySelector('.venuechip') && document.querySelector('.venuechip').textContent.indexOf('Louisville Library, Louisville') >= 0", timeout=8000)
    check("the card shows the venue's real name once the venues load", "Venue asked for: Louisville Library, Louisville" in li.inner_text(), li.inner_text())
    check("the card shows the ZIP", "ZIP: 80027" in li.inner_text(), li.inner_text())
    li.locator("button.head").click()
    li.get_by_role("button", name="Put in a class…").click()
    c.wait_for_selector(".putbox select[id$='_cls']")
    check("the Put in a class box names the venue asked for", "Louisville Library, Louisville" in li.locator(".putbox").inner_text(), li.locator(".putbox").inner_text())
    optinfo = li.locator("select[id$='_cls'] option", has_text="build it now").evaluate("o => ({text: o.textContent, color: o.style.color, weight: o.style.fontWeight})")
    check("the new-class option starts with + and is green and bold", optinfo["text"].startswith("+ ") and optinfo["color"] != "" and optinfo["weight"] == "700", optinfo)
    li.locator("select[id$='_cls']").select_option(label="+ A new class (build it now)")
    check("choosing it outlines the Class box in green", "buildnew" in (li.locator("select[id$='_cls']").get_attribute("class") or ""))
    sel = li.locator("select[id$='n_ven']")
    check("the build step has the requested venue selected", sel.input_value() == lib["id"], sel.input_value())
    check("a hint says who chose it", "Chosen by the requester" in li.locator(".putbox").inner_text())
    sel.select_option(hall["id"])
    check("the operator can change it", sel.input_value() == hall["id"])
    check("no script errors in the Console", not cerr, cerr)
    # ---------- GPS in the Venues station ----------
    from crud import geocoder
    geocoder.lookup = lambda a: None if a.get("locality") == "Boulder" else (40.0, -105.0)
    c.select_option("#collPick", "venues"); c.wait_for_selector("#vList li")
    check("venues without GPS say so", "No GPS" in c.locator("#vList li", has_text="Louisville Library").inner_text())
    row = c.locator("#vList li", has_text="Louisville Library"); row.locator("button.head").click()
    check("a public venue has a Find GPS button, a private one does not", row.get_by_role("button", name="Find GPS").count() == 1 and c.locator("#vList li", has_text="Private Den").get_by_role("button", name="Find GPS").count() == 0)
    row.get_by_role("button", name="Find GPS").click()
    c.wait_for_function("document.getElementById('vNotice').textContent.indexOf('GPS found') >= 0")
    check("Find GPS saves a point and says so", "GPS found and saved" in c.locator("#vNotice").inner_text())
    c.wait_for_function("Array.from(document.querySelectorAll('#vList li')).some(l => l.textContent.indexOf('Louisville Library') >= 0 && l.textContent.indexOf('GPS: looked up') >= 0)")
    check("the card now says GPS: looked up", True)
    c.click("#vGps")
    c.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Checked') === 0", timeout=15000)
    note = c.locator("#vNotice").inner_text()
    check("Find missing GPS reports found / not found counts", "not found by the lookup" in note and "Checked" in note, note)
    check("a lookup that finds nothing leaves the venue without GPS", "No GPS" in c.locator("#vList li", has_text="Boulder Hall").inner_text())
    geocoder.lookup = None
    check("no script errors in the Venues station", not cerr, cerr)
    b.close()

print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all venue-pick browser checks pass")); sys.exit(1 if fails else 0)

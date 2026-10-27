#!/usr/bin/env python3
"""Browser test: the ZIP sits in the open top block of the private form (optional, not in the checklist, friendlier message for a
non-Colorado ZIP); the Console's Build the class lists venues nearest first to the request's ZIP and fills in the nearest public
place unless the requester picked one or chose a home. Headless Chromium, in-memory store, nothing touches Firebase.
Run from enjoy_router/:  python3 run_venue_rank_browser_test.py"""
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
def venue(name, slug, zip_code, public=True):
    r = VS.create_with_place(store, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": public}, A,
                             address={"street": "1 Main St", "locality": "Town", "region": "CO", "postal_code": zip_code, "country": "US"})
    assert r.ok, r.problems
    assert VS.update(store, r.data["id"], {"status": "active"}, A).ok
    return r.data
aa = venue("Aardvark Den", "aard", "80202", public=False)     # Denver, private: first alphabetically
bou = venue("Boulder Hall", "bou", "80301")
lou = venue("Louisville Library", "lou", "80027")
dur = venue("Durango Hall", "dur", "81301")
store.create("discovery_areas", "r-front", {"id": "r-front", "kind": "region", "name": "Front Range", "state_code": "CO", "is_active": True, "schema_version": 1,
                                          "zip_codes": ["80202", "80301", "80027"]})   # Durango (81301) is outside this region
NOW = "2026-10-14T12:00:00Z"
def req(i, conf, first, **kw):
    r = {"id": f"{i}{i}{i}{i}{i}{i}{i}{i}-1111-4111-8111-111111111111", "confirmation_number": conf, "registration_type": "private", "created_at": NOW,
         "first_name": first, "last_name": "Test", "email": f"{first.lower()}@example.com", "processing_status": "not_processed", **kw}
    store.create(AT.REQUESTS.name, r["id"], dict(r)); return r
R1 = req(1, "ICDT-ZIP001", "Zipper", postal_code="80027", location_type="off_site")     # ZIP, no venue picked
R2 = req(2, "ICDT-HOME02", "Homer", postal_code="80027", location_type="home")          # chose home
R3 = req(3, "ICDT-PICK03", "Picker", postal_code="80027", location_type="off_site", preferred_venue_id=dur["id"])
R5 = req(5, "ICDT-OUT005", "Outsider", postal_code="81301", location_type="off_site")      # ZIP in no served region
R4 = req(4, "ICDT-NOZIP4", "Nozip")                                                     # no ZIP
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    r_ = route.request
    if r_.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(r_.method, r_.headers.get("authorization", ""), (r_.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    # ---- the form
    sent = []; errs = []
    def reg_route(route):
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=201, headers=CORS, body=json.dumps({"ok": True, "data": {"confirmation_number": "ICDT-TESTZZ", "registration_type": "private"}}))
    pg = b.new_page(viewport={"width": 420, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_public_venues*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": public_list(store)}})))
    pg.route("**/enjoy_public_curriculums*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"curriculums": []}})))
    pg.route(re.compile(r"enjoy-registration-request"), reg_route); pg.goto(FORM)
    z = pg.locator("input[name=postal_code]")
    check("the ZIP field is visible in the open top block", z.is_visible() and pg.evaluate("document.querySelector('details.rf__more').open") is False)
    check("the ZIP field sits above the closed details section", pg.evaluate("document.querySelector('input[name=postal_code]').compareDocumentPosition(document.querySelector('details.rf__more')) & Node.DOCUMENT_POSITION_FOLLOWING") > 0)
    lab = pg.locator("#rf .rf__field", has=z).inner_text()
    check("it explains why, and is not marked required", "find a place near you" in lab and "optional" not in lab.split("\n")[0].lower(), lab)
    check("the checklist still has three items", len(pg.locator("#rf-need li").all_inner_texts()) == 3)
    pg.fill("input[name=first_name]", "Pat"); pg.fill("input[name=last_name]", "Lee"); pg.fill("input[name=email]", "pat@example.com"); pg.check("input[name=consent_to_contact]", force=True)
    pg.fill("input[name=postal_code]", "9021"); pg.click("button[type=submit]"); pg.wait_for_timeout(400)
    msg = pg.locator("#rf").inner_text()
    check("a ZIP that is not five digits is stopped with a plain message", not sent and "five-digit ZIP" in msg and "Colorado" not in msg, msg[-300:])
    pg.fill("input[name=postal_code]", "90210"); pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("a ZIP in another state from the top block is sent", sent and sent[0].get("postal_code") == "90210", sent)
    check("no script errors on the form", not errs, errs)

    # ---- the Console
    c = b.new_page(viewport={"width": 420, "height": 900}); cerr = []
    c.on("pageerror", lambda e: cerr.append(str(e)))
    c.route("**/enjoy_admin", admin_route)
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": [R1, R2, R3, R4, R5]}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    c.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    c.goto(CONSOLE); c.fill("#keyInput", KEY); c.click("#unlockBtn"); c.wait_for_selector("#homeView:not([hidden])")
    c.select_option("#collPick", "requests") if c.locator("#collPick option[value=requests]").count() else None
    c.wait_for_selector("#list li", state="attached")
    def build(name):
        li = c.locator("#list li", has_text=name)
        li.locator("button.head").click(); li.get_by_role("button", name="Put in a class…").click()
        c.wait_for_selector(".putbox select[id$='_cls']", state="attached")
        li.locator("select[id$='_cls']").select_option(label="+ A new class (build it now)")
        return li
    def wait(fn, ms=8000):
        for _ in range(ms // 100):
            if fn(): return True
            c.wait_for_timeout(100)
        return False
    def ven_of(li): return li.locator("select[id$='n_ven']")
    li = build("Zipper")
    wait(lambda: ven_of(li).input_value() != "")
    labels = ven_of(li).locator("option").all_inner_texts()
    check("with a ZIP the venue list is nearest first, with distances", labels[0] == "Not chosen yet" and labels[1].startswith("Louisville Library") and labels[2].startswith("Boulder Hall") and "mile" in labels[1], labels)
    check("P-92: only venues in the request's region are offered (Durango is outside it)", not any(l.startswith("Durango") for l in labels) and len(labels) == 4, labels)
    check("a private venue is still in the operator list", any(l.startswith("Aardvark Den") for l in labels), labels)
    check("the nearest PUBLIC place is filled in (not the nearer private one)", ven_of(li).input_value() == lou["id"], ven_of(li).input_value())
    check("a hint says it was chosen by distance", "Nearest public place to ZIP 80027" in li.locator(".putbox").inner_text())
    li = build("Homer")
    wait(lambda: "mile" in " ".join(ven_of(li).locator("option").all_inner_texts()))
    c.wait_for_timeout(300)
    check("a home request: ranked, but nothing is filled in", "mile" in " ".join(ven_of(li).locator("option").all_inner_texts()) and ven_of(li).input_value() == "", ven_of(li).input_value())
    li = build("Picker")
    wait(lambda: "mile" in " ".join(ven_of(li).locator("option").all_inner_texts()))
    c.wait_for_timeout(300)
    check("a requester's own venue pick is kept", ven_of(li).input_value() == dur["id"], ven_of(li).input_value())
    li = build("Outsider")
    wait(lambda: "mile" in " ".join(ven_of(li).locator("option").all_inner_texts()))
    labels = ven_of(li).locator("option").all_inner_texts()
    check("P-92: a ZIP in no served region is not limited (all venues, nearest first)", len(labels) == 5 and labels[1].startswith("Durango"), labels)
    li = build("Nozip"); c.wait_for_timeout(800)
    labels = ven_of(li).locator("option").all_inner_texts()
    check("no ZIP: alphabetical, no distances, nothing filled in", labels[1].startswith("Aardvark") and not any("mile" in l for l in labels) and ven_of(li).input_value() == "", labels)
    check("no script errors in the Console", not cerr, cerr)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all venue-rank browser checks pass")); sys.exit(1 if fails else 0)

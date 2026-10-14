#!/usr/bin/env python3
"""Browser test: the lead-instructor box in the Console's Build the class lists only active instructor-roster people, filtered to the
state of the request's ZIP when there is one. Headless Chromium, in-memory store, nothing touches Firebase.
Run from enjoy_router/:  python3 run_instructor_pick_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_crud as I, instructor_rosters_service as INS, location_links_service as LKS, locations_crud as L, attendances_service as AT
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

CONSOLE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
A = "user:admin"
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)
def person(given, family): return I.create(store, {"given_name": given, "family_name": family}, A).data
def live_in(p, region):
    loc = L.create(store, {"name": p["given_name"] + " home", "addresses": [{"usage": "civic", "street_number": "1", "street": "Main St", "locality": "Town", "region": region, "postal_code": "80027", "country": "US"}]}, A).data
    assert LKS.create(store, {"subject_type": "individual", "subject_id": p["id"], "location_id": loc["id"], "relationship": "resides_at"}, A).ok
def roster(p, status="active"):
    r = INS.create(store, {"individual_id": p["id"], "status": status}, A); assert r.ok, r.problems; return r.data
colo, cali, nada, gone = person("Colo", "Rado"), person("Cali", "Fornia"), person("Nada", "Address"), person("Gone", "Inactive")
bobby = person("Bobby", "Hodgkins")           # a person, never an instructor
live_in(colo, "CO"); live_in(cali, "CA"); live_in(gone, "CO")
roster(colo); roster(cali); roster(nada); gone_r = roster(gone, "inactive")
NOW = "2026-10-14T12:00:00Z"
def req(i, conf, first, **kw):
    r = {"id": f"{i}{i}{i}{i}{i}{i}{i}{i}-1111-4111-8111-111111111111", "confirmation_number": conf, "registration_type": "private", "created_at": NOW,
         "first_name": first, "last_name": "Test", "email": f"{first.lower()}@example.com", "processing_status": "not_processed", **kw}
    store.create(AT.REQUESTS.name, r["id"], dict(r)); return r
R1 = req(1, "ICDT-ZIP001", "Zipper", postal_code="80027"); R2 = req(2, "ICDT-NOZIP2", "Nozip"); R3 = req(3, "ICDT-LAST03", "Lastone", postal_code="80027")
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
    c = b.new_page(viewport={"width": 420, "height": 900}); cerr = []
    c.on("pageerror", lambda e: cerr.append(str(e)))
    c.route("**/enjoy_admin", admin_route)
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": [R1, R2, R3]}})))
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
    def wait(fn, ms=6000):
        for _ in range(ms // 100):
            if fn(): return True
            c.wait_for_timeout(100)
        return False
    def box(li): return li.locator("div.addbox")
    def buttons(li):   # the instructor choices only: the buttons right after the instructor search box
        return box(li).locator("input[aria-label='Search instructors by name'] ~ div button").all_inner_texts()
    li = build("Zipper")
    wait(lambda: "Loading" not in box(li).inner_text())
    got = buttons(li)
    check("a Colorado ZIP: only the Colorado instructor shows", got == ["Colo Rado"], got)
    check("no non-instructor, no inactive instructor, no California, no one without an address", not any(x in " ".join(got) for x in ("Bobby", "Gone", "Cali", "Nada")), got)
    li2 = li
    box(li2).locator("input[aria-label='Search instructors by name']").fill("zzz")
    check("typing a name that matches nobody says so", "No instructor matches that name" in box(li2).inner_text())
    box(li2).locator("input[aria-label='Search instructors by name']").fill("col")
    check("typing narrows the list", buttons(li2) == ["Colo Rado"], buttons(li2))
    box(li2).locator("input[aria-label='Search instructors by name'] ~ div button").first.click()
    check("choosing one shows who was chosen", "Chosen: Colo Rado" in box(li2).inner_text())
    li = build("Nozip")
    wait(lambda: "Loading" not in box(li).inner_text())
    got = buttons(li)
    check("no ZIP: all active instructors, the one with no address is labelled", sorted(got) == ["Cali Fornia", "Colo Rado", "Nada Address (no address on file)"], got)
    check("still no non-instructor and no inactive instructor without a ZIP", not any(x in " ".join(got) for x in ("Bobby", "Gone")), got)
    # the only Colorado instructor goes inactive: the empty message
    r = INS.update(store, INS.list(store, {"individual_id": colo["id"]}).data["records"][0]["id"], {"status": "inactive"}, A); assert r.ok, r.problems
    li = build("Lastone")
    wait(lambda: "Loading" not in box(li).inner_text())
    txt = box(li).inner_text()
    check("no active Colorado instructor: a plain message and nothing to pick", "No active instructor lives in CO" in txt and "Instructors station" in txt and buttons(li) == [], txt[-300:])
    check("no script errors in the Console", not cerr, cerr)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all instructor-pick browser checks pass")); sys.exit(1 if fails else 0)

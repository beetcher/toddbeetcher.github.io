#!/usr/bin/env python3
"""P-92 part 2: the Edit form of a class lists only venues in the region of the class's current venue. Adapted from the Classes browser test.
(old docstring) Browser test for the Classes station (console/classes.js): the list, Add class, the Edit form, and the station's hooks (it is its own file, nothing of it is left
in console.js, leaving the page closes the edit form, sign-out empties it, signing back in loads it, the kit forwards to it). Drives the real Console page in headless
Chromium against the real admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when they are not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_classes_browser_test.py"""
import sys, json, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import scheduled_classes_crud as CL, venues_service as VS
from crud_endpoint import handle_admin, make_failure_limiter
from test_helpers import give_venue_zone
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
    r_ = route.request
    if r_.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(r_.method, r_.headers.get("authorization", ""), (r_.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
A = "user:admin"
v = VS.create_with_place(store, {"name": "Library", "slug": "library", "status": "inactive", "is_public_venue": True}, A,
                         address={"street": "951 Spruce St", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"})
assert v.ok, v.problems; give_venue_zone(store, v.data["id"], actor=A); assert VS.update(store, v.data["id"], {"status": "active"}, A).ok
base = {"class_type": "private", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 5, "capacity_max": 9}
sc = CL.create(store, {**base, "title": "Evening Basics", "slug": "eb", "status": "scheduled", "venue_id": v.data["id"], "starts_at": "2026-11-05T01:00:00Z",
                       "time_zone": "America/Denver", "duration_minutes": 60, "is_venue_confirmed": False}, A).data
idea = CL.create(store, {**base, "title": "Idea Session", "slug": "idea", "status": "identified"}, A).data

def mkv(name, slug, zip_code):
    r = VS.create_with_place(store, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": True}, A,
                             address={"street": slug + " Main St", "locality": "Town " + slug, "region": "CO", "postal_code": zip_code, "country": "US"})
    assert r.ok, r.problems; assert VS.update(store, r.data["id"], {"status": "active"}, A).ok
    return r.data
bou = mkv("Boulder Hall", "bou", "80301"); dur = mkv("Durango Hall", "dur", "81301"); nor = mkv("Nowhere Hall", "now", "99950")
store.create("discovery_areas", "r-front", {"id": "r-front", "kind": "region", "name": "Front Range", "state_code": "CO", "is_active": True, "schema_version": 1,
                                          "zip_codes": ["80027", "80301"]})
free = CL.create(store, {**base, "title": "Free Idea", "slug": "free", "status": "identified"}, A).data
far = CL.create(store, {**base, "title": "Far Class", "slug": "far", "status": "scheduled", "venue_id": nor["id"], "starts_at": "2026-11-05T01:00:00Z",
                        "time_zone": "America/Denver", "duration_minutes": 60, "is_venue_confirmed": False}, A).data
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 1100, "height": 1200}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    def venues_for(title):
        pg.locator("#cList li", has_text=title).get_by_role("button", name="Edit", exact=True).click()
        pg.wait_for_selector("#cEditPanel:not([hidden])"); pg.wait_for_selector("#ef_c_venue_id")
        return pg.eval_on_selector_all("#ef_c_venue_id option", "os => os.map(o => o.textContent)"), pg.inner_text("#cEditPanel")
    labels, panel = venues_for("Evening Basics")
    check("a class with a venue: only venues in that venue's region are listed", sorted(labels) == sorted(["Not chosen yet", "Library", "Boulder Hall"]), labels)
    check("a hint says why and what to do", "cancel this class" in panel, panel[-200:])
    pg.click("#cEditCancel") if pg.locator("#cEditCancel").count() else None
    labels, panel = venues_for("Free Idea")
    check("a class with no venue yet: every venue is listed", all(n in labels for n in ("Library", "Boulder Hall", "Durango Hall", "Nowhere Hall")), labels)
    pg.click("#cEditCancel") if pg.locator("#cEditCancel").count() else None
    labels, panel = venues_for("Far Class")
    check("a venue in no served region: every venue is listed (not locked in)", "Library" in labels and "Durango Hall" in labels, labels)
    check("no script errors", not errors, errors)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: class edit venue-region checks pass")); sys.exit(1 if fails else 0)

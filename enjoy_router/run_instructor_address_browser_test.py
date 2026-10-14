#!/usr/bin/env python3
"""Browser test: the Instructors station shows only an instructor's state and lets an operator add or replace the address write-only.
Headless Chromium, in-memory store, nothing touches Firebase.  Run from enjoy_router/:  python3 run_instructor_address_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import individuals_crud as I, instructor_rosters_service as INS, location_links_service as LKS, locations_crud as L
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
CONSOLE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
INS.R.needs_address = False   # setup makes grandfathered instructors; this test is about something else
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []; A = "user:admin"
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)
ann = I.create(store, {"given_name": "Ann", "family_name": "Noaddr"}, A).data
bo = I.create(store, {"given_name": "Bo", "family_name": "Hasaddr"}, A).data
oldloc = L.create(store, {"name": "Bo home", "addresses": [{"usage": "civic", "street_number": "9", "street": "Old Rd", "locality": "Denver", "region": "CO", "postal_code": "80202", "country": "US"}]}, A).data
oldlink = LKS.create(store, {"subject_type": "individual", "subject_id": bo["id"], "location_id": oldloc["id"], "relationship": "resides_at", "is_primary": True}, A).data
for pp in (ann, bo): assert INS.create(store, {"individual_id": pp["id"], "status": "active"}, A).ok
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
    c = b.new_page(viewport={"width": 420, "height": 1000}); cerr = []
    c.on("pageerror", lambda e: cerr.append(str(e)))
    c.route("**/enjoy_admin", admin_route)
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    c.goto(CONSOLE); c.fill("#keyInput", KEY); c.click("#unlockBtn"); c.wait_for_selector("#homeView:not([hidden])")
    c.select_option("#collPick", "instructors"); c.wait_for_selector("#instructorsView:not([hidden])"); c.wait_for_selector("#riList li")
    def li(name): return c.locator("#riList li", has_text=name)
    def open_(name):
        if "open" not in (li(name).get_attribute("class") or ""): li(name).locator("button.head").click()
    open_("Ann"); open_("Bo")
    check("no address: card says so", "Lives in: No address on file" in li("Ann").inner_text(), li("Ann").inner_text())
    check("has address: card shows the state only", "Lives in: CO" in li("Bo").inner_text() and "Old Rd" not in li("Bo").inner_text() and "80202" not in li("Bo").inner_text(), li("Bo").inner_text())
    check("button labels", li("Ann").get_by_role("button", name="Add address").count() == 1 and li("Bo").get_by_role("button", name="Replace address").count() == 1)
    li("Ann").get_by_role("button", name="Add address").click()
    li("Ann").get_by_role("button", name="Save address").click()
    check("empty form refuses", "needs a street" in li("Ann").inner_text() or "Enter a street" in li("Ann").inner_text() or "street" in li("Ann").inner_text().lower())
    f = li("Ann")
    f.get_by_label("Street address", exact=True).first.fill("5 Pine St"); f.get_by_label("City", exact=True).first.fill("Sacramento"); f.get_by_label("State", exact=True).first.fill("CA"); f.get_by_label("ZIP code", exact=True).first.fill("95814")
    f.get_by_role("button", name="Save address").click()
    c.wait_for_function("document.querySelector('#riNotice').innerText.includes('Saved the address for Ann')")
    c.wait_for_function("document.querySelector('#riList').textContent.includes('Lives in: CA')"); open_("Ann")
    check("after save: state CA shown, address not shown", "Lives in: CA" in li("Ann").inner_text() and "Pine" not in li("Ann").inner_text(), li("Ann").inner_text())
    open_("Bo"); li("Bo").get_by_role("button", name="Replace address").click()
    f = li("Bo")
    f.get_by_label("Street address", exact=True).first.fill("7 New Ave"); f.get_by_label("City", exact=True).first.fill("Reno"); f.get_by_label("State", exact=True).first.fill("NV"); f.get_by_label("ZIP code", exact=True).first.fill("89501")
    f.get_by_role("button", name="Save address").click()
    c.wait_for_function("document.querySelector('#riNotice').innerText.includes('Saved the address for Bo')")
    c.wait_for_function("document.querySelector('#riList').textContent.includes('Lives in: NV')"); open_("Bo")
    check("replace: new state shown", "Lives in: NV" in li("Bo").inner_text(), li("Bo").inner_text())
    links = [d for d in LKS.list(store, {"subject_id": bo["id"]}, limit=50).data["records"]]
    live = [d for d in links if d["status"] == "active"]
    check("old link ended, one live link", len(live) == 1 and any(d["id"] == oldlink["id"] and d["status"] == "ended" for d in links), [(d["id"][:6], d["status"]) for d in links])
    check("no script errors", not cerr, cerr)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all instructor-address browser checks pass")); sys.exit(1 if fails else 0)

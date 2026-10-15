#!/usr/bin/env python3
"""Browser test: Put in a class on a registration request places the requester AND everyone named on it, and says what each was sent. Fake mail transport, in-memory store, headless Chromium.
Run from enjoy_router/:  python3 run_participants_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
import smtp_transport as T
import comms, seed_comms
from launch_comms import wiring
from crud.memory_doc_store import MemoryDocStore
from crud import attendances_service as AT, individuals_service as IS, scheduled_classes_crud as CL, venues_service as VS
from crud_endpoint import handle_admin, make_failure_limiter
from test_helpers import give_address
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
sent, mode = [], ["accept"]
def fake(key, to, subject, body, html=None, attachments=None, headers=None):
    sent.append({"to": to, "body": body, "att": attachments})
    return T.SendResult(True, "accepted") if mode[0] == "accept" else T.SendResult(False, "recipient_rejected")
T.transport = fake
_need, _todo = seed_comms.plan(store); seed_comms.apply(store, _need, _todo)
class ON:   # switching the CMS on / off for the test
    @staticmethod
    def on(): comms.configure(wiring.build(store, lambda: "key", {"ICDT_COMMS_MODE": "live"}))
    @staticmethod
    def off(): comms.configure(None)
ON.on()
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
assert v.ok, v.problems; assert VS.update(store, v.data["id"], {"status": "active"}, A).ok
base = {"class_type": "private", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 5, "capacity_max": 9}
sc = CL.create(store, {**base, "title": "Evening Basics", "slug": "eb", "status": "scheduled", "venue_id": v.data["id"], "starts_at": "2026-11-05T01:00:00Z",
                       "time_zone": "America/Denver", "duration_minutes": 60, "is_venue_confirmed": False}, A).data
idea = CL.create(store, {**base, "title": "Idea Session", "slug": "idea", "status": "identified"}, A).data
def person(g, f, **kw): return IS.create(store, {"given_name": g, "family_name": f, **kw}, A).data
ina = person("Ina", "Teach", email="ina@example.com"); give_address(store, ina["id"])
NOW_ = "2026-10-14T12:00:00Z"
def mkreq(i, first, att, parts):
    r = {"id": f"{i}{i}{i}{i}{i}{i}{i}{i}-1111-4111-8111-111111111111", "confirmation_number": f"ICDT-PART0{i}", "registration_type": "class", "created_at": NOW_, "first_name": first, "last_name": "Requester", "email": first.lower() + "@example.com", "processing_status": "not_processed", "is_requester_attending": att, "attendee_count": len(parts) + int(att), "participants": parts}
    store.create(AT.REQUESTS.name, r["id"], dict(r)); return r
R1 = mkreq(1, "Ann", True, [{"first_name": "Bob", "last_name": "Guest", "email": "bob@example.com"}, {"first_name": "Cy"}])
R2 = mkreq(2, "Dora", False, [{"first_name": "Eve", "email": "eve@example.com"}])
assert AT.assign(store, {"scheduled_class_id": sc["id"], "role": "primary_instructor", "order": 1, "individual_id": ina["id"]}, A).ok

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    c = b.new_page(viewport={"width": 420, "height": 900}); errors = []
    c.on("pageerror", lambda e: errors.append(str(e)))
    c.route("**/enjoy_admin", admin_route)
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": [R1, R2]}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    c.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    c.goto(PAGE); c.fill("#keyInput", KEY); c.click("#unlockBtn"); c.wait_for_selector("#homeView:not([hidden])")
    c.select_option("#collPick", "requests"); c.wait_for_selector("#list li", state="attached")
    def open_put(name):
        li = c.locator("#list li", has_text=name)
        li.locator("button.head").click(); li.get_by_role("button", name="Put in a class…").click()
        c.wait_for_selector(".putbox select[id$='_cls']", state="attached")
        li.locator("select[id$='_cls']").select_option(sc["id"])
        return li
    li = open_put("Ann")
    said = li.locator(".putbox .note", has_text="will be placed").first.inner_text()
    check("the card lists everyone who will be placed", "Ann Requester" in said and "Bob Guest" in said and "Cy" in said and "(3)" in said, said)
    li.get_by_role("button", name="Add to class").click()
    c.wait_for_selector("#reqDone:not([hidden])")
    done = c.locator("#reqDone").inner_text()
    check("the banner names all three", "Ann Requester" in done and "Bob Guest" in done and "Cy" in done, done)
    rows = [d for d in store.data["attendances"].values() if d["role"] == "student"] if "attendances" in store.data else [d for d in store.data[next(k for k in store.data if k.endswith("attendances"))].values() if d["role"] == "student"]
    check("three students are on the attendance list, all from this request", len(rows) == 3 and all(d.get("request_id") == R1["id"] for d in rows), len(rows))
    to = sorted(m["to"] for m in sent if m["to"] != "ina@example.com")
    check("Ann and Bob were emailed; Cy has no email and nothing went to anyone else", to == ["ann@example.com", "bob@example.com"], to)
    # a request where the requester is not attending
    n = len(sent)
    c.select_option("#reqShow", "all") if c.locator("#reqShow option[value=all]").count() else None
    li2 = open_put("Dora")
    said2 = li2.locator(".putbox .note", has_text="will be placed").first.inner_text()
    check("not attending: the requester is not in the list", "Dora" not in said2 and "Eve" in said2 and "(1)" in said2, said2)
    li2.get_by_role("button", name="Add to class").click()
    c.wait_for_function("document.getElementById('reqDone').textContent.indexOf('Eve') >= 0")
    check("Eve was emailed, Dora was not", [m["to"] for m in sent][n:] == ["eve@example.com", "ina@example.com"], [m["to"] for m in sent][n:])
    # the Messages log shows the confirmation number on every entry that belongs to a request
    c.select_option("#collPick", "messages"); c.wait_for_selector("#mList li")
    confs = c.locator("#mList li .mconf").all_inner_texts()
    check("Messages: each placement email shows its request's confirmation number, upper right", confs.count("ICDT-PART01") >= 2 and confs.count("ICDT-PART02") >= 1, confs)
    c.fill("#mSearch", "ICDT-PART02"); c.wait_for_timeout(300)
    check("searching a confirmation number narrows the list to that request", 1 <= c.locator("#mList li").count() < len(confs), c.locator("#mList li").count())
    check("no script errors", not errors, errors)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all participants browser checks pass")); sys.exit(1 if fails else 0)

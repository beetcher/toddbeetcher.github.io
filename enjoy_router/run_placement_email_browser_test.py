#!/usr/bin/env python3
"""Browser test: the Console shows each student's correspondence log (newest first) and a Send confirmation email button; placing a
student reports the email; failures and refusals are said in plain words. Fake mail transport, in-memory store, headless Chromium.
Run from enjoy_router/:  python3 run_placement_email_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
import smtp_transport as T
import placement_email as PE
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
def fake(key, to, subject, body, html=None, attachments=None):
    sent.append({"to": to, "body": body, "att": attachments})
    return T.SendResult(True, "accepted") if mode[0] == "accept" else T.SendResult(False, "recipient_rejected")
T.transport = fake
ON = lambda st, id, actor, now, manual: PE.send_for(st, id, actor, "key", now, manual)
AT.notify = ON
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
person("Ann", "Able", email="ann@example.com"); person("Nina", "Nomail"); person("Bea", "Bad", email="bea@example.com")
assert AT.assign(store, {"scheduled_class_id": sc["id"], "role": "primary_instructor", "order": 1, "individual_id": ina["id"]}, A).ok

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    def open_class(name):
        pg.locator("#cList li", has_text=name).get_by_role("button", name="Attendance", exact=True).click()
        pg.wait_for_selector("#atDlg[open] #atBody .bandname")
    def add_student(query, name):
        det = pg.locator("#atAddBox")
        if not det.evaluate("e => e.open"): pg.locator("#atAddBox summary").click()
        f = pg.locator("#atBody form")
        f.locator("select[id$='_role']").select_option("student"); f.locator("select[id$='_who']").select_option("existing")
        f.locator("input[placeholder='Search by name']").fill(query)
        pg.locator("#atBody form button", has_text=name).first.click()
        f.get_by_role("button", name="Add to class").click()
        pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added %s') === 0" % name)
    def row(name): return pg.locator("#atBody .arow", has_text=name)
    def wait_msg(text):
        pg.wait_for_function("t => document.getElementById('atMsg').textContent.indexOf(t) >= 0", arg=text)
    open_class("Evening Basics")
    check("the instructor row has no message log", pg.locator("#atBody section.inst .alog").count() == 0)
    add_student("ann", "Ann Able")
    msg = pg.locator("#atMsg").inner_text()
    check("placing says the email with the calendar file went out", "confirmation email with the calendar file went to ann@example.com" in msg, msg)
    check("the email was sent once and carries a calendar file and the instructor", len(sent) == 1 and sent[0]["att"][0][0] == "workshop.ics" and "Lead instructor: Ina Teach" in sent[0]["body"], sent)
    pg.wait_for_selector("#atBody .arow .alog .alogline.bad, #atBody .arow .alog .alogline:not(.none)")
    t = row("Ann Able").locator(".alog").inner_text()
    check("Ann's row lists the message: kind, address, Sent, automatic", "Messages sent" in t and "Placement confirmation" in t and "Email to ann@example.com" in t and "Sent" in t and "automatic" in t, t)
    row("Ann Able").get_by_role("button", name="Send confirmation email").click()
    wait_msg("Confirmation email sent to Ann Able.")
    pg.wait_for_function("document.querySelectorAll('#atBody .arow .alog .alogline').length >= 2")
    lines = row("Ann Able").locator(".alog .alogline").all_inner_texts()
    check("pressing Send adds a line, newest first", len(lines) == 2 and "sent by hand" in lines[0] and "automatic" in lines[1], lines)
    check("a second email really went", len(sent) == 2)
    # a person with no email address
    add_student("nina", "Nina Nomail")
    check("no email on file: placed, and no email claim", "confirmation email" not in pg.locator("#atMsg").inner_text() and len(sent) == 2)
    check("her row says nothing was sent yet", "None yet." in row("Nina Nomail").locator(".alog").inner_text())
    row("Nina Nomail").get_by_role("button", name="Send confirmation email").click()
    wait_msg("no email address")
    check("the button explains why", "no email address on file" in pg.locator("#atMsg").inner_text())
    # a rejected email
    mode[0] = "reject"
    add_student("bea", "Bea Bad")
    check("a failed email is said plainly, and the person is still placed", "did not go" in pg.locator("#atMsg").inner_text() and row("Bea Bad").count() == 1, pg.locator("#atMsg").inner_text())
    pg.wait_for_selector("#atBody .alogline.bad")
    bt = row("Bea Bad").locator(".alogline.bad").inner_text()
    check("the log shows Failed with the reason", "Failed (recipient rejected)" in bt, bt)
    mode[0] = "accept"
    # email turned off
    AT.notify = None
    row("Ann Able").get_by_role("button", name="Send confirmation email").click()
    wait_msg("Email is turned off")
    check("with email off the button says so", "turned off on the server" in pg.locator("#atMsg").inner_text())
    AT.notify = ON
    pg.click("#atClose")
    # a class that is only an idea
    open_class("Idea Session")
    n = len(sent)
    add_student("ann", "Ann Able")
    check("a class with no date: placed, nothing sent", len(sent) == n and "confirmation email" not in pg.locator("#atMsg").inner_text())
    row("Ann Able").get_by_role("button", name="Send confirmation email").click()
    wait_msg("no date and start time")
    check("the button says to finish the class first", "no date and start time" in pg.locator("#atMsg").inner_text())
    check("no script errors", not errors, errors)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all placement-email browser checks pass")); sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Browser test: a save shows a working spinner on the pressed button and a toast (Working, then Done), the button cannot be pressed twice, and an email-sending status change asks first. Fake mail transport, in-memory store, headless Chromium.
Run from enjoy_router/:  python3 run_feedback_browser_test.py"""
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
person("Ann", "Able", email="ann@example.com")
assert AT.assign(store, {"scheduled_class_id": sc["id"], "role": "primary_instructor", "order": 1, "individual_id": ina["id"]}, A).ok

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900}); errors = []; dialogs = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("""(function(){var f=window.fetch;window.fetch=function(u,o){var slow=o&&o.body&&/"op":"assign"/.test(o.body);return f.apply(this,arguments).then(function(r){return slow?new Promise(function(ok){setTimeout(function(){ok(r)},1500)}):r})}})()""")
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    pg.locator("#cList li", has_text="Evening Basics").get_by_role("button", name="Attendance", exact=True).click()
    pg.wait_for_selector("#atDlg[open] #atBody .bandname")
    pg.locator("#atAddBox summary").click()
    f = pg.locator("#atBody form")
    f.locator("select[id$='_role']").select_option("student"); f.locator("select[id$='_who']").select_option("existing")
    f.locator("input[placeholder='Search by name']").fill("ann")
    pg.locator("#atBody form button", has_text="Ann Able").first.click()
    add = f.get_by_role("button", name="Add to class")
    add.click()
    pg.wait_for_selector("#workToast.on")
    check("while it saves the button shows the spinner class and is not pressable", "working" in add.get_attribute("class") and add.evaluate("e => getComputedStyle(e).pointerEvents") == "none")
    check("the toast says Working", "Working" in pg.locator("#workText").inner_text())
    pg.wait_for_selector("#workToast.ok")
    check("then it says Done", pg.locator("#workText").inner_text() == "Done")
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('Added Ann Able') === 0")
    pg.wait_for_function("!document.getElementById('workToast').classList.contains('on')", timeout=5000)
    check("the toast goes away by itself", True)
    check("one email only (the button could not be pressed twice)", len(sent) == 1, len(sent))
    # status change that emails asks first
    sel = pg.locator("#atBody .arow", has_text="Ann Able").locator("select")
    pg.once("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    sel.select_option("withdrawn")
    pg.wait_for_timeout(500)
    check("declining the question leaves the status alone and sends nothing", sel.input_value() == "assigned" and len(sent) == 1 and len(dialogs) == 1 and "emailed" in dialogs[0], (sel.input_value(), dialogs))
    pg.once("dialog", lambda d: d.accept())
    sel.select_option("withdrawn")
    pg.wait_for_function("document.getElementById('atMsg').textContent.indexOf('withdrawn') >= 0")
    check("accepting it withdraws and emails", len(sent) >= 2, len(sent))
    # a change that does not end a place asks nothing
    n = len(dialogs); pg.on("dialog", lambda d: (dialogs.append("unexpected"), d.accept()))
    sel2 = pg.locator("#atBody .arow", has_text="Ann Able").locator("select")
    sel2.select_option("confirmed"); pg.wait_for_timeout(700)
    check("a harmless change asks no question", "unexpected" not in dialogs)
    check("no script errors", not errors, errors)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all feedback browser checks pass")); sys.exit(1 if fails else 0)

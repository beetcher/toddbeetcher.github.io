#!/usr/bin/env python3
"""Browser test: the Instructors section on the Edit class screen shows the lead, changes the lead (one lead-change notice per person), adds and removes an instructor. Fake mail transport, in-memory store, headless Chromium.
Run from enjoy_router/:  python3 run_class_instructors_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
import smtp_transport as T
import comms, seed_comms
from launch_comms import wiring
from crud.memory_doc_store import MemoryDocStore
from crud import instructor_rosters_service as INS, attendances_service as AT, individuals_service as IS, scheduled_classes_crud as CL, venues_service as VS
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
    sent.append({"to": to, "subject": subject, "body": body, "att": attachments})
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


def person(g, f, **kw): return IS.create(store, {"given_name": g, "family_name": f, **kw}, A).data
ina = person("Ina", "Teach", email="ina@example.com"); give_address(store, ina["id"])
zed = person("Zed", "Newbie", email="zed@example.com"); give_address(store, zed["id"])
max_ = person("Max", "Mentor", email="max@example.com"); give_address(store, max_["id"])
ann = person("Ann", "Able", email="ann@example.com")
for p_ in (ina, zed, max_):
    r = INS.create(store, {"individual_id": p_["id"], "status": "active"}, A); assert r.ok, r.problems
assert AT.assign(store, {"scheduled_class_id": sc["id"], "role": "primary_instructor", "order": 1, "individual_id": ina["id"]}, A).ok
assert AT.assign(store, {"scheduled_class_id": sc["id"], "role": "student", "individual_id": ann["id"]}, A).ok
def roles(): return {store.get("individuals", r["individual_id"])["given_name"]: (r["role"], r.get("order"), "deleted_at" in r, r["status"]) for r in store.query("attendances", [("scheduled_class_id", "==", sc["id"])], limit=50)}
def changed(to): return [m for m in sent if m["to"] == to and "class changed" in m["subject"]]

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 1100}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "classes"); pg.wait_for_selector("#cList li")
    li = pg.locator("#cList li", has_text="Evening Basics"); li.locator("button.head").click()
    li.get_by_role("button", name="Edit", exact=True).click()
    pg.wait_for_selector("#cInsSection")
    box = pg.locator("#cInstructors")
    box.get_by_text("Lead instructor: Ina Teach").wait_for()
    check("the Edit class screen shows who is the lead instructor", box.get_by_text("Lead instructor: Ina Teach").count() == 1)
    # change the lead to someone not yet in the class
    lead_box = box.locator(".addbox").nth(0)
    lead_box.locator("input").fill("zed"); lead_box.get_by_role("button", name="Zed Newbie").click()
    sent.clear(); lead_box.get_by_role("button", name="Make lead").click()
    pg.wait_for_function("document.getElementById('cInsMsg').textContent.indexOf('lead instructor is now') >= 0")
    r_ = roles()
    check("the new person is the lead and the old lead stays on as an instructor", r_["Zed"][0] == "primary_instructor" and r_["Ina"][0] == "instructor", r_)
    pg.wait_for_function("document.getElementById('cInstructors').textContent.indexOf('Lead instructor: Zed Newbie') >= 0")
    check("the screen now shows the new lead", box.get_by_text("Lead instructor: Zed Newbie").count() == 1)
    check("the new lead is told they are assigned to teach", any(m["to"] == "zed@example.com" and "assigned to teach" in m["subject"] for m in sent), [(m["to"], m["subject"]) for m in sent])
    check("the student and the old lead each get ONE lead-change notice naming both", len(changed("ann@example.com")) == 1 and len(changed("ina@example.com")) == 1 and
          "Lead instructor: Ina Teach \u2192 Zed Newbie" in changed("ann@example.com")[0]["body"], [(m["to"], m["subject"]) for m in sent])
    # add another instructor
    add_box = box.locator(".addbox").nth(1)
    add_box.locator("input").fill("max"); add_box.get_by_role("button", name="Max Mentor").click()
    sent.clear(); add_box.get_by_role("button", name="Add instructor").click()
    pg.wait_for_function("document.getElementById('cInsMsg').textContent.indexOf('Added') >= 0")
    check("another instructor is added and told", roles()["Max"][0] == "instructor" and any(m["to"] == "max@example.com" and "assigned to teach" in m["subject"] for m in sent))
    pg.wait_for_function("document.getElementById('cInstructors').textContent.indexOf('Max Mentor') >= 0"); pg.wait_for_timeout(300)
    check("the list shows who is also teaching", box.get_by_text("Max Mentor").count() >= 1 and box.get_by_text("also teaching").count() >= 1)
    check("adding a second instructor is not a lead change", not changed("ann@example.com"))
    # remove him (two presses)
    sent.clear()
    row = box.locator(".arow", has_text="Max Mentor"); row.get_by_role("button", name="Remove").click()
    row.get_by_role("button", name="Really remove? They are emailed.").click()
    pg.wait_for_function("document.getElementById('cInsMsg').textContent.indexOf('was removed') >= 0")
    check("removing an instructor removes and tells them", roles()["Max"][2] and any(m["to"] == "max@example.com" and "no longer" in m["subject"] for m in sent), [(m["to"], m["subject"]) for m in sent])
    # promote someone already in the class (Ina, now an instructor) to lead: one notice per person
    lead_box.locator("input").fill("ina"); lead_box.get_by_role("button", name="Ina Teach").click()
    sent.clear(); lead_box.get_by_role("button", name="Make lead").click()
    pg.wait_for_function("document.getElementById('cInsMsg').textContent.indexOf('lead instructor is now') >= 0 && document.getElementById('cInstructors').textContent.indexOf('Lead instructor: Ina Teach') >= 0")
    for _ in range(40):
        if changed("zed@example.com") and changed("ann@example.com"): break
        pg.wait_for_timeout(250)
    r_ = roles()
    check("promoting someone already in the class: they lead, the old lead steps back", r_["Ina"][0] == "primary_instructor" and r_["Zed"][0] == "instructor", r_)
    check("promoting: one lead-change notice each for the student and the old lead", len(changed("ann@example.com")) == 1 and len(changed("zed@example.com")) == 1, [(m["to"], m["subject"]) for m in sent], r_, [(k, v) for k, v in [(a["individual_id"][-4:], (a["role"], a.get("order"), a.get("created_at"), a.get("updated_at"))) for a in store.query("attendances", [("scheduled_class_id", "==", sc["id"])], limit=50)]])
    # choosing the current lead says so and changes nothing
    lead_box.locator("input").fill("ina"); lead_box.get_by_role("button", name="Ina Teach").click(); sent.clear(); n = len(sent)
    lead_box.get_by_role("button", name="Make lead").click()
    pg.wait_for_function("document.getElementById('cInsMsg').textContent.indexOf('already the lead') >= 0")
    check("choosing the current lead changes nothing", not sent)
    # the class details Save button still works and does not touch instructors
    pg.fill("#ef_c_venue_notes", "Side door"); pg.click("#cEditSave")
    pg.wait_for_function("document.getElementById('cNotice').textContent.indexOf('Saved') === 0")
    check("saving the class details still works", store.get("scheduled_classes", sc["id"]).get("venue_notes") == "Side door" and roles()["Ina"][0] == "primary_instructor")
    check("no script errors", not errors, errors)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all class-instructor browser checks pass")); sys.exit(1 if fails else 0)

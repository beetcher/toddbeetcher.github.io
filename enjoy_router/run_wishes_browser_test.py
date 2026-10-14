#!/usr/bin/env python3
"""Browser test: the Console's Put in a class > Build the class shows a "They asked for" block (first and second choice date,
best time of day, other timing notes), fills the Date from the first choice date, and shows the time of day only as a display
indicator (three pills, one highlighted); the Start time is never filled in. Headless Chromium, in-memory store.
Run from enjoy_router/:  python3 run_wishes_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import attendances_service as AT
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

CONSOLE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)
NOW = "2026-10-14T12:00:00Z"
def req(i, conf, first, **kw):
    r = {"id": f"{i}{i}{i}{i}{i}{i}{i}{i}-2222-4222-8222-222222222222", "confirmation_number": conf, "registration_type": "private", "created_at": NOW,
         "first_name": first, "last_name": "Test", "email": f"{first.lower()}@example.com", "processing_status": "not_processed", **kw}
    store.create(AT.REQUESTS.name, r["id"], dict(r)); return r
W1 = req(1, "ICDT-WISH01", "Allwish", requested_date="2026-11-03", alternate_requested_date="2026-11-10", requested_time_of_day="evening", preferred_times="weekday evenings, not Fridays")
W2 = req(2, "ICDT-WISH02", "Dateonly", requested_date="2026-11-04")
W3 = req(3, "ICDT-WISH03", "Todonly", requested_time_of_day="morning")
W4 = req(4, "ICDT-WISH04", "Nowish")
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
    c.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": [W1, W2, W3, W4]}})))
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
        c.wait_for_timeout(300)
        return li
    li = build("Allwish"); box = li.locator(".wishbox"); t = box.inner_text() if box.count() else ""
    check("all answers: the block lists both dates, the time of day and the notes",
          "They asked for" in t and "2026-11-03" in t and "2026-11-10" in t and "Evening" in t and "weekday evenings, not Fridays" in t, t)
    check("the Date box is filled from the first choice date", li.locator("input[id$='n_date']").input_value() == "2026-11-03")
    check("the Start time box stays empty", li.locator("input[id$='n_time']").input_value() == "")
    pills = li.locator(".todpill")
    check("three pills, only Evening highlighted", pills.count() == 3 and li.locator(".todpill.on").count() == 1 and li.locator(".todpill.on").inner_text() == "Evening", pills.all_inner_texts())
    check("a hint says to pick the actual start time", "Pick the actual start time yourself" in li.locator(".putbox").inner_text())
    check("the pills are not buttons or inputs", li.locator(".todpills button, .todpills input").count() == 0)
    li = build("Dateonly"); t = li.locator(".wishbox").inner_text() if li.locator(".wishbox").count() else ""
    check("date only: first choice shown, no time of day, no pills", "2026-11-04" in t and "Best time" not in t and "Second choice" not in t and li.locator(".todpill").count() == 0, t)
    check("date only: the Date box is filled", li.locator("input[id$='n_date']").input_value() == "2026-11-04")
    li = build("Todonly"); t = li.locator(".wishbox").inner_text() if li.locator(".wishbox").count() else ""
    check("time of day only: shown as Morning, pills present, Date and Start time empty",
          "Morning" in t and li.locator(".todpill.on").inner_text() == "Morning" and li.locator("input[id$='n_date']").input_value() == "" and li.locator("input[id$='n_time']").input_value() == "", t)
    li = build("Nowish")
    check("nothing answered: no block, no pills, empty Date and Start time",
          li.locator(".wishbox").count() == 0 and li.locator(".todpills").count() == 0 and li.locator("input[id$='n_date']").input_value() == "" and li.locator("input[id$='n_time']").input_value() == "")
    check("no script errors in the Console", not cerr, cerr)
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all wishes browser checks pass")); sys.exit(1 if fails else 0)

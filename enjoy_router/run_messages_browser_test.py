#!/usr/bin/env python3
"""Browser test: the Messages station shows the whole message log, filters it with tick boxes and search, opens an entry, copies it, and
lets an operator add notes (add only) and mark a not-sent message handled. In-memory store, headless Chromium.
Run from enjoy_router/:  python3 run_messages_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone, timedelta
from crud.memory_doc_store import MemoryDocStore
from crud import communication_logs_crud as LG, scheduled_classes_crud as CL
from crud_endpoint import handle_admin, make_failure_limiter
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
base = {"class_type": "private", "program_slug": "launch", "is_public": False, "capacity_minimum": 1, "capacity_target": 5, "capacity_max": 9}
sc = CL.create(store, {**base, "title": "Evening Basics", "slug": "eb", "status": "identified"}, A).data
T0 = datetime(2026, 10, 15, 13, 0, 0, tzinfo=timezone.utc)
N = [0]
def log(**kw):
    N[0] += 1
    e = {"channel": "email", "trigger": "automatic", "contract_version": 1, "audience": "student", **kw}
    r = LG.record(store, e, "system:cms", now=T0 + timedelta(minutes=N[0]))
    assert r.ok, r.problems
    return r.data
ann = "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"
e1 = log(kind="request_received", audience="requester", to="ann@example.com", subject="Launch — we received your request", status="sent", reason="ok", request_id="11111111-1111-4111-8111-111111111111")
e2 = log(kind="placement_confirmation", to="ann@example.com", subject="Launch — you're scheduled: Thu Oct 29, 2:00 PM", status="sent", reason="ok", scheduled_class_id=sc["id"], attendance_id="22222222-2222-4222-8222-222222222222", individual_id=ann)
e3 = log(kind="placement_confirmation", status="not_sent", reason="no_contact", scheduled_class_id=sc["id"])
e4 = log(kind="placement_confirmation", to="bea@example.com", subject="Launch — you're scheduled", status="failed", reason="adapter_error", error_code="recipient_rejected")
e5 = log(kind="placement_confirmation", to="cy@example.com", subject="Launch — you're scheduled", status="unknown", reason="timeout")
e6 = log(kind="placement_confirmation", to="test-inbox@example.com", is_redirected=True, subject="Launch — you're scheduled", status="sent", reason="ok", trigger="manual")
e7 = log(kind="request_received", audience="requester", to="di@example.com", subject="Launch — we received your request", status="skipped", reason="duplicate")

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 420, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "scheduled_class.schema.json").read_text()
    pg.route("**/schemas/scheduled_class.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("Messages is a station on the home page", pg.locator("#stationTiles .tile", has_text="Messages").count() == 1)
    pg.select_option("#collPick", "messages"); pg.wait_for_selector("#mList li")
    check("the page has one visible title, Messages", pg.locator("#mTitle").is_visible() and pg.locator("#messagesView h2:visible").count() == 1)
    check("the filters start closed, but Search and Needs attention are always in view", not pg.evaluate("document.getElementById('mFilters').open") and pg.locator("#mSearch").is_visible() and pg.locator("#mAttnBtn").is_visible())
    check("the first message is near the top, not pushed down by a filter panel", pg.evaluate("document.querySelector('#mList li').getBoundingClientRect().top") < 600, pg.evaluate("document.querySelector('#mList li').getBoundingClientRect().top"))
    pg.click("#mFilterSummary")   # the rest of this test works the boxes inside Filters
    def rows(): return pg.locator("#mList li").count()
    def count(): return pg.locator("#mCount").inner_text()
    check("every entry is listed", rows() == 7 and count() == "7 messages", count())
    first = pg.locator("#mList li").first.inner_text()
    check("newest first (the skipped receipt)", "Skipped" in first and "Request received" in first and "di@example.com" in first, first)
    summ = pg.locator("#mSummary").inner_text()
    check("the summary counts each status and what needs attention", "3 sent" in summ and "1 failed" in summ and "1 unknown" in summ and "1 not sent" in summ and "1 skipped" in summ and "3 need attention" in summ, summ)
    check("the not-sent row says why in plain words", "no email or phone on file" in pg.locator('#mList li[data-log="%s"]' % e3["id"]).inner_text())
    check("the failed row shows the code, the redirected one is marked", "recipient rejected" in pg.locator('#mList li[data-log="%s"]' % e4["id"]).inner_text() and "test address" in pg.locator('#mList li[data-log="%s"]' % e6["id"]).inner_text())
    check("the by-hand one is marked", "by hand" in pg.locator('#mList li[data-log="%s"]' % e6["id"]).inner_text())
    check("trouble is red, sent is green", "bad" in pg.locator('#mList li[data-log="%s"]' % e4["id"]).get_attribute("class") and "ok" in pg.locator('#mList li[data-log="%s"]' % e1["id"]).get_attribute("class"))
    kinds = pg.locator("#mKindBoxes label").all_inner_texts()
    check("the message kinds come from the log", sorted(k.strip() for k in kinds) == ["Placement confirmation", "Request received"], kinds)
    # tick-box filters apply at once
    pg.locator("#mStatusBoxes input[value=sent]").uncheck()
    check("unticking Sent hides the sent ones", rows() == 4 and count() == "4 messages of 7", count())
    check("the filter heading says some are hidden", "some messages are hidden" in pg.locator("#mFilterSummary").inner_text())
    pg.locator("#mStatusBoxes input[value=sent]").check()
    pg.locator("#mKindBoxes label", has_text="Request received").locator("input").uncheck()
    check("unticking a kind hides it", rows() == 5 and "Request received" not in pg.locator("#mList").inner_text())
    pg.locator("#mKindBoxes label", has_text="Request received").locator("input").check()
    pg.locator("label", has_text="By hand").locator("input").uncheck()
    check("unticking By hand hides the manual one", rows() == 6)
    pg.locator("label", has_text="By hand").locator("input").check()
    pg.click("#mAttnBtn")
    check("the quick button shows it is on, and the box inside Filters agrees", pg.get_attribute("#mAttnBtn", "aria-pressed") == "true" and pg.is_checked("#mAttn"))
    check("Needs attention: failed, unknown and the unhandled not-sent", rows() == 3, count())
    pg.click("#mAttnBtn")
    pg.check("#mRedir")
    check("Went to a test address", rows() == 1 and "test-inbox@example.com" in pg.locator("#mList").inner_text())
    pg.uncheck("#mRedir")
    pg.fill("#mSearch", "ann@example.com")
    check("search finds an address", rows() == 2, count())
    pg.fill("#mSearch", "rejected")
    check("search finds a reason code", rows() == 1)
    pg.locator("#mStatusBoxes input[value=sent]").uncheck()
    pg.fill("#mSearch", "ann@example.com")
    check("search covers the whole log even when a filter is unticked", rows() == 2 and "Searching the whole log" in pg.locator("#mFilterSummary").inner_text(), count())
    pg.locator("#mStatusBoxes input[value=sent]").check()
    pg.fill("#mSearch", "")
    pg.click("#mShowAll")
    check("Show all brings everything back", rows() == 7)
    # open an entry
    row2 = pg.locator('#mList li[data-log="%s"]' % e2["id"])
    row2.locator(".mhead").click()
    d = row2.locator(".mdetail").inner_text()
    check("the detail shows the facts", "Placement confirmation" in d and "ann@example.com" in d and "Launch — you're scheduled" in d and e2["id"] in d and "Automatic" in d, d)
    check("no message body is shown anywhere (never stored)", "Hello" not in d)
    # notes: add only
    ta = row2.locator("textarea")
    row2.get_by_role("button", name="Add note").click()
    check("an empty note is refused in plain words", "Write the note first." in row2.inner_text())
    ta.fill("Looks fine. <b>Landed</b> in Primary after we dropped our own Message-ID.")
    row2.get_by_role("button", name="Add note").click()
    pg.wait_for_selector('#mList li[data-log="%s"] .mnote' % e2["id"])
    check("the note shows with who wrote it, and as typed (no markup)", "<b>Landed</b>" in row2.locator(".mnote").inner_text() and "user:admin" in row2.locator(".mnote").inner_text(), row2.locator(".mnote").inner_text())
    check("the row now carries a note marker", "1 note" in row2.locator(".mhead").inner_text())
    check("the note is saved on the server, the facts did not change", len(LG.get(store, e2["id"]).data["notes"]) == 1 and LG.get(store, e2["id"]).data["status"] == "sent" and LG.get(store, e2["id"]).data["to"] == "ann@example.com")
    row2.locator("textarea").fill("Second note: nothing to do.")
    row2.get_by_role("button", name="Add note").click()
    pg.wait_for_function("document.querySelectorAll('#mList li[data-log=\"%s\"] .mnote').length === 2" % e2["id"])
    check("notes are oldest first and there is no edit or delete", row2.locator(".mnote").first.inner_text().startswith("Looks fine") and row2.get_by_role("button", name="Edit").count() == 0 and row2.get_by_role("button", name="Delete").count() == 0)
    pg.check("#mNotes")
    check("Has notes shows only the commented entry", rows() == 1)
    pg.fill("#mSearch", "primary")
    check("search covers the note text", rows() == 1)
    pg.fill("#mSearch", ""); pg.evaluate("document.getElementById('mFilters').open = true"); pg.uncheck("#mNotes")
    # refresh keeps notes (they are on the server) and the open row
    pg.click("#mRefresh"); pg.wait_for_function("document.querySelectorAll('#mList li').length === 7")
    check("after Refresh the notes are still there", "2 notes" in pg.locator('#mList li[data-log="%s"] .mhead' % e2["id"]).inner_text())
    # copy
    row2 = pg.locator('#mList li[data-log="%s"]' % e2["id"])
    row2.get_by_role("button", name="Copy entry").click()
    pg.wait_for_function("document.getElementById('mNotice').textContent.indexOf('Entry copied') === 0")
    clip = pg.evaluate("navigator.clipboard.readText()")
    check("Copy entry puts the whole entry and its notes on the clipboard", "To: ann@example.com" in clip and "Status: Sent (sent)" in clip and "Second note" in clip, clip)
    row2.get_by_role("button", name="Copy as JSON").click()
    check("the Copy button itself says Copied", row2.get_by_role("button", name="Copied ✓").count() >= 1)
    pg.wait_for_function("document.getElementById('mNotice').textContent.indexOf('JSON copied') === 0")
    js = json.loads(pg.evaluate("navigator.clipboard.readText()"))
    check("Copy as JSON is the real record, notes included", js["id"] == e2["id"] and len(js["notes"]) == 2 and js["status"] == "sent", js)
    # jump to the class
    row2.get_by_role("button", name="Open the class attendance").click()
    pg.wait_for_selector("#atDlg[open]")
    check("the jump opens that class's attendance", "Evening Basics" in pg.locator("#atDlg").inner_text())
    pg.keyboard.press("Escape")
    # mark handled on the not-sent one
    row3 = pg.locator('#mList li[data-log="%s"]' % e3["id"])
    row3.locator(".mhead").click()
    check("only a not-sent entry offers Mark handled", row3.get_by_role("button", name="Mark handled").count() == 1 and pg.locator('#mList li[data-log="%s"]' % e1["id"]).get_by_role("button", name="Mark handled").count() == 0)
    row3.locator("textarea").fill("Phoned her, she is fine.")
    row3.get_by_role("button", name="Mark handled").click()
    pg.wait_for_function("document.getElementById('mSummary').textContent.indexOf('2 need attention') >= 0")
    h = LG.get(store, e3["id"]).data
    check("it is handled: marked, with the comment also as a note", h["handled_by"] == A and h["handled_note"] == "Phoned her, she is fine." and h["notes"][0]["text"] == "Handled: Phoned her, she is fine.", h)
    pg.click("#mAttnBtn")
    check("a handled message no longer needs attention", rows() == 2)
    pg.click("#mAttnBtn")
    # a server that cannot be reached is said plainly
    pg.unroute("**/enjoy_admin"); pg.route("**/enjoy_admin", lambda r: r.abort())
    pg.click("#mRefresh"); pg.wait_for_function("document.getElementById('mMsg').textContent.indexOf('Could not') >= 0")
    check("an unreachable server is said plainly", "Could not load the messages. Could not reach the server." in pg.locator("#mMsg").inner_text())
    check("the manual opens for Messages", pg.evaluate("document.querySelectorAll('[data-m=messages]').length") >= 1)
    check("no script errors", not errors, errors)
    b.close()
print(f"\n{'all passed' if not fails else str(len(fails)) + ' FAILED: ' + '; '.join(fails)}")
sys.exit(1 if fails else 0)

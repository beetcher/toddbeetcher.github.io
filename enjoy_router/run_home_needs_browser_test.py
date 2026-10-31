#!/usr/bin/env python3
"""Browser test (P-102): the "Needs you now" box on Home. It counts messages that did not go out (the same rule as the Messages switch "Needs attention")
and people invited who have not signed in yet, each with one button to the screen that fixes it, and it hides itself when nothing needs anyone.
Run from enjoy_router/:  python3 run_home_needs_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone, timedelta
from crud.memory_doc_store import MemoryDocStore
from crud import communication_logs_crud as LG, access_persons_crud as PE, access_roles_crud as RO
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []; A = "user:admin"
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
T0 = datetime(2026, 10, 15, 13, 0, 0, tzinfo=timezone.utc); N = [0]
def log(**kw):
    N[0] += 1
    e = {"channel": "email", "trigger": "automatic", "contract_version": 1, "audience": "student", **kw}
    r = LG.record(store, e, "system:cms", now=T0 + timedelta(minutes=N[0])); assert r.ok, r.problems; return r.data
log(kind="request_received", audience="requester", to="a@example.com", subject="Launch: we received your request", status="sent", reason="ok", request_id="11111111-1111-4111-8111-111111111111")
log(kind="placement_confirmation", status="not_sent", reason="no_contact")                                   # needs attention: not sent, not handled
log(kind="placement_confirmation", to="b@example.com", subject="Launch: you're scheduled", status="failed", reason="adapter_error", error_code="recipient_rejected")   # needs attention
log(kind="placement_confirmation", to="c@example.com", subject="Launch: you're scheduled", status="unknown", reason="timeout")                              # needs attention
log(kind="request_received", audience="requester", to="d@example.com", subject="Launch: we received your request", status="skipped", reason="duplicate")        # does not
role = RO.create(store, {"key": "viewer_role", "label": "Viewer", "is_super_admin": False, "capabilities": ["view_console"]}, A); assert role.ok, role.problems; role = role.data
def invite(email, name, **kw):
    r = PE.create(store, {"email": email, "display_name": name, "role_id": role["id"], **kw}, A); assert r.ok, r.problems; return r.data
p1, p2, p3 = invite("one@example.com", "One Pending"), invite("two@example.com", "Two Pending"), invite("three@example.com", "Three Signed In")
store.data["access_persons"][p3["id"]]["last_sign_in_at"] = "2026-10-20T10:00:00Z"                           # has signed in: not waiting
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.wait_for_selector("#needBox:not([hidden])"); txt = pg.inner_text("#needBody")
    check("the box is titled Needs you now and counts 3 messages plus 2 people", pg.inner_text("#needBox h3").lower().startswith("needs you now") and pg.inner_text("#needBadge") == "5", pg.inner_text("#needBox"))
    check("it says 3 messages did not go out (failed, unknown, not sent and not handled; sent and skipped do not count)", "3 messages did not go out" in txt, txt)
    check("it says 2 people were invited and have not signed in yet (the one who signed in does not count)", "2 people were invited and have not signed in yet" in txt, txt)
    check("each row has one button to the screen that fixes it", pg.locator("#needBody button[data-go=messages]").inner_text() == "Open Messages" and pg.locator("#needBody button[data-go=access]").inner_text() == "Open Access")
    pg.locator("#needBody button[data-go=messages]").click(); pg.wait_for_selector("#messagesView:not([hidden])"); pg.wait_for_timeout(500)
    check("Open Messages goes to Messages, whose own Needs attention count agrees (3)", pg.locator("#mChips .cf-chip", has_text="Needs attention").inner_text().strip().endswith("3"), pg.locator("#mChips").inner_text())
    pg.evaluate("location.hash='#/home'"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_selector("#needBox:not([hidden])")
    pg.locator("#needBody button[data-go=access]").click(); pg.wait_for_selector("#accessView:not([hidden])")
    check("Open Access goes to Access", pg.locator("#accessView").is_visible())
    # everything handled: mark the messages sent and the people signed in; the box goes away
    for e in store.data["communication_logs"].values(): e["status"] = "sent"
    for pr in store.data["access_persons"].values(): pr["last_sign_in_at"] = "2026-10-21T10:00:00Z"
    pg.evaluate("location.hash='#/home'"); pg.wait_for_selector("#homeView:not([hidden])"); pg.wait_for_timeout(700)
    check("with nothing waiting, the box is hidden", pg.locator("#needBox").is_hidden())
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("locking empties and hides the box", pg.locator("#needBox").is_hidden() and pg.evaluate("document.getElementById('needBody').children.length === 0"))
    check("no page errors", not errs, errs)
    b.close()
print("FAILED: " + ", ".join(fails) if fails else "OK: home needs-you-now checks pass"); sys.exit(1 if fails else 0)

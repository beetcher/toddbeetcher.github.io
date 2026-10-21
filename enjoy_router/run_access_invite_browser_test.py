#!/usr/bin/env python3
"""Browser test (P-64): the invitation email in the Access station. Real doors with an in-memory store, the real CMS with a fake email channel,
headless Chromium, signed in with the admin key. Checks: the message after inviting says the email went (or why it did not); Resend invite
email is on each person who is switched on and not on a switched-off one; pressing it sends and says so; a provider failure is said in
words; the invitation is saved even when the email fails; no script errors; a screenshot is written for a human to look at.
Run from enjoy_router/:  python3 run_access_invite_browser_test.py   (SHOT=/path/dir to choose where screenshots go)"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
import comms
from comms.channels.fake import FakeChannel
from crud import access_persons_crud as PE, access_roles_crud as RO, discovery_areas_crud as AR
from crud import comms_settings_crud as CS, message_templates_crud as MT
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
from launch_comms import kinds as K
from launch_comms.directory import IndividualDirectory
from launch_comms.stores import LogStore, SettingsStore, TemplateStore
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
A = "user:admin"
SHOT = pathlib.Path(os.environ.get("SHOT", "/tmp/claude-0/shots")); SHOT.mkdir(parents=True, exist_ok=True)
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
SEED = json.loads((HERE.parent / "schemas" / "examples" / "message_template.seed.json").read_text())["templates"]
for t in SEED:
    r = MT.create(store, {k: t[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A); assert r.ok, r.problems
    assert MT.publish(store, r.data["id"], A).ok
assert CS.create(store, {}, A).ok
ch = FakeChannel()
def wire(channel):
    comms.configure(comms.Comms(kinds=K.registry(), directory=IndividualDirectory(store), templates=TemplateStore(store), log=LogStore(store), settings=SettingsStore(store),
                                channels=[channel], mode="live"))
wire(ch)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

sup = RO.create(store, {"key": "super_admin", "label": "Super admin", "is_super_admin": True, "is_active": True}, A).data
mgr = RO.create(store, {"key": "manager", "label": "Manager", "is_super_admin": False, "is_active": True, "capabilities": ["view_console", "manage_requests"],
                        "description": "Runs classes and requests in their own regions."}, A).data
PE.create(store, {"email": "todd@example.com", "display_name": "Todd Beetcher", "role_id": sup["id"]}, A)
hana = PE.create(store, {"email": "hana@example.com", "display_name": "Hana Head", "role_id": mgr["id"]}, A).data
off = PE.create(store, {"email": "off@example.com", "display_name": "Olly Off", "role_id": mgr["id"], "is_active": False}, A).data
AR.create(store, {"kind": "state", "name": "Colorado", "state_code": "CO", "is_active": True}, A)

def row(pg, who): return pg.locator("#accessView .acrow", has_text=who)
def rowmsg(pg, who): return row(pg, who).locator(".acrowmsg")
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 1000}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "access"); pg.wait_for_selector("#accessView .acrow")

    check("Resend invite email is on a person who is switched on", row(pg, "Hana Head").get_by_role("button", name="Resend invite email", exact=True).count() == 1)
    check("...and not on a person who is switched off", row(pg, "Olly Off").get_by_role("button", name="Resend invite email", exact=True).count() == 0)
    check("...and the invite button still has its own name", pg.get_by_role("button", name="Invite someone", exact=True).count() == 1)

    # ---- invite: the email goes
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apEmail")
    pg.fill("#apEmail", "dana@example.com"); pg.fill("#apName", "Dana Smith"); pg.select_option("#apRole", mgr["id"])
    pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Dana Smith')")
    msg = pg.locator("#accessView .acerr[role=status]").first.inner_text()
    check("the page says the invitation email went, to that address, in the success colour", msg == "Added. An invitation email went to dana@example.com." and "acok" in pg.locator("#accessView .acerr[role=status]").first.get_attribute("class"), msg)
    check("one real email went to that address with the Console link and the exact Google account", [m["to"] for m in ch.sent] == ["dana@example.com"] and "https://beetcher.com/console/" in ch.sent[0]["content"]["text"] and "dana@example.com" in ch.sent[0]["content"]["text"])
    check("the email names the inviter as the LAUNCH team (the admin key)", "The LAUNCH team has invited you" in ch.sent[0]["content"]["text"])
    check("Dana has a Resend invite email button", row(pg, "Dana Smith").get_by_role("button", name="Resend invite email", exact=True).count() == 1)
    pg.screenshot(path=str(SHOT / "invite_sent.png"))

    # ---- resend
    row(pg, "Hana Head").get_by_role("button", name="Resend invite email", exact=True).click()
    row(pg, "Hana Head").locator(".acrowmsg").wait_for()
    msg = rowmsg(pg, "Hana Head").inner_text()
    check("Resend says it sent, to Hana's address, on Hana's own row", msg == "Invitation email sent to hana@example.com.", msg)
    check("...in the success colour, and nothing is said at the top of the station", "acok" in rowmsg(pg, "Hana Head").get_attribute("class") and pg.locator("#accessView > .acs > .acerr[role=status]").first.inner_text() == "")
    check("the resend email went to Hana, as a second email overall", [m["to"] for m in ch.sent] == ["dana@example.com", "hana@example.com"])
    row(pg, "Hana Head").get_by_role("button", name="Resend invite email", exact=True).click()
    pg.wait_for_timeout(400)
    check("pressing Resend again sends again", len(ch.sent) == 3, len(ch.sent))
    check("a row message belongs to one row only", rowmsg(pg, "Dana Smith").count() == 0 and rowmsg(pg, "Olly Off").count() == 0)
    pg.screenshot(path=str(SHOT / "resend_sent.png"))

    # ---- the provider refuses
    bad = FakeChannel(outcome="rejected", error_code="provider_refused"); wire(bad)
    row(pg, "Hana Head").get_by_role("button", name="Resend invite email", exact=True).click()
    row(pg, "Hana Head").locator(".acrowmsg").wait_for(); pg.wait_for_function("[...document.querySelectorAll('.acrowmsg')].some(e => e.innerText.includes('did not go'))")
    msg = rowmsg(pg, "Hana Head").inner_text()
    check("a refusal on Resend is said in words, on the row, not in the success colour", msg == "The invitation email did not go (the email service refused it)." and "acok" not in rowmsg(pg, "Hana Head").get_attribute("class"), msg)
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apEmail")
    pg.fill("#apEmail", "erin@example.com"); pg.select_option("#apRole", mgr["id"])
    pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('erin@example.com')")
    msg = pg.locator("#accessView .acerr[role=status]").first.inner_text()
    check("when the email fails the person is still added and the page says how to retry", msg.startswith("Added. They can sign in with that Google account, but the invitation email did not go (the email service refused it).") and "Resend invite email" in msg, msg)
    check("the person is really saved", PE.find_live_by_email(store, "erin@example.com") is not None)
    pg.screenshot(path=str(SHOT / "invite_failed.png"))

    # ---- email sending is off on the server
    comms.configure(None)
    row(pg, "Hana Head").get_by_role("button", name="Resend invite email", exact=True).click()
    pg.wait_for_function("[...document.querySelectorAll('.acrowmsg')].some(e => e.innerText.includes('not switched on'))")
    msg = rowmsg(pg, "Hana Head").inner_text()
    check("with email sending not switched on, Resend says so in words", msg == "Email: Email sending is not switched on here.", msg)
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apEmail")
    pg.fill("#apEmail", "fred@example.com"); pg.select_option("#apRole", mgr["id"])
    pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('fred@example.com')")
    msg = pg.locator("#accessView .acerr[role=status]").first.inner_text()
    check("inviting with email off adds the person and says the sending is switched off", "email sending is switched off on the server" in msg and msg.startswith("Added."), msg)

    # ---- phone width
    pg.set_viewport_size({"width": 375, "height": 800}); pg.wait_for_timeout(200)
    check("phone width: the button row still fits (no sideways scroll)", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    pg.screenshot(path=str(SHOT / "invite_phone.png"))
    check("no script errors", not errs, errs)
    b.close()
print("\n%s" % ("All browser checks passed." if not fails else "FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)

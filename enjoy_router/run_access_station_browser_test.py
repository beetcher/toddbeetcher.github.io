#!/usr/bin/env python3
"""Browser test (P-62 step 5): the Access station. Real doors with an in-memory store, headless Chromium, signed in with the admin key.
Checks: the station and its capability table; invite someone; refusals read in plain words; edit; switch off and on; add and edit a role;
manage_access is not offered; the last super admin is protected; an email is locked after a first sign-in; no script errors.
Run from enjoy_router/:  python3 run_access_station_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud import access_persons_crud as PE, access_roles_crud as RO, discovery_areas_crud as AR
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
A = "user:admin"
store = MemoryDocStore(""); limiter = make_failure_limiter(); fails = []
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

sup = RO.create(store, {"key": "super_admin", "label": "Super admin", "is_super_admin": True, "is_active": True}, A).data
head = RO.create(store, {"key": "region_head", "label": "Region head", "is_super_admin": False, "is_active": True, "capabilities": ["view_console", "edit_venues"]}, A).data
todd = PE.create(store, {"email": "todd@example.com", "display_name": "Todd Beetcher", "role_id": sup["id"]}, A).data
hana = PE.create(store, {"email": "hana@example.com", "display_name": "Hana Head", "role_id": head["id"]}, A).data
AR.create(store, {"kind": "state", "name": "Colorado", "state_code": "CO", "is_active": True}, A)
reg = AR.create(store, {"kind": "region", "name": "Boulder", "state_code": "CO", "zip_codes": ["80301"], "is_active": True}, A).data

def rows(pg, sel): return pg.locator(sel).count()
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 1000}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("Access is a station on the home page, marked admin", pg.locator('#stationTiles .tile[data-go="access"]').count() == 1 and "admin" in pg.locator('#stationTiles .tile[data-go="access"]').inner_text().lower())
    pg.select_option("#collPick", "access"); pg.wait_for_selector("#accessView .acrow")
    check("both people are listed with their roles", rows(pg, "#accessView .acrow") >= 4 and "Todd Beetcher" in pg.inner_text("#accessView") and "Hana Head" in pg.inner_text("#accessView"))
    txt = pg.inner_text("#accessView")
    check("a person who never signed in says so", "Has not signed in yet" in txt)
    check("the capability table lists all 15", pg.locator("#accessView table tr").count() == 16, pg.locator("#accessView table tr").count())
    check("the super admin role says it does everything", "Everything, including access" in txt)

    # ---- invite
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apEmail")
    check("the invite form offers the roles and the region", set(pg.eval_on_selector_all("#apRole option", "o => o.map(x => x.textContent)")) == {"Region head", "Super admin (super admin)"} and "Boulder, CO" in pg.inner_text("#apRegion"))
    pg.fill("#apEmail", "nora@example.com"); pg.fill("#apName", "Nora New"); pg.select_option("#apRole", head["id"]); pg.select_option("#apRegion", reg["id"])
    pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Nora New')")
    nora = PE.find_live_by_email(store, "nora@example.com")
    check("the invitation is saved, switched on, with the role and region", bool(nora) and nora["is_active"] and nora["role_id"] == head["id"] and nora["scope_region_id"] == reg["id"] and nora["display_name"] == "Nora New", nora)
    check("it was written by the admin key's actor", nora and nora["created_by"] == "user:admin")
    check("the page confirms and shows the region", "Added" in pg.inner_text("#accessView") and "Region: Boulder" in pg.inner_text("#accessView"))
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.fill("#apEmail", "NORA@example.com"); pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('apErr').textContent.length > 0")
    check("the same email twice is refused in plain words", "Email: That one is already used." in pg.inner_text("#apErr"), pg.inner_text("#apErr"))
    pg.fill("#apEmail", "not-an-email"); pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('apErr').textContent.includes('not valid')")
    check("a bad email is refused", "Email" in pg.inner_text("#apErr"))
    pg.get_by_role("button", name="Cancel", exact=True).click()

    # ---- edit, switch off and on
    def row(name): return pg.locator("#accessView .acrow", has_text=name).first
    row("Nora New").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#apName")
    pg.fill("#apName", "Nora Newman"); pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Nora Newman')")
    check("an edit is saved", PE.find_live_by_email(store, "nora@example.com")["display_name"] == "Nora Newman")
    check("an edit that does not touch the region keeps it", PE.find_live_by_email(store, "nora@example.com")["scope_region_id"] == reg["id"])
    row("Nora Newman").get_by_role("button", name="Switch off", exact=True).click(); pg.wait_for_function("document.querySelector('#accessView .acrow.off')")
    check("Switch off turns access off and keeps the record", PE.find_live_by_email(store, "nora@example.com")["is_active"] is False and "Access switched off" in pg.inner_text("#accessView"))
    row("Nora Newman").get_by_role("button", name="Switch on", exact=True).click(); pg.wait_for_function("!document.querySelector('#accessView .acrow.off')")
    check("Switch on restores it", PE.find_live_by_email(store, "nora@example.com")["is_active"] is True)

    # ---- the last super admin
    row("Todd Beetcher").get_by_role("button", name="Switch off", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('no active super admin')")
    check("the last super admin cannot be switched off, and the page says why", PE.find_live_by_email(store, "todd@example.com")["is_active"] is True)

    # ---- roles
    pg.get_by_role("button", name="Add a role", exact=True).click(); pg.wait_for_selector("#arKey")
    labels = pg.locator("#accessView .accaps input").evaluate_all("els => els.map(e => e.value)")
    check("the role form offers 14 capabilities and never manage_access", len(labels) == 14 and "manage_access" not in labels, labels)
    pg.fill("#arKey", "helper"); pg.fill("#arLabel", "Helper")
    for c in ("view_console", "view_messages"): pg.locator('#accessView .accaps input[value="%s"]' % c).check()
    pg.locator('#accessView .accaps input[value="view_console"]').uncheck(); pg.locator('#accessView .accaps input[value="view_messages"]').uncheck()
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('arErr').textContent.length > 0")
    check("a role with no capability is refused", "Capabilities: Required." in pg.inner_text("#arErr"), pg.inner_text("#arErr"))
    for c in ("view_console", "view_messages"): pg.locator('#accessView .accaps input[value="%s"]' % c).check()
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('view_console, view_messages')")
    helper = RO.list(store, {"key": "helper"}).data["records"][0]
    check("the role is saved with its capabilities", sorted(helper["capabilities"]) == ["view_console", "view_messages"] and helper["is_active"] and not helper["is_super_admin"])
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apRole")
    check("a new role can be given to an invited person at once", "Helper" in pg.inner_text("#apRole")); pg.get_by_role("button", name="Cancel", exact=True).click()
    pg.locator("#accessView .acrow", has_text="Helper").first.get_by_role("button", name="Switch off", exact=True).click(); pg.wait_for_function("document.querySelector('#accessView .acrow.off')")
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apRole")
    check("a switched-off role is not offered for new invitations", "Helper" not in pg.inner_text("#apRole"))
    pg.get_by_role("button", name="Cancel", exact=True).click()
    pg.locator("#accessView .acrow.off", has_text="Helper").first.get_by_role("button", name="Switch on", exact=True).click(); pg.wait_for_function("!document.querySelector('#accessView .acrow.off')")
    pg.select_option("#collPick", "home")
    check("leaving the station hides it", not pg.locator("#accessView").is_visible())
    pg.select_option("#collPick", "access"); pg.wait_for_selector("#accessView .acrow")
    pg.locator("#accessView .acrow", has_text="Helper").first.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#arLabel")
    check("the key cannot be changed after the role is saved", pg.locator("#arKey").is_disabled())
    pg.locator('#accessView .accaps input[value="view_messages"]').uncheck(); pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("!document.getElementById('accessView').innerText.includes('view_messages,')")
    check("a role's capabilities can be changed", RO.get(store, helper["id"]).data["capabilities"] == ["view_console"])
    pg.locator("#accessView .acrow", has_text="Super admin").last.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#arLabel")
    check("...the form says it holds everything instead of listing boxes", pg.locator("#accessView .accaps").count() == 0 and "holds every capability" in pg.inner_text("#accessView"))
    pg.get_by_role("button", name="Cancel", exact=True).click()

    # ---- an email is locked after a first sign-in
    PE.record_sign_in(store, PE.find_live_by_email(store, "hana@example.com"), "uid-hana", datetime.now(timezone.utc))
    pg.select_option("#collPick", "home"); pg.select_option("#collPick", "access"); pg.wait_for_selector("#accessView .acrow")
    pg.wait_for_function("document.getElementById('accessView').innerText.includes('Last signed in')")
    row("Hana Head").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#apEmail")
    check("once someone has signed in their email cannot be edited", pg.locator("#apEmail").is_disabled())
    pg.get_by_role("button", name="Cancel", exact=True).click()
    check("the page made no script errors", not errs, errs)
    check("nothing scrolls sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    pg.set_viewport_size({"width": 390, "height": 900}); pg.wait_for_timeout(200)
    check("phone width: nothing scrolls sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    b.close()

print("\nFAILED: " + ", ".join(fails) if fails else "\nOK: all Access station browser checks pass")
sys.exit(1 if fails else 0)

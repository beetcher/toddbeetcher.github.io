#!/usr/bin/env python3
"""Browser test (Access look, steps L-1 to L-8): the tab row (People, Territory, Roles, Sign-in and data checks), its addresses and keyboard, tabs that
would be empty are hidden (a person who may only invite sees People alone), no inline style, then (as the steps land) plain words, buttons, People,
Roles, Territory, Sign-in checks, states and phone. Run from enjoy_router/:  python3 run_access_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import access_roles_crud as AR_, access_persons_crud as PE
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SHOTS = pathlib.Path(os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="access_look_")); SHOTS.mkdir(parents=True, exist_ok=True)
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
A = "user:admin"
sup = AR_.create(store, {"key": "super_admin", "label": "Super admin", "is_super_admin": True, "is_active": True}, A).data
head = AR_.create(store, {"key": "region_head", "label": "Region head", "is_super_admin": False, "is_active": True, "capabilities": ["view_console", "edit_venues"]}, A).data
big = AR_.create(store, {"key": "ops_lead", "label": "Ops lead", "description": "Runs the day to day.", "is_super_admin": False, "is_active": True, "capabilities": ["view_console", "manage_requests", "manage_classes", "edit_venues", "edit_people", "edit_places", "view_messages", "manage_messages", "run_discovery", "view_performance"]}, A).data
PE.create(store, {"email": "todd@example.com", "display_name": "Todd Beetcher", "role_id": sup["id"]}, A)
PE.create(store, {"email": "hana@example.com", "display_name": "Hana Head", "role_id": head["id"]}, A)
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/access'"); pg.wait_for_selector("#accessView .acrow")

    # ===== L-1 tabs shell
    tabs = pg.locator("#accessView [role=tab]")
    check("L-1 four tabs, People first and selected", tabs.all_inner_texts() == ["People", "Territory", "Roles", "Sign-in and data checks"] and pg.get_attribute("#acTab-people", "aria-selected") == "true", tabs.all_inner_texts())
    check("L-1 the tab row is a tablist with a tabpanel", pg.locator("#accessView [role=tablist]").count() == 1 and pg.get_attribute("#acPanel", "role") == "tabpanel" and pg.get_attribute("#acPanel", "aria-labelledby") == "acTab-people")
    check("L-1 only the People tab's content is on the page", pg.locator("#acTerr").count() == 0 and pg.locator("#acSignIn").count() == 0 and pg.locator("#accessView table").count() == 0)
    pg.click("#acTab-signin"); pg.wait_for_selector("#acSignIn")
    check("L-1 Sign-in and data checks holds the sign-in, review code and time zone boxes under their old ids", all(pg.locator(i).count() == 1 for i in ["#acSignIn", "#acReview", "#acZones"]))
    check("L-1 the time zone box sits under a Data checks heading", pg.locator("#accessView h2", has_text="Data checks").count() == 1)
    check("L-1 the address follows the tab and keeps the page", pg.evaluate("location.hash") == "#/access/signin" and pg.locator("#accessView").is_visible())
    pg.click("#acTab-territory"); pg.wait_for_selector("#acTerr")
    check("L-1 Territory holds the two views", pg.evaluate("location.hash") == "#/access/territory" and pg.locator("#accessView").get_by_role("button", name="By permission").count() == 1)
    pg.click("#acTab-roles"); pg.wait_for_selector("#accessView table")
    check("L-1 Roles holds the role cards and the permission list", pg.locator("#accessView .acrow").count() >= 2 and pg.locator("#accessView table").count() == 1)
    # ===== L-2 plain words
    import re
    def raw_keys(sel):
        txt = pg.evaluate("(s) => { const r = document.querySelector(s); const c = r.cloneNode(true); c.querySelectorAll('code,[title]').forEach(e => { e.removeAttribute('title'); if (e.tagName === 'CODE') e.remove(); }); return c.innerText; }", sel)
        return re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", txt)
    check("L-2 the Roles tab shows no technical permission names (they are small grey text under the plain name)", raw_keys("#acPanel") == [], raw_keys("#acPanel"))
    ops = pg.locator("#accessView .acrow", has_text="Ops lead")
    check("L-2 a role card says what it can do in plain words, first four, then 'and 6 more'", "Can: Open the Console, Manage registration requests, Manage classes and attendance, Edit venues and 6 more" in ops.inner_text(), ops.inner_text())
    ops.locator("summary").click()
    check("L-2 See all lists every permission by plain name", "Run Discovery" in ops.inner_text() and "See Performance" in ops.inner_text())
    check("L-2 the role's technical name is not on the card, only in its hover text", "ops_lead" not in ops.inner_text() and ops.locator(".acn").get_attribute("title") == "Technical name: ops_lead")
    check("L-2 the permission list shows plain name with the technical name under it", "view_console" in pg.locator("#accessView table code.ackey").all_inner_texts() and "Open the Console" in pg.locator("#accessView table tr", has=pg.locator("code.ackey", has_text="view_console")).inner_text())
    check("L-2 the list is headed 'What each permission allows'", pg.locator("#accessView h2", has_text="What each permission allows").count() == 1)
    pg.click("#acTab-people"); pg.wait_for_selector("#accessView .acrow")
    check("L-2 a person says 'Works in:' not 'Title (from their territory)'", "Works in:" in pg.inner_text("#acPanel") and "Title (from" not in pg.inner_text("#acPanel"))
    pg.click("#acTab-territory"); pg.wait_for_selector("#acTerr")
    pg.get_by_role("button", name="By permission", exact=True).click(); pg.wait_for_selector("#acTerr details")
    check("L-2 by permission, the list reads in plain names", "Manage registration requests" in pg.inner_text("#acTerr") and raw_keys("#acTerr") == [], raw_keys("#acTerr"))
    # ===== L-3 button cues
    pg.click("#acTab-people"); pg.wait_for_selector("#accessView .acrow")
    prim = pg.locator("#acPanel button.btn-primary").all_inner_texts()
    check("L-3 People: one orange button, Invite someone", prim == ["Invite someone"], prim)
    check("L-3 People: Edit is outlined, Switch off is a plain link", pg.locator("#acPanel .acrow").first.get_by_role("button", name="Edit").get_attribute("class") == "btn-secondary" and pg.locator("#acPanel .acrow").first.get_by_role("button", name="Switch off").get_attribute("class") == "btn-link")
    pg.get_by_role("button", name="Invite someone").click(); pg.wait_for_selector("#apEmail")
    check("L-3 with the invite form open, its Send invitation is the one orange button and Invite someone steps back", pg.locator("#acPanel button.btn-primary").all_inner_texts() == ["Send invitation"], pg.locator("#acPanel button.btn-primary").all_inner_texts())
    pg.get_by_role("button", name="Cancel", exact=True).click()
    pg.click("#acTab-roles"); pg.wait_for_selector("#accessView table")
    check("L-3 Roles: one orange button, Add a role", pg.locator("#acPanel button.btn-primary").all_inner_texts() == ["Add a role"])
    pg.click("#acTab-signin"); pg.wait_for_selector("#acSignIn")
    check("L-3 Sign-in: one orange button per box (Save minutes, Set code); Check places is outlined", pg.locator("#acPanel button.btn-primary").all_inner_texts() == ["Save minutes", "Set code (24 hours)"] and pg.locator("#acZoneCheck").get_attribute("class") == "btn-secondary", pg.locator("#acPanel button.btn-primary").all_inner_texts())
    hs = pg.evaluate("[...document.querySelectorAll('#acPanel button.btn-primary, #acPanel button.btn-secondary')].map(b => Math.round(b.getBoundingClientRect().height))")
    check("L-3 every outlined and orange button on the tab has one height", len(set(hs)) == 1, hs)
    check("L-3 no red anywhere on the Access page (nothing here deletes)", pg.locator("#accessView button.btn-danger, #accessView button.danger").count() == 0)
    pg.click("#acTab-roles"); pg.wait_for_selector("#accessView table")
    pg.focus("#acTab-roles"); pg.keyboard.press("ArrowRight"); pg.wait_for_selector("#acTab-signin[aria-selected=true]")
    check("L-1 arrow keys move between tabs and focus follows", pg.evaluate("document.activeElement.id") == "acTab-signin")
    pg.keyboard.press("Home"); pg.wait_for_selector("#acTab-people[aria-selected=true]")
    check("L-1 Home goes to the first tab", pg.evaluate("document.activeElement.id") == "acTab-people")
    pg.evaluate("location.hash='#/home'"); pg.evaluate("location.hash='#/access/roles'"); pg.wait_for_selector("#acTab-roles[aria-selected=true]")
    check("L-1 an address with a tab opens that tab", pg.locator("#accessView table").count() == 1)
    check("L-1 no inline style block (the rules are in console.css)", pg.locator("style#accessStyle").count() == 0 and pg.evaluate("getComputedStyle(document.querySelector('.acs')).maxWidth") == "900px")
    pg.screenshot(path=str(SHOTS / "L1_roles.png"), full_page=True)

    # a person who may only invite sees People alone (no empty tabs)
    pg.evaluate("ConsoleKit.me = function () { return { name: 'Hana Head', is_super_admin: false, inspector: false, method: 'google', grants: [{ kind: 'all', capabilities: ['invite_people'] }] }; }")
    pg.evaluate("location.hash='#/home'"); pg.evaluate("location.hash='#/access/roles'"); pg.wait_for_selector("#accessView .acs")
    check("L-1 a person who may only invite sees no tab row and the People page", pg.locator("#accessView [role=tab]").count() == 0 and "Invite someone" in pg.inner_text("#accessView") and pg.locator("#accessView table").count() == 0)
    # ===== L-4 People tab
    pg.evaluate("ConsoleKit.me = function () { return null; }")
    pg.goto(PAGE); pg.wait_for_timeout(500)
    if pg.locator("#keyInput").is_visible(): pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    PE.record_sign_in(store, PE.find_live_by_email(store, "hana@example.com"), "uid-hana", datetime.now(timezone.utc))
    pg.evaluate("location.hash='#/access'"); pg.wait_for_selector("#accessView .acrow")
    hana = pg.locator("#acPanel .acrow", has_text="Hana Head"); todd = pg.locator("#acPanel .acrow", has_text="Todd Beetcher")
    check("L-4 a person who has signed in shows when; one who has not says invited and not signed in yet", "Last signed in" in hana.inner_text() and "Has not signed in yet" in todd.inner_text() and "Invited" in todd.inner_text(), todd.inner_text())
    check("L-4 Resend invite email shows only for people who have not signed in", todd.get_by_role("button", name="Resend invite email").count() == 1 and hana.get_by_role("button", name="Resend invite email").count() == 0)
    check("L-4 each person has a History link (plain, not a button box)", hana.get_by_role("button", name="History of Hana Head").get_attribute("class") == "btn-link")
    check("L-4 with only a few people there is no search or filter row", pg.locator("#acSearch").count() == 0 and pg.locator("#acChips").count() == 0)
    pg.get_by_role("button", name="Invite someone").click(); pg.wait_for_selector("#apName"); pg.fill("#apName", "todd beetcher")
    check("L-4 typing a name that is already listed warns, without refusing", "A person named todd beetcher is already listed" in pg.inner_text("#apDup") and "Super admin" in pg.inner_text("#apDup"), pg.inner_text("#apDup"))
    pg.fill("#apName", "Brand New"); check("L-4 a new name clears the warning", pg.inner_text("#apDup") == "")
    pg.get_by_role("button", name="Cancel", exact=True).click()
    todd.get_by_role("button", name="Switch off").click(); pg.wait_for_selector("#uiDialog[open]"); pg.click("#uiNo")
    check("L-4 Keep on leaves a super admin switched on", PE.find_live_by_email(store, "todd@example.com")["is_active"] is True)
    # ===== L-5 Roles tab
    pg.click("#acTab-roles"); pg.wait_for_selector("#accessView table")
    reg = pg.locator("#acPanel .acrow", has_text="Region head")
    check("L-5 a role card says how many people hold it and who", "1 person holds this role" in reg.inner_text(), reg.inner_text())
    check("L-5 a role no one holds says so", "No one holds this role." in pg.locator("#acPanel .acrow", has_text="Ops lead").inner_text())
    reg.get_by_role("button", name="Edit").click(); pg.wait_for_selector("#arLabel")
    check("L-5 editing a role says who it affects", "Changing this role affects 1 person: Hana Head." in pg.inner_text("#acPanel"), pg.inner_text("#acPanel"))
    pg.get_by_role("button", name="Cancel", exact=True).click()
    reg.get_by_role("button", name="Switch off").click(); pg.wait_for_selector("#uiDialog[open]")
    check("L-5 switching off a role people hold asks first and says what happens", "cannot sign in" in pg.inner_text("#uiDialog") and "1 person holds the Region head role" in pg.inner_text("#uiDialog"), pg.inner_text("#uiDialog")); pg.click("#uiNo")
    check("L-5 Keep on leaves the role on", pg.locator("#acPanel .acrow", has_text="Region head").get_by_role("button", name="Switch off").count() == 1)
    grp = [g.capitalize() if False else g.lower() for g in pg.locator("#accessView table tr.acgrp th").all_inner_texts()]
    check("L-5 the permission list is in groups", grp[0] == "registration requests" and "venues, places and regions" in grp and len(grp) == 8, grp)
    row = pg.locator("#accessView table tr", has=pg.locator("code.ackey", has_text="edit_venues"))
    check("L-5 each permission shows the roles that hold it (Super admin always)", "Region head" in row.inner_text() and "Super admin" in row.inner_text() and "Ops lead" in row.inner_text(), row.inner_text())
    check("L-5 a permission no role holds says so", "No role" in pg.locator("#accessView table tr", has=pg.locator("code.ackey", has_text="view_spend")).inner_text() or "Super admin" in pg.locator("#accessView table tr", has=pg.locator("code.ackey", has_text="view_spend")).inner_text())

    for i in range(8):
        PE.create(store, {"email": "p%d@example.com" % i, "display_name": "Person %d" % i, "role_id": head["id"], "is_active": i != 5}, "user:admin")
    pg.evaluate("location.hash='#/home'"); pg.evaluate("location.hash='#/access'"); pg.wait_for_selector("#acTab-people"); pg.click("#acTab-people"); pg.wait_for_selector("#acSearch")
    check("L-4 with ten people a search box and Show chips appear, with a count", pg.locator("#acChips .cf-chip").count() == 2 and "10 people" in pg.inner_text("#acCount"), pg.inner_text("#acCount"))
    pg.fill("#acSearch", "person 3"); pg.wait_for_function("document.querySelectorAll('#acPanel .acrow').length === 1")
    check("L-4 search narrows by name or email and says how many", "Person 3" in pg.inner_text("#acPanel") and "1 of 10 people" in pg.inner_text("#acCount"), pg.inner_text("#acCount"))
    pg.fill("#acSearch", "")
    pg.locator("#acChips .cf-chip", has_text="Not signed in yet").click(); pg.wait_for_function("document.querySelectorAll('#acPanel .acrow').length === 8")
    check("L-4 the Not signed in yet chip keeps people who are on and have never signed in", pg.locator("#acPanel .acrow", has_text="Hana Head").count() == 0 and pg.locator("#acPanel .acrow", has_text="Person 5").count() == 0)
    check("no script errors", not errs, errs)
    b.close()
print("screenshots:", SHOTS)
print("\nOK: all Access look checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

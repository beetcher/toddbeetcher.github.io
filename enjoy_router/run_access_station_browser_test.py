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
reg2 = AR.create(store, {"kind": "region", "name": "Longmont", "state_code": "CO", "zip_codes": ["80501"], "is_active": True}, A).data
AR.create(store, {"kind": "state", "name": "Wisconsin", "state_code": "WI", "is_active": True}, A)
wi_reg = AR.create(store, {"kind": "region", "name": "Madison", "state_code": "WI", "zip_codes": ["53703"], "is_active": True}, A).data
old_person = PE.create(store, {"email": "olga@example.com", "display_name": "Olga Old", "role_id": head["id"], "scope_region_id": reg2["id"]}, A).data   # the retired single region

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
    check("the capability table lists all 17, and says which apply inside a territory", pg.locator("#accessView table tr").count() == 18 and "Inside a person's territory" in pg.locator("#accessView table").inner_text() and "Everywhere (from the role)" in pg.locator("#accessView table").inner_text(), pg.locator("#accessView table tr").count())
    check("the super admin role says it does everything", "Everything, including access" in txt)

    # ---- invite
    pg.get_by_role("button", name="Invite someone", exact=True).click(); pg.wait_for_selector("#apEmail")
    check("the invite form offers the roles and the territory editor (no single-region box any more)", set(pg.eval_on_selector_all("#apRole option", "o => o.map(x => x.textContent)")) == {"Region head", "Super admin (super admin)"} and pg.locator("#apRegion").count() == 0 and pg.locator("#agKind").count() == 1)
    check("a new person starts with no territory and says so", "No territory yet" in pg.inner_text("#agBox"))
    pg.fill("#apEmail", "nora@example.com"); pg.fill("#apName", "Nora New"); pg.select_option("#apRole", head["id"])
    # regions of Colorado, defaulted from the role's territorial capabilities (edit_venues)
    check("regions of the chosen state are listed, the capabilities start from the role", pg.locator("#agBox .accaps input[type=checkbox]").evaluate_all("els => els.filter(e => e.checked).map(e => e.value)") == ["edit_venues"], pg.locator("#agBox .accaps input[type=checkbox]").evaluate_all("els => els.filter(e => e.checked).map(e => e.value)"))
    pg.locator('#agBox label', has_text="Boulder").locator("input").check()
    pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Regions in Colorado: Boulder')")
    check("the territory is listed before saving", "edit_venues" in pg.inner_text("#agBox") and "No territory yet" not in pg.inner_text("#agBox"))
    pg.get_by_role("button", name="Send invitation", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Nora New')")
    nora = PE.find_live_by_email(store, "nora@example.com")
    check("the invitation is saved with its grants", bool(nora) and nora["is_active"] and nora["role_id"] == head["id"] and nora["display_name"] == "Nora New" and nora["grants"] == [{"kind": "regions", "state_code": "CO", "region_ids": [reg["id"]], "capabilities": ["edit_venues"]}] and "scope_region_id" not in nora, nora)
    check("it was written by the admin key's actor", nora and nora["created_by"] == "user:admin")
    check("the page confirms and shows the territory", "Added" in pg.inner_text("#accessView") and "Territory: Regions in Colorado: Boulder" in pg.inner_text("#accessView"))
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
    check("an edit that does not touch the territory keeps it", PE.find_live_by_email(store, "nora@example.com")["grants"][0]["region_ids"] == [reg["id"]])
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
    check("the role form offers 16 capabilities and never manage_access", len(labels) == 16 and "manage_access" not in labels and "edit_regions" in labels, labels)
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


    # ---- territory: editing grants
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox")
    check("editing shows the grants a person already holds", "Regions in Colorado: Boulder" in pg.inner_text("#agBox"))
    check("a region already in a grant cannot be picked again", pg.locator('#agBox .acadd label', has_text="Boulder").locator("input").is_disabled() and "already in a grant" in pg.inner_text("#agBox .acadd"))
    pg.locator('#agBox .acadd label', has_text="Longmont").locator("input").check()
    pg.select_option("#agCopy", index=1)
    check("copy-from starts the capabilities from another grant", pg.locator("#agBox .acadd .accaps input[type=checkbox]").evaluate_all("els => els.filter(e => e.checked && ['edit_venues'].includes(e.value)).length") == 1)
    pg.locator('#agBox .acadd .accaps label', has_text="manage_requests").locator("input").check(); pg.fill("#agGroup", "Front Range")
    pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Longmont')")
    pg.select_option("#agKind", "regions"); pg.select_option("#agState", "WI"); pg.wait_for_timeout(100)
    check("changing the state lists that state's regions only", pg.locator("#agBox .acadd .accaps").first.inner_text().strip().startswith("Madison") and "Longmont" not in pg.locator("#agBox .acadd .accaps").first.inner_text())
    pg.get_by_role("button", name="Add this territory", exact=True).click()
    check("a regions grant needs a region picked", "Pick at least one region" in pg.inner_text("#agErr"))
    pg.locator('#agBox .acadd label', has_text="Madison").locator("input").check()
    pg.locator('#agBox .acadd .accaps').nth(1).locator("input:checked").evaluate_all("els => els.forEach(e => e.click())")
    pg.get_by_role("button", name="Add this territory", exact=True).click()
    check("a regions grant needs a capability picked", "Pick at least one capability" in pg.inner_text("#agErr"))
    pg.locator('#agBox .acadd .accaps').nth(1).locator("label", has_text="view_messages").locator("input").check()
    pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Madison')")
    pg.select_option("#agKind", "state"); pg.select_option("#agState", "CO")
    check("choosing a whole state hides the region and capability pickers", not pg.locator("#agBox .acadd .accaps").first.is_visible())
    pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Whole state: Colorado')")
    check("a whole state says it includes the ZIPs no region has claimed", "state administrator" in pg.inner_text("#agBox"))
    pg.select_option("#agKind", "state"); pg.select_option("#agState", "CO")
    pg.get_by_role("button", name="Add this territory", exact=True).click()
    check("the same state twice is refused", "already added" in pg.inner_text("#agErr"))
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Saved')")
    gr = PE.find_live_by_email(store, "nora@example.com")["grants"]
    check("every grant is saved as built: capabilities per grant, a label, a whole state", len(gr) == 4 and {**gr[1], "capabilities": sorted(gr[1]["capabilities"])} == {"kind": "regions", "state_code": "CO", "region_ids": [reg2["id"]], "capabilities": ["edit_venues", "manage_requests"], "group": "Front Range"}
          and gr[2] == {"kind": "regions", "state_code": "WI", "region_ids": [wi_reg["id"]], "capabilities": ["view_messages"]} and gr[3] == {"kind": "state", "state_code": "CO"}, gr)
    check("the person row lists each grant, with its label", "Territory: Regions in Colorado: Longmont [Front Range]" in pg.inner_text("#accessView") and "Territory: Whole state: Colorado" in pg.inner_text("#accessView"))
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox")
    pg.locator("#agBox .acgrant", has_text="Whole state: Colorado").get_by_role("button", name="Remove", exact=True).click()
    check("Remove takes a grant out of the list at once", pg.locator("#agBox .acgrant", has_text="Whole state: Colorado").count() == 0 and pg.locator("#agBox .acgrant").count() == 3)
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Saved')")
    check("the removal is saved", len(PE.find_live_by_email(store, "nora@example.com")["grants"]) == 3)
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox")
    for _ in range(3): pg.locator("#agBox .acgrant").first.get_by_role("button", name="Remove", exact=True).click()
    check("with every grant removed it says there is no territory", "No territory yet" in pg.inner_text("#agBox"))
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Saved')")
    check("removing every grant saves a person with none", "grants" not in PE.find_live_by_email(store, "nora@example.com"))
    check("the row says so in plain words", "Territory: none yet" in pg.locator("#accessView .acrow", has_text="Nora Newman").first.inner_text())
    # editing a territory that is already in the list
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox")
    pg.locator('#agBox .acadd label', has_text="Boulder").locator("input").check(); pg.fill("#agGroup", "Boulder team")
    pg.locator('#agBox .acadd .accaps').nth(1).locator("label", has_text="view_messages").locator("input").check()
    pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Boulder')")
    pg.select_option("#agKind", "state"); pg.select_option("#agState", "WI")
    pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Whole state: Wisconsin')")
    check("every territory in the list has an Edit button", pg.locator("#agBox .acgrant").get_by_role("button", name="Edit", exact=True).count() == 2)
    pg.locator("#agBox .acgrant", has_text="Boulder").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox .acadd:has-text('Edit this territory')")
    check("Edit loads that territory into the form: kind, state, its region ticked, its capabilities, its label", pg.input_value("#agKind") == "regions" and pg.input_value("#agState") == "CO" and pg.locator('#agBox .acadd label', has_text="Boulder").locator("input").is_checked() and not pg.locator('#agBox .acadd label', has_text="Boulder").locator("input").is_disabled()
          and pg.locator("#agBox .acadd .accaps").nth(1).locator("input:checked").evaluate_all("els => els.map(e => e.value)") == ["edit_venues", "view_messages"] and pg.input_value("#agGroup") == "Boulder team", pg.input_value("#agGroup"))
    check("while editing, the button says Save and there is a way out", pg.get_by_role("button", name="Save this territory", exact=True).count() == 1 and pg.get_by_role("button", name="Cancel editing", exact=True).count() == 1 and pg.get_by_role("button", name="Add this territory", exact=True).count() == 0)
    pg.locator('#agBox .acadd .accaps').nth(1).locator("label", has_text="manage_requests").locator("input").check()
    pg.locator('#agBox .acadd label', has_text="Boulder").locator("input").uncheck(); pg.locator('#agBox .acadd label', has_text="Longmont").locator("input").check(); pg.fill("#agGroup", "Longmont team")
    pg.get_by_role("button", name="Save this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Longmont team')")
    check("saving an edit replaces that territory (still two), with the new region, capabilities and label", pg.locator("#agBox .acgrant").count() == 2 and "Regions in Colorado: Longmont [Longmont team]" in pg.inner_text("#agBox") and "Boulder" not in pg.inner_text("#agBox .acgrant:first-of-type") and "manage_requests" in pg.inner_text("#agBox"), pg.inner_text("#agBox"))
    check("the form goes back to adding", pg.get_by_role("button", name="Add this territory", exact=True).count() == 1)
    pg.locator("#agBox .acgrant", has_text="Wisconsin").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox .acadd:has-text('Edit this territory')")
    check("editing a whole-state territory loads it as a whole state", pg.input_value("#agKind") == "state" and pg.input_value("#agState") == "WI")
    pg.select_option("#agState", "CO"); pg.get_by_role("button", name="Save this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Whole state: Colorado')")
    check("a whole state can be changed to another state", pg.locator("#agBox .acgrant").count() == 2 and "Whole state: Wisconsin" not in pg.inner_text("#agBox"))
    pg.locator("#agBox .acgrant", has_text="Longmont").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox .acadd:has-text('Edit this territory')")
    pg.select_option("#agKind", "all"); pg.get_by_role("button", name="Cancel editing", exact=True).click()
    check("Cancel editing changes nothing", pg.locator("#agBox .acgrant").count() == 2 and "Longmont team" in pg.inner_text("#agBox") and pg.get_by_role("button", name="Add this territory", exact=True).count() == 1)
    pg.locator("#agBox .acgrant", has_text="Longmont").get_by_role("button", name="Remove", exact=True).click()
    check("removing leaves no half-open edit form", pg.get_by_role("button", name="Save this territory", exact=True).count() == 0 and pg.locator("#agBox .acgrant").count() == 1)
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Saved')")
    check("the edited territory is saved on the server", PE.find_live_by_email(store, "nora@example.com")["grants"] == [{"kind": "state", "state_code": "CO"}], PE.find_live_by_email(store, "nora@example.com").get("grants"))
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox"); pg.locator("#agBox .acgrant").first.get_by_role("button", name="Remove", exact=True).click()
    pg.select_option("#agKind", "all"); pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Whole US')")
    pg.locator("#agBox .acgrant").first.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox .acadd:has-text('Edit this territory')")
    pg.get_by_role("button", name="Save this territory", exact=True).click(); pg.wait_for_timeout(150)
    check("the only whole-US territory can be edited and saved without being refused as a duplicate", pg.locator("#agBox .acgrant").count() == 1 and "already added" not in pg.inner_text("#agBox") and "Whole US" in pg.inner_text("#agBox"))
    pg.locator("#agBox .acgrant").first.get_by_role("button", name="Remove", exact=True).click()
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Saved')")
    # the whole US and the super admin
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox")
    pg.select_option("#agKind", "all"); pg.get_by_role("button", name="Add this territory", exact=True).click(); pg.wait_for_function("document.getElementById('agBox').innerText.includes('Whole US')")
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Territory: Whole US')")
    check("the whole US can be granted", PE.find_live_by_email(store, "nora@example.com")["grants"] == [{"kind": "all"}])
    row("Nora Newman").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox"); pg.locator("#agBox .acgrant").first.get_by_role("button", name="Remove", exact=True).click()
    pg.select_option("#apRole", sup["id"])
    check("picking the super admin role hides the territory editor and says why", "works everywhere" in pg.inner_text("#agBox") and pg.locator("#agKind").count() == 0)
    pg.get_by_role("button", name="Cancel", exact=True).click()
    check("a person's title comes from their territory, not their role", "Title (from their territory): Super admin: everywhere" in row("Todd Beetcher").inner_text() and "Title (from their territory): Region head: 1 region in Colorado" in row("Olga Old").inner_text(), row("Olga Old").inner_text())
    check("Todd's row says everywhere", "Territory: everywhere" in row("Todd Beetcher").inner_text())
    # the retired single region
    check("a person with only the old single region shows it as a territory and says how to convert it", "Territory: Regions in Colorado: Longmont (from the old single-region setting" in row("Olga Old").inner_text(), row("Olga Old").inner_text())
    row("Olga Old").get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_selector("#agBox")
    check("editing starts from the old region as a real grant with the role's capabilities", "Regions in Colorado: Longmont" in pg.inner_text("#agBox") and "edit_venues" in pg.inner_text("#agBox"))
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('accessView').innerText.includes('Saved')")
    olga = PE.find_live_by_email(store, "olga@example.com")
    check("saving converts it: grants set, the retired field gone", olga["grants"] == [{"kind": "regions", "state_code": "CO", "region_ids": [reg2["id"]], "capabilities": ["edit_venues"]}] and "scope_region_id" not in olga, olga)
    # the two views
    PE.update(store, PE.find_live_by_email(store, "nora@example.com")["id"], {"grants": [{"kind": "state", "state_code": "WI"}]}, A)
    pg.select_option("#collPick", "home"); pg.select_option("#collPick", "access"); pg.wait_for_selector("#acTerr")
    t = pg.inner_text("#acTerr")
    check("by region: the whole-US line, the states folded, nothing opened yet", "Whole US: Todd Beetcher" in t and pg.locator("#acTerr details").count() == 2 and pg.locator("#acTerr details[open]").count() == 0, t)
    pg.locator("#acTerr details", has_text="Colorado").first.locator("summary").click(); pg.locator("#acTerr details", has_text="Wisconsin").first.locator("summary").click()
    t = pg.inner_text("#acTerr")
    check("by region: a Colorado region lists who holds it and with what", "Longmont" in t and "Olga Old: edit_venues" in t, t)
    check("by region: a state's administrators are named", "Nora Newman" in pg.locator("#acTerr details", has_text="Wisconsin").first.inner_text())
    check("by region: a region nobody holds says so", "No one is given this region by name." in pg.locator("#acTerr details", has_text="Colorado").first.text_content())
    pg.get_by_role("button", name="By capability", exact=True).click(); pg.wait_for_selector("#acTerr details")
    pg.locator("#acTerr details", has_text="edit_venues").first.locator("summary").click()
    t = pg.locator("#acTerr details", has_text="edit_venues").first.inner_text()
    check("by capability: who holds it and where", "Olga Old: Longmont (CO)" in t and "Todd Beetcher: everywhere" in t, t)
    pg.locator("#acTerr details", has_text="manage_requests").first.locator("summary").click()
    check("by capability: a whole-state grant holds every territorial capability there", "Nora Newman: all of Wisconsin" in pg.locator("#acTerr details", has_text="manage_requests").first.inner_text())
    check("the capability list in this view is only the territorial ones", pg.locator("#acTerr details").count() == 12)
    pg.get_by_role("button", name="By region", exact=True).click()

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

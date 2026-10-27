#!/usr/bin/env python3
"""Browser test (P-46): the Activity station and the Change history buttons. Real doors with an in-memory store wrapped in the ActivityStore,
headless Chromium, signed in with the admin key. Changes are made through the door, as the Console makes them, and the station must show them.
Checks: the station and its tile; entries newest first; created / edited / deleted read in plain words; old to new; a personal change shows no value;
the filters and the search; Change history on a venue card opens the station on that one venue; Change history on an entry does the same; the
manual; phone width; no script errors. Screenshots go to SHOTS (default: a temp folder) for a human to look at.
Run from enjoy_router/:  python3 run_activity_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from crud import individuals_service as IND
from crud.activity_store import ActivityStore
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SHOTS = pathlib.Path(os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="activity_shots_")); SHOTS.mkdir(parents=True, exist_ok=True)
inner = MemoryDocStore(""); store = ActivityStore(inner); limiter = make_failure_limiter(); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def door(coll, op, args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    return r
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))

# ---- a little history, made the way the Console makes it
v1 = door("venues", "create", {"data": {"name": "Trident Booksellers", "slug": "trident", "status": "inactive", "is_public_venue": True}}).body["data"]
v2 = door("venues", "create", {"data": {"name": "Pearl Street Library", "slug": "pearl", "status": "inactive", "is_public_venue": True}}).body["data"]
r = door("venues", "update", {"id": v1["id"], "changes": {"name": "Trident Books & Cafe", "phone": "+13035551234"}, "expected_updated_at": v1["updated_at"]})
assert r.body.get("ok"), r.body
r = door("venues", "soft_delete", {"id": v2["id"]})
assert r.body.get("ok"), r.body
pr = IND.create(store, {"given_name": "Zephyrina", "family_name": "Quillfeather"}, "user:admin")
assert pr.ok, pr.problems
IND.update(store, pr.data["id"], {"name_to_use": "Zeph"}, "user:admin")

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 1000}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("Activity is a station on the home page, marked admin", pg.locator('#stationTiles .tile[data-go="activity"]').count() == 1 and "admin" in pg.locator('#stationTiles .tile[data-go="activity"]').inner_text().lower())
    pg.screenshot(path=str(SHOTS / "00_home.png"))
    pg.select_option("#collPick", "activity"); pg.wait_for_selector("#activityView .avrow")
    txt = pg.inner_text("#activityView")
    n = pg.locator("#activityView .avrow").count()
    check("entries are listed (every write left one)", n >= 6, n)
    first = pg.locator("#activityView .avrow").first.inner_text()
    check("the newest entry is first (the change to the person)", "Person" in first and "Edited" in first, first[:120])
    check("a venue edit reads old to new", "Trident Booksellers" in txt and "Trident Books & Cafe" in txt and "Edited" in txt)
    check("a delete reads as Deleted, a create as Created", "Deleted" in txt and "Created" in txt)
    check("who made it is in plain words", "Admin key" in txt)
    check("a personal change names the field and holds no value", "not recorded" in txt and "Zephyrina" not in txt and "Quillfeather" not in txt and "Zeph" not in txt.replace("Zephyrina", ""), txt[:400])
    check("a venue's phone is personal contact data: the change is listed and the number is not", "Phone" in txt and "+13035551234" not in txt and "3035551234" not in txt)
    pg.screenshot(path=str(SHOTS / "01_station.png"), full_page=True)

    # ---- filters
    pg.select_option("#avMode", "action"); pg.select_option("#avValue", "deleted"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 1")
    check("filter: only deletes", "Deleted" in pg.inner_text("#activityView .avrow") and "Pearl Street Library" in pg.inner_text("#activityView .avrow"))
    pg.select_option("#avMode", "record_type"); pg.select_option("#avValue", "venue"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 4")
    check("filter: one kind of record", "Person ·" not in pg.inner_text("#avList"))
    pg.select_option("#avMode", "all"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length >= 6")
    pg.fill("#avSearch", "pearl"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 2")
    check("search narrows what is on the screen", "Pearl Street Library" in pg.inner_text("#avList") and "Trident" not in pg.inner_text("#avList") and "of" in pg.inner_text("#avCount"))
    pg.fill("#avSearch", "no such thing xyz"); pg.wait_for_selector("#avList >> text=Nothing matches")
    check("a search that finds nothing says so", True)
    pg.fill("#avSearch", "")

    # ---- Change history on an entry
    pg.locator("#activityView .avrow", has_text="Trident Books & Cafe").get_by_role("button", name="Change history").click()
    pg.wait_for_selector("#activityView .avfocus")
    check("Change history on an entry opens that one record", "Change history" not in pg.inner_text("#activityView .avfocus") and "History of" in pg.inner_text("#activityView .avfocus"))
    rows = pg.locator("#activityView .avrow")
    check("...and lists only that record, oldest change included", rows.count() == 2 and all("Trident" in t for t in rows.all_inner_texts()), rows.all_inner_texts())
    pg.screenshot(path=str(SHOTS / "02_one_record.png"), full_page=True)
    pg.get_by_role("button", name="Show everything").click(); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length >= 6")

    # ---- Change history on a venue card
    pg.select_option("#collPick", "venues"); pg.wait_for_selector("#mainList li, #vList li, #venuesView li")
    pg.locator("#venuesView li", has_text="Trident").first.locator("button.head").click()
    btn = pg.locator("#venuesView li", has_text="Trident").first.get_by_role("button", name="Change history")
    check("a venue card has a Change history button", btn.count() == 1)
    pg.screenshot(path=str(SHOTS / "03_venue_card.png"), full_page=True)
    btn.click(); pg.wait_for_selector("#activityView .avfocus")
    check("it opens the station on that venue", pg.locator("#activityView .avrow").count() == 2 and "Trident" in pg.inner_text("#activityView .avfocus"), pg.inner_text("#activityView .avfocus"))
    check("the address is the activity page", pg.evaluate("location.hash") == "#/activity")

    # ---- the manual
    pg.select_option("#collPick", "home")
    pg.click("#helpOpen"); pg.click('#overlayBtns button[data-m="activity"]'); pg.wait_for_selector("#manual:not([hidden])")
    check("the manual explains the station", "Personal details are never copied" in pg.inner_text("#manual") and "station 14" in pg.inner_text("#manual").lower())
    pg.screenshot(path=str(SHOTS / "04_manual.png"))

    # ---- phone width
    pg.keyboard.press("Escape")
    pg.set_viewport_size({"width": 390, "height": 800}); pg.goto(PAGE + "#/activity")
    pg.wait_for_selector("#activityView .avrow")
    check("phone width: nothing scrolls sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    pg.screenshot(path=str(SHOTS / "05_phone.png"), full_page=True)
    check("no script errors", not errs, errs)
    b.close()

print("screenshots:", SHOTS)
print("\nOK: all Activity browser checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

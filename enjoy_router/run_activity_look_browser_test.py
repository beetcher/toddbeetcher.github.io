#!/usr/bin/env python3
"""Browser test (Activity look, steps L-1 to L-6): entries read as three short lines in plain words, lists are shortened, details are built when opened,
then (as the steps land) head, chips, day headings, address filters, burst grouping, paging, links and states. Entries are written straight into the
log store so the page can be tested with many entries. Run from enjoy_router/:  python3 run_activity_look_browser_test.py"""
import sys, json, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone, timedelta
from crud.activity_store import ActivityStore
from crud.memory_doc_store import MemoryDocStore
from crud import activity_log as AL
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)
PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SHOTS = pathlib.Path(os.environ.get("SHOTS") or tempfile.mkdtemp(prefix="activity_look_")); SHOTS.mkdir(parents=True, exist_ok=True)
inner = MemoryDocStore(""); store = ActivityStore(inner); limiter = make_failure_limiter(); fails = []
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
SEQ = [0]
def seed(collection, type_name, action, rid, actor, when, changes, label=None, related=None):
    SEQ[0] += 1
    e = AL._entry(collection, type_name, action, rid, actor, when.strftime("%Y-%m-%dT%H:%M:%SZ"), changes, 0, related or [rid], label, int(when.timestamp() * 1000) * 1000 + SEQ[0])
    inner.create(AL.ACTIVITY.name, e["id"], e); return e
def ch(field, old=None, new=None): 
    c = {"field": field}
    if old is not None: c["old_value"] = json.dumps(old)
    if new is not None: c["new_value"] = json.dumps(new)
    return c
NOW = datetime.now(timezone.utc).replace(microsecond=0)
ZIPS = ["80%03d" % i for i in range(59)]

# ---- the look data
seed("venues", "venue", "created", "v-1", "system:discovery_run", NOW - timedelta(minutes=5),
     [ch("name", None, "Panera Bread"), ch("postal_code", None, "55901"), ch("has_wifi", None, True), ch("model_name", None, "gpt-x"), ch("found_at", None, "2026-10-27T10:00:00Z"), ch("zip_codes", None, ZIPS)], "Panera Bread")
seed("venues", "venue", "edited", "v-2", "web:enjoy", NOW - timedelta(minutes=9), [ch("name", "Old Library", "New Library")], "New Library")
seed("venues", "venue", "edited", "v-3", "system:unattributed", NOW - timedelta(minutes=12), [ch("phone", None, None)], None)
seed("venues", "venue", "edited", "v-4", "user:admin", NOW - timedelta(minutes=14), [ch(f, "a", "b") for f in ["name", "phone", "email", "website_url", "allows_minors"]], "Big Edit")

LOCAL_MID = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
seed("access_persons", "access_person", "edited", "ap-1", "user:admin", NOW - timedelta(minutes=20), [ch("is_active", True, False)], "Eli Wood")
seed("scheduled_classes", "scheduled_class", "created", "c-1", "web:enjoy", LOCAL_MID - timedelta(hours=12), [ch("title", None, "Intro class")], "Intro class")
seed("scheduled_classes", "scheduled_class", "deleted", "c-2", "user:admin", LOCAL_MID - timedelta(days=3, hours=-12), [ch("deleted_by", None, "user:admin")], "Old class")
seed("venues", "venue", "edited", "v-9", "user:admin", LOCAL_MID - timedelta(days=40), [ch("name", "A", "B")], "Ancient Cafe")
TOTAL = 8

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_admin", admin_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    pg.evaluate("location.hash='#/activity'"); pg.wait_for_selector("#activityView .avrow")
    rows = pg.locator("#activityView .avrow")
    first = rows.nth(0).inner_text()

    # ===== L-1 entry summary
    check("L-1 an entry has a who/what/when summary: kind and name, when and who, what changed", "Venue · Panera Bread" in first and "Created with 6 fields" in first and "Automatic job (discovery run)" in first, first)
    check("L-1 details are closed and not yet built (a closed entry holds no field list)", rows.nth(0).locator("details li").count() == 0 and rows.nth(0).locator("details[open]").count() == 0)
    rows.nth(0).locator("summary").click(); rows.nth(0).locator("details li").first.wait_for()
    opened = rows.nth(0).inner_text()
    check("L-1 opening Details builds the lines in plain words", all(t in opened for t in ["ZIP code: 55901", "Wi-Fi: Yes", "AI model: gpt-x", "Found on:", "First" if False else "Name: Panera Bread"]), opened)
    check("L-1 no engine field name on screen", not any(t in opened for t in ["postal_code", "has_wifi", "model_name", "found_at", "zip_codes"]))
    check("L-1 a 59-item list reads '59 ZIP codes' with Show all", "59 ZIP codes" in opened and "80058" not in opened.replace("Show all", ""), opened)
    rows.nth(0).get_by_role("button", name="Show all").click()
    check("L-1 Show all reveals the list", "80058" in rows.nth(0).inner_text())
    check("L-1 a one-field edit shows was and now inline", "Old Library" in pg.inner_text("#avList") and "New Library" in pg.inner_text("#avList") and "→" in pg.inner_text("#avList"))
    check("L-1 the website form and the automatic job read in plain words", "Website form" in pg.inner_text("#avList") and "Automatic job" in pg.inner_text("#avList"))
    check("L-1 an entry with no name says so, not a ref code", "Record without a name" in pg.inner_text("#avList") and "ref " not in pg.inner_text("#avList"))
    big = rows.filter(has_text="Big Edit")
    check("L-1 a five-field edit names the fields and folds the rest", "Changed Name, Phone, Email and 2 more" in big.inner_text() and big.locator("li").count() == 0, big.inner_text())
    pg.screenshot(path=str(SHOTS / "L1_desktop.png"), full_page=True)

    # ===== L-2 shared head and layout
    head = pg.locator("#activityView .phead")
    check("L-2 the head is the shared one: title, count line, Last checked, Refresh on the right", head.count() == 1 and "Activity" in head.inner_text() and "8 entries" in pg.inner_text("#avCount") and "Last checked" in pg.inner_text("#avChecked") and pg.locator("#activityView .phead .actions button.btn-secondary", has_text="Refresh").count() == 1, head.inner_text())
    check("L-2 no inline style block (the rules are in console.css)", pg.locator("style#activityStyle").count() == 0)
    left = pg.evaluate("document.querySelector('#activityView .acv').getBoundingClientRect().left")
    pg.evaluate("location.hash='#/places'"); pg.wait_for_selector("#placesView:not([hidden])"); pleft = pg.evaluate("document.querySelector('#placesView h2, #placesView .ptitle, #placesView .bar').getBoundingClientRect().left")
    check("L-2 the page starts at the same left edge as the other stations", abs(left - pleft) <= 2, (left, pleft))
    pg.evaluate("location.hash='#/activity'"); pg.wait_for_selector("#activityView .avrow")
    ys = pg.evaluate("[...document.querySelectorAll('#avList .avrow')].slice(0, 2).map(r => Math.round(r.getBoundingClientRect().top))")
    check("L-2 two entries sit side by side on a wide screen", len(ys) == 2 and ys[0] == ys[1], ys)
    pg.click("#activityView .phead button:has-text('Refresh')"); pg.wait_for_selector("#activityView .avrow")
    check("L-2 Refresh keeps the list", pg.locator("#activityView .avrow").count() == TOTAL)
    # ===== L-3 chips, date chips, day headings, filters in the address
    def chip(name): return pg.locator("#avChips .cf-chip", has=pg.locator(".cf-lab", has_text=name)).first
    def opt(value): return pg.locator("#avChips .cf-pop:not([hidden]) label.cf-opt", has=pg.locator("input[value='%s']" % value))
    def pick(name, value):
        chip(name).click(); opt(value).click(); pg.wait_for_timeout(60)
        d = pg.get_by_role("button", name="Done with %s filter" % name)
        if d.count() and d.first.is_visible(): d.first.click()
    check("L-3 four chips: What, Change, When, Who", pg.locator("#avChips .cf-chip").count() == 4 and [pg.locator("#avChips .cf-chip .cf-lab").nth(i).inner_text() for i in range(4)] == ["What", "Change", "When", "Who"])
    heads = pg.locator("#avList h3.avday").all_inner_texts()
    check("L-3 entries sit under day headings: Today, Yesterday, then dated days, newest first", heads[0] == "Today" and heads[1] == "Yesterday" and len(heads) >= 4, heads)
    pick("What", "access"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 1")
    check("L-3 What: Access shows only the access change", "Eli Wood" in pg.inner_text("#avList") and "1 of 8 entries" in pg.inner_text("#avCount"), pg.inner_text("#avCount"))
    check("L-3 the choice is in the address", pg.evaluate("location.hash") == "#/activity?kind=access", pg.evaluate("location.hash"))
    pg.locator("#avChips .cf-clearall").click(); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === %d" % TOTAL)
    check("L-3 Clear all brings everything back and empties the address", pg.evaluate("location.hash") == "#/activity")
    pick("When", "today"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 5")
    check("L-3 When: Today hides yesterday and older", "Intro class" not in pg.inner_text("#avList") and pg.locator("#avList h3.avday").all_inner_texts() == ["Today"], pg.locator("#avList h3.avday").all_inner_texts())
    pg.locator("#avChips .cf-clearall").click(); pick("When", "d7"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 7")
    check("L-3 When: Last 7 days drops the 40-day-old change", "Ancient Cafe" not in pg.inner_text("#avList") and "Old class" in pg.inner_text("#avList"))
    pg.locator("#avChips .cf-clearall").click(); pick("Change", "created"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 6")
    check("L-3 Change: unticking Created hides the two created entries", "Intro class" not in pg.inner_text("#avList") and "Panera" not in pg.inner_text("#avList"))
    pg.locator("#avChips .cf-clearall").click()
    pg.evaluate("location.hash='#/home'"); pg.evaluate("location.hash='#/activity?kind=places&q=panera'"); pg.wait_for_function("document.querySelectorAll('#activityView .avrow').length === 1")
    check("L-3 an address with a choice and a search opens already narrowed", pg.input_value("#avSearch") == "panera" and "Panera Bread" in pg.inner_text("#avList") and "What: Venues and places" in pg.inner_text("#avChips"), pg.inner_text("#avChips"))
    pg.fill("#avSearch", "zzzz"); pg.wait_for_selector("#avList >> text=No entries match these filters.")
    check("L-3 nothing matching says so (not 'nothing recorded')", "Nothing has been recorded" not in pg.inner_text("#avList"))
    pg.fill("#avSearch", ""); pg.locator("#avChips .cf-clearall").click()
    pg.set_viewport_size({"width": 390, "height": 900}); pg.evaluate("location.hash='#/activity'"); pg.wait_for_selector("#activityView .avrow")
    check("L-3 phone width: the chips fit, nothing scrolls sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    pg.set_viewport_size({"width": 1440, "height": 1000})
    check("no script errors", not errs, errs)
    b.close()
print("screenshots:", SHOTS)
print("\nOK: all Activity look checks pass" if not fails else "\nFAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)

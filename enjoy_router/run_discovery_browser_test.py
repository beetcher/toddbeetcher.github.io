#!/usr/bin/env python3
"""Browser test: the Discovery station. Real admin door and Discovery door over an in-memory store (seeded the way the live system is), a fake AI,
headless Chromium. Covers the banner, the Run tab (pickers, estimate, Go, progress, review), Runs (open, withdraw), and Settings (models, areas,
types, prompt draft and publish, limits). Nothing leaves this computer.
Run from enjoy_router/:  python3 run_discovery_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timedelta, timezone
from crud.memory_doc_store import MemoryDocStore
from crud import venues_crud as VE, discovery_runs_crud as RU
from crud_endpoint import handle_admin
from console import make_failure_limiter
from discovery.contract import ProviderResult
from discovery.memory_stores import FakeProvider
from discovery_door import handle_discovery
from launch_discovery import wiring, zip_table
import seed_discovery as SEED
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

PAGE = (HERE.parent / "console" / "index.html").as_uri()
KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
SECRET = "sk-REAL-LOOKING-SECRET-1234567890"
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

# the ZIP table the live system will have (a few Colorado ZIPs and one Texas ZIP is enough here)
zip_table.set_table({z: ["CO", 39.6 + 0.12 * n, -105.4 + 0.15 * (n % 4), "Boulder"] for n, z in enumerate(("80301", "80302", "80303", "80304", "80305", "80027", "80026", "80501", "80503", "80504"))}
                    | {"78701": ["TX", 30.2, -97.7, "Austin"], "78702": ["TX", 30.3, -97.7, "Austin"]})
store, limiter, dlimiter = MemoryDocStore(""), make_failure_limiter(), make_failure_limiter()
clock = [0]
def tick():
    clock[0] += 3
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=clock[0])
def seed_call(coll, op, **args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter, tick())
    return r.status, r.body
quiet = lambda *_: None
SEED.seed(seed_call, say=quiet); SEED.seed(seed_call, say=quiet, regions=True)
ENV = {"ICDT_DISCOVERY_MODE": "live", "ICDT_CLAUDE_KEY": SECRET}
def ai(req):
    def item(**kw): return {k: {"value": v, "mark": "sure", "source_url": "https://example.org/" + k} for k, v in kw.items()}
    good = item(name="Ozo Coffee", operator="Ozo Coffee Company", city="Boulder", state="CO", is_public_venue=True, street="1825 Pearl St", website_url="https://ozo.example.org")
    good["phone"] = {"value": "303-555-0101", "mark": "verify"}
    noaddr = item(name="Corner Table Cafe", operator="Corner Table LLC", city="Boulder", state="CO", is_public_venue=True)
    return ProviderResult("ok", text=json.dumps({"venues": [good, noaddr]}), input_tokens=500, output_tokens=300)
engine = wiring.build_engine(store, ENV, providers={"gemini": FakeProvider("gemini", ai)}, clock=tick)

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
def admin_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_admin(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, limiter, tick())
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def disc_route(route):
    q = route.request
    if q.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    r = handle_discovery(q.method, q.headers.get("authorization", ""), (q.post_data or "").encode(), KEY, "v", store, engine, ENV, dlimiter, tick())
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
def recs(coll, **f):
    return SEED._records(seed_call, coll, **f)

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", admin_route); pg.route("**/enjoy_discovery", disc_route)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE); pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#homeView:not([hidden])")
    check("Discovery is a station on the home page", pg.locator("#stationTiles .tile", has_text="Discovery").count() == 1)
    pg.select_option("#collPick", "discovery"); pg.wait_for_selector("#dModel")
    ban = pg.locator("#dBanner").inner_text()
    check("the banner says the mode and the ZIP table", "LIVE" in ban and "ZIP table: 12 ZIPs" in ban, ban)
    check("only models switched on are offered", pg.locator("#dModel option").all_inner_texts() == ["Gemini 3.5 Flash-Lite (Google search)", "Gemini 3.8 Flash (Google search)"]
          or len(pg.locator("#dModel option").all_inner_texts()) == 2, pg.locator("#dModel option").all_inner_texts())
    check("only states switched on are offered", pg.locator("#dState option").all_inner_texts() == ["Colorado"])
    regs = pg.locator("#dAreas label").all_inner_texts()
    check("the whole state and its regions are offered", len(regs) == 4 and "Boulder" in " ".join(regs), regs)
    check("the four starting kinds of place are offered", pg.locator("#dTypes label").count() == 4)
    check("the starting limits are 10", pg.input_value("#dMax") == "10" and pg.input_value("#dCap") == "10")
    check("Go starts disabled", pg.locator("#dGo").is_disabled())
    pg.click("#dEstimate")
    check("an estimate with nothing chosen says what to choose", "Choose where to look" in pg.locator("#dMsg").inner_text(), pg.locator("#dMsg").inner_text())
    pg.locator("#dAreas label", has_text="Boulder").locator("input").check()
    pg.locator("#dTypes label", has_text="coffee shops").locator("input").check()
    pg.click("#dEstimate"); pg.wait_for_selector("#dQuote .dcard")
    qt = pg.locator("#dQuote").inner_text()
    check("the estimate shows calls, a cost range, the cap and the prompt version", "1 AI call" in qt and "$" in qt and "Your cap is $0.10" in qt and "Prompt version 1" in qt, qt)
    pg.locator("#dQuote summary").click()
    ptxt = pg.locator("#dQuote .dprompt").first.inner_text()
    check("the exact prompt text can be read before Go", "Boulder" in ptxt and "coffee" in ptxt.lower(), ptxt[:200])
    check("Go is enabled after an estimate", pg.locator("#dGo").is_enabled())
    pg.fill("#dCap", "9")
    check("changing a choice throws the estimate away", pg.locator("#dGo").is_disabled() and pg.locator("#dQuote .dcard").count() == 0)
    pg.click("#dEstimate"); pg.wait_for_selector("#dQuote .dcard"); pg.click("#dGo")
    pg.wait_for_function("document.getElementById('dRunLine') && document.getElementById('dRunLine').textContent === 'Finished.'", timeout=20000)
    summ = pg.locator("#dProgress").inner_text()
    check("a finished run says what it found, saved and spent", "Found 2, saved 2" in summ and "need attention" in summ and "Spent" in summ, summ)
    runs = RU.list(store, None, "-created_at", 50).data["records"]
    check("one run record exists, finished", len(runs) == 1 and runs[0]["status"] == "finished" and runs[0]["spend_cap_cents"] == 9, runs and runs[0]["status"])
    pg.get_by_role("button", name="Review this run").click(); pg.wait_for_selector("#dCands .dcard")
    cards = pg.locator("#dCands .dcard")
    check("both candidates are listed for review", cards.count() == 2)
    ozo = pg.locator("#dCands .dcard", has_text="Ozo Coffee")
    check("a candidate is Inactive with facts and marks in words", "Inactive" in ozo.inner_text() and "Sure" in ozo.inner_text() and "Check" in ozo.inner_text(), ozo.inner_text())
    check("a source link is shown and is safe", ozo.locator("a[target=_blank][rel*=noopener]").count() >= 1)
    noadr = pg.locator("#dCands .dcard", has_text="Corner Table")
    check("a venue with no street address is flagged", "No street address" in noadr.inner_text() and "Unknown" in noadr.locator("tr", has_text="Street address").inner_text(), noadr.inner_text())
    check("an unknown fact looks different from a sure one (dashed chip)", noadr.locator("tr", has_text="Street address").locator(".dchip.unknown").count() == 1 and ozo.locator(".dchip.sure").count() >= 1)
    check("the page never shows a key", SECRET not in pg.content())
    check("the run's exact prompts can be opened", pg.locator("#dRuns details summary", has_text="exact prompt").count() == 1)
    # withdraw (two presses)
    pg.click("#dWithdraw"); check("withdraw asks twice", "Really" in pg.locator("#dWithdraw").inner_text())
    pg.click("#dWithdraw"); pg.wait_for_function("document.getElementById('dRuns').textContent.indexOf('Withdrawn') >= 0")
    pg.wait_for_function("document.getElementById('dCands') && document.getElementById('dCands').textContent.indexOf('Removed') >= 0")
    made = RU.list(store, None, "-created_at", 5).data["records"][0]["created_venue_ids"]
    gone = [VE.get(store, i, include_deleted=True).data for i in made]
    check("withdraw takes the candidates back", len(made) == 2 and all(v.get("deleted_at") for v in gone) and "Removed" in pg.locator("#dCands").inner_text(), [v.get("deleted_at") for v in gone])
    pg.click("#dTabs button[data-tab=runs]"); pg.wait_for_selector("#dRuns .dcard")
    check("the Runs list shows the run as Withdrawn", "Withdrawn" in pg.locator("#dRuns").inner_text())

    # ---- settings
    pg.click("#dTabs button[data-tab=settings]"); pg.wait_for_selector("#dSubBody .dcard")
    check("Models lists all five, with key status in words", pg.locator("#dSubBody .dcard[data-id]").count() == 5 and "key ICDT_CLAUDE_KEY is set" in pg.locator("#dSubBody").inner_text()
          and "NOT set" in pg.locator("#dSubBody").inner_text())
    hk = [m for m in recs("discovery_models") if m["model_name"] == "claude-haiku-5-5"][0]
    pg.locator('#dSubBody .dcard[data-id="%s"] .dsw' % hk["id"]).click()
    pg.wait_for_function("document.querySelector('#dSubBody .dcard[data-id=\"%s\"] .dsw').getAttribute('aria-checked') === 'true'" % hk["id"])
    check("switching a model on is saved", [m for m in recs("discovery_models") if m["id"] == hk["id"]][0]["is_active"] is True)
    pg.click("#dAdd_discovery_models")
    pg.fill("#dF_discovery_models_model_name", "gemini-x-test"); pg.fill("#dF_discovery_models_label", "Gemini test"); pg.select_option("#dF_discovery_models_provider", "gemini")
    pg.fill("#dF_discovery_models_price_input_per_million_cents", "5"); pg.fill("#dF_discovery_models_price_output_per_million_cents", "9")
    pg.get_by_role("button", name="Add", exact=True).click(); pg.wait_for_function("document.getElementById('dSubBody').textContent.indexOf('Gemini test') >= 0")
    check("a new model is a record, nothing else", any(m["label"] == "Gemini test" for m in recs("discovery_models")))
    pg.click("#dAdd_discovery_models"); pg.fill("#dF_discovery_models_label", "Broken")
    pg.get_by_role("button", name="Add", exact=True).click(); pg.wait_for_selector("#dSubBody form .msg:not(:empty)")
    check("a bad model is refused with words, not codes", "Required" in pg.locator("#dSubBody form .msg").inner_text() or "not valid" in pg.locator("#dSubBody form .msg").inner_text(), pg.locator("#dSubBody form .msg").inner_text())
    pg.get_by_role("button", name="Cancel").click()

    pg.click("#dSubs button[data-sub=areas]"); pg.wait_for_selector("#dStateFind")
    pg.fill("#dStateFind", "tex"); check("find a state narrows the 51", pg.locator("#dSubBody .dgrid .dcard").count() == 1)
    pg.locator("#dSubBody .dgrid .dcard .dsw").click()
    pg.wait_for_function("document.querySelectorAll('#dSubBody .dgrid .dcard .dsw[aria-checked=true]').length === 1")
    tx = [a for a in recs("discovery_areas", kind="state") if a["state_code"] == "TX"][0]
    check("switching Texas on is saved", tx["is_active"] is True)
    pg.click("#dAdd_discovery_areas"); pg.fill("#dF_discovery_areas_name", "Test region"); pg.select_option("#dF_discovery_areas_state_code", "TX"); pg.fill("#dF_discovery_areas_zip_codes", "80301")
    pg.get_by_role("button", name="Add", exact=True).click(); pg.wait_for_selector("#dSubBody form .msg:not(:empty)")
    check("a ZIP in the wrong state is refused in words", "not in this state" in pg.locator("#dSubBody form .msg").inner_text(), pg.locator("#dSubBody form .msg").inner_text())
    pg.fill("#dF_discovery_areas_zip_codes", "78701,\n78702"); pg.get_by_role("button", name="Add", exact=True).click()
    pg.wait_for_function("document.getElementById('dSubBody').textContent.indexOf('Test region') >= 0")
    check("a region of ZIPs is saved", any(a["name"] == "Test region" and a["zip_codes"] == ["78701", "78702"] for a in recs("discovery_areas", kind="region")))

    pg.click("#dSubs button[data-sub=types]"); pg.wait_for_selector("#dAdd_discovery_types")
    pg.click("#dAdd_discovery_types"); pg.fill("#dF_discovery_types_label", "Bookstores"); pg.fill("#dF_discovery_types_key", "bookstores"); pg.fill("#dF_discovery_types_search_hint", "Independent bookstores with a cafe or reading nook.")
    pg.get_by_role("button", name="Add", exact=True).click(); pg.wait_for_function("document.getElementById('dSubBody').textContent.indexOf('Bookstores') >= 0")
    check("a new kind of place is a record", any(t["key"] == "bookstores" and t["finder_key"] == "venue" for t in recs("discovery_types")))

    pg.click("#dSubs button[data-sub=prompt]"); pg.wait_for_selector("#dPEdit")
    pt = pg.locator("#dSubBody").inner_text()
    check("the prompt tab shows the words in use and the allowed placeholders", "version 1" in pt and "{territory}" in pt and "{max_results}" in pt, pt[:300])
    pg.click("#dPEdit"); pg.wait_for_selector("#dPText")
    cur = pg.input_value("#dPText")
    pg.fill("#dPText", cur + "\nPrefer places with a quiet back room. {bogus}"); pg.click("#dPSave"); pg.wait_for_function("document.querySelector('#dSubBody .msg').textContent.length > 0")
    check("a made-up {placeholder} is refused in words", "does not supply" in pg.locator("#dSubBody .msg").inner_text() or "not valid" in pg.locator("#dSubBody .msg").inner_text(), pg.locator("#dSubBody .msg").inner_text())
    pg.fill("#dPText", cur + "\nPrefer places with a quiet back room."); pg.click("#dPPublish"); pg.wait_for_selector("#dPEdit")
    check("publishing makes version 2 the one in use", "version 2" in pg.locator("#dSubBody").inner_text() and "Earlier versions (1)" in pg.locator("#dSubBody").inner_text())
    pg.click("#dTabs button[data-tab=run]"); pg.select_option("#dModel", label="Gemini 3.8 Flash (Google search)")
    check("a model switched on in Settings is offered on the Run tab", "Claude Haiku 5.5" in pg.locator("#dModel option").all_inner_texts())
    pg.locator("#dAreas label", has_text="Boulder").locator("input").check(); pg.locator("#dTypes label", has_text="coffee shops").locator("input").check()
    pg.click("#dEstimate"); pg.wait_for_selector("#dQuote .dcard"); pg.locator("#dQuote summary").click()
    check("the next estimate uses the new wording", "quiet back room" in pg.locator("#dQuote .dprompt").first.inner_text())

    pg.click("#dTabs button[data-tab=settings]"); pg.click("#dSubs button[data-sub=limits]"); pg.click("#dEditLimits")
    pg.fill("#dF_discovery_settings_max_spend_cap_cents", "50"); pg.fill("#dF_discovery_settings_default_spend_cap_cents", "20")
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_function("document.getElementById('dSubBody').textContent.indexOf('$0.50') >= 0")
    st = recs("discovery_settings")[0]
    check("limits are editable and saved", st["max_spend_cap_cents"] == 50 and st["default_spend_cap_cents"] == 20)
    pg.click("#dTabs button[data-tab=run]")
    check("the Run tab picks up the new limits", pg.input_value("#dCap") == "20" and pg.get_attribute("#dCap", "max") == "50")
    pg.click("#dEditLimits") if False else None
    pg.click("#dTabs button[data-tab=settings]"); pg.click("#dEditLimits"); pg.fill("#dF_discovery_settings_default_spend_cap_cents", "90")
    pg.get_by_role("button", name="Save", exact=True).click(); pg.wait_for_selector("#dSubBody form .msg:not(:empty)")
    check("a starting cap above the maximum is refused", pg.locator("#dSubBody form .msg").inner_text() != "", pg.locator("#dSubBody form .msg").inner_text())

    # ---- mode off: the banner says so and Go cannot be pressed
    ENV["ICDT_DISCOVERY_MODE"] = "off"
    pg.click("#dRefresh"); pg.wait_for_function("document.getElementById('dBanner').textContent.indexOf('OFF') >= 0")
    check("with the server off, the banner says so", "nothing can run" in pg.locator("#dBanner").inner_text())
    pg.click("#dTabs button[data-tab=run]"); pg.select_option("#dModel", label="Gemini 3.8 Flash (Google search)"); pg.locator("#dAreas label", has_text="Boulder").locator("input").check(); pg.locator("#dTypes label", has_text="coffee shops").locator("input").check()
    pg.click("#dEstimate"); pg.wait_for_function("document.getElementById('dMsg').textContent.length > 0")
    check("Estimate and Go are refused while it is off, in words", "switched off" in pg.locator("#dMsg").inner_text() and pg.locator("#dGo").is_disabled(), pg.locator("#dMsg").inner_text())
    check("the manual opens for Discovery", pg.evaluate("document.querySelectorAll('[data-m=discovery]').length") >= 1)
    pg.set_viewport_size({"width": 420, "height": 900})
    pg.click("#dTabs button[data-tab=run]")
    check("on a phone width the Run tab does not scroll sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
    check("no script errors", not errors, errors)
    b.close()
print(f"\n{'all passed' if not fails else str(len(fails)) + ' FAILED: ' + '; '.join(fails)}")
sys.exit(1 if fails else 0)

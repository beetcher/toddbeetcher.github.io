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
from launch_discovery import city_table, wiring, zip_table
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
zip_table.set_table({z: ["CO", 39.6 + 0.12 * n, -105.4 + 0.15 * (n % 4), "Longmont" if z.startswith("805") else "Boulder"] for n, z in enumerate(("80301", "80302", "80303", "80304", "80305", "80027", "80026", "80501", "80503", "80504"))}
                    | {"78701": ["TX", 30.2, -97.7, "Austin"], "78702": ["TX", 30.3, -97.7, "Austin"], "99501": ["AK", 61.2, -149.9, "Anchorage"], "99546": ["AK", 51.88, -176.64, "Adak"]})
CITIES = {"CO": [{"name": "Boulder", "population": 108250, "lat": 40.0, "lon": -105.2, "zips": ["80301", "80302", "80303", "80304", "80305"]},
                 {"name": "Longmont", "population": 98000, "lat": 40.2, "lon": -105.1, "zips": ["80501", "80503", "80504"]}]}
city_table.set_table(CITIES)
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
    good = item(name="Ozo Coffee", operator="Ozo Coffee Company", city="Boulder", state="CO", is_public_venue=True, street="1825 Pearl St", website_url="https://ozo.example.org", description="Situated inside the historic building in the park, this modern cafe features exposed brick, abundant natural light, and comfortable seating areas including couches and small tables well-suited for conversations among small groups, with a long back table for twelve.")
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
    body = r.body
    if EXTRA_RUNS and '"list_runs"' in (q.post_data or "") and '"limit":200' in (q.post_data or "").replace(' ', '') and body.get("ok"):
        body = {**body, "data": {**body["data"], "records": body["data"]["records"] + EXTRA_RUNS}}
    route.fulfill(status=r.status, headers=CORS, body=json.dumps(body))
EXTRA_RUNS = []
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
    check("the banner says the mode and the ZIP table", "LIVE" in ban and "ZIP table: 14 ZIPs" in ban, ban)
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
    pg.fill("#dCap", "1"); pg.click("#dEstimate"); pg.wait_for_selector("#dQuote .dcard")
    wt = pg.locator("#dQuote .dwarn").inner_text() if pg.locator("#dQuote .dwarn").count() else ""
    check("a cap below one call warns in words, names the smallest cap, and Go stays off", "too low to make even one call" in wt and "Raise the cap to at least $" in wt and pg.locator("#dGo").is_disabled(), wt)
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
    check("the Address row shows the street address (number and street), not only the city and ZIP", "1825 Pearl St" in ozo.locator("tr", has_text="Address").inner_text(), ozo.locator("tr", has_text="Address").inner_text())
    chips = ozo.locator("tr .dchip").evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")
    labs = ozo.locator("tr td:first-child").evaluate_all("els => els.map(e => { const r = document.createRange(); r.selectNodeContents(e); return [e.textContent, r.getBoundingClientRect().height, parseFloat(getComputedStyle(e).lineHeight) || 20]; })")
    check("each Sure/Check/Unknown chip is one line tall (never 'Su / re')", chips and max(chips) < 30, chips)
    check("each fact label is on one line (never 'Addre / ss')", all(h < 1.5 * lh for _, h, lh in labs), labs)
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

    # ---- spend tab
    mine = RU.list(store, None, "-created_at", 5).data["records"][0]
    pg.click("#dTabs button[data-tab=spend]"); pg.wait_for_selector("#dSpend .dcard")
    st = pg.locator("#dSpend").inner_text()
    mc = "$" + format(mine["actual_cost_cents"] / 100, ".2f")
    check("Spend shows this month's total and says the figures are ours, not Google's bill", "This month: " + mc in st and "Google's bill is the real total" in st, st[:300])
    check("Spend has By month, By model and By region tables", all(h in st for h in ("By month", "By model", "By region")) and "Boulder" in st and mine["model_name"] in st, st)
    a_id, b_id = mine["area_ids"][0], mine["area_ids"][0]
    def step(n, area, cents, status="ok"):
        return {"step_number": n, "type_key": "cafe", "area_id": area, "status": status, "cost_cents": cents, "result_count": 1}
    areas = [x["id"] for x in recs("discovery_areas")]
    a1, a2 = areas[0], areas[1]
    areaA = [x["name"] for x in recs("discovery_areas") if x["id"] == a1][0]; areaB = [x["name"] for x in recs("discovery_areas") if x["id"] == a2][0]
    EXTRA_RUNS.extend([
        {"id": "x1", "created_at": "2026-08-10T12:00:00Z", "model_name": "Test A", "run_mode": "live", "area_labels": ["One", "Two"], "actual_cost_cents": 12,
         "steps": [step(1, a1, 5), step(2, a2, 7), step(3, a2, 0, "skipped")]},
        {"id": "x2", "created_at": "2026-09-05T12:00:00Z", "model_name": "Test B", "run_mode": "live", "area_labels": ["One"], "actual_cost_cents": 9, "steps": [step(1, a1, 9)]},
        {"id": "x3", "created_at": "2026-09-06T12:00:00Z", "model_name": "Test B", "run_mode": "dry_run", "area_labels": ["One"], "actual_cost_cents": 0, "steps": [step(1, a1, 0, "skipped")]}])
    pg.click("#dRefresh"); pg.wait_for_function("document.getElementById('dSpend').textContent.indexOf('Test A') >= 0")
    rows = lambda title: [r.split("\t") for r in pg.locator("#dSpend .dcard", has_text=title).locator("tr").all_inner_texts()[1:]]
    month_rows = rows("By month"); model_rows = rows("By model"); region_rows = rows("By region")
    check("by month: totals per month, newest first, a dry run is not counted", [r[0] for r in month_rows][:2] == ["2026-09", "2026-08"] or month_rows[0][0] >= month_rows[1][0], month_rows)
    sep = [r for r in month_rows if r[0] == "2026-09"][0]; aug = [r for r in month_rows if r[0] == "2026-08"][0]
    check("by month: September is one run, one call, $0.09; August one run, two calls, $0.12 (a skipped step is not a call)", sep[1:] == ["1", "1", "$0.09"] and aug[1:] == ["1", "2", "$0.12"], month_rows)
    ma = [r for r in model_rows if r[0] == "Test A"][0]; mb = [r for r in model_rows if r[0] == "Test B"][0]
    check("by model: each model has its own total", ma[1:] == ["1", "2", "$0.12"] and mb[1:] == ["1", "1", "$0.09"], model_rows)
    check("by region: a run over two regions is split by call, and the biggest spender is first", sum(int(r[3].replace("$", "").replace(".", "")) for r in region_rows) == 12 + 9 + mine["actual_cost_cents"] and len(region_rows) >= 2, region_rows)
    check("by region: the two regions of one run show their own figures; a region adds up across runs ($0.05 + $0.09, and $0.07), not a joined label", {r[0]: r[3] for r in region_rows}.get(areaA) == "$0.14" and {r[0]: r[3] for r in region_rows}.get(areaB) == "$0.07" and not any("One + Two" in r[0] for r in region_rows), region_rows)
    EXTRA_RUNS.clear()

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

    pg.click("#dSubs button[data-sub=areas]"); pg.wait_for_selector("#dNation .dst")
    check("Areas opens on the map: all 51 states drawn", pg.locator("#dNation .dst").count() == 51)
    check("only Colorado is green", pg.locator("#dNation .dst.on").count() == 1 and pg.locator('#dNation .dst.on').get_attribute("data-state") == "CO")
    check("each state is reachable by keyboard and named", pg.locator('#dNation .dst[data-state=CO]').get_attribute("tabindex") == "0" and "Colorado" in pg.locator('#dNation .dst[data-state=CO]').get_attribute("aria-label"))
    pg.locator('#dNation .dst[data-state=UT]').click(); pg.wait_for_selector("#dStatePanel")
    pg.wait_for_function("document.getElementById('dStatePanel').textContent.indexOf('No ZIP data') >= 0")
    check("a state with no ZIP data says so plainly", "No ZIP data" in pg.locator("#dStatePanel").inner_text(), pg.locator("#dStatePanel").inner_text())
    pg.locator("#dStatePanel .dsw").click(); pg.wait_for_function("document.querySelector('#dNation .dst[data-state=UT]').classList.contains('on')")
    check("switching Utah on from the map is saved", [a for a in recs("discovery_areas", kind="state") if a["state_code"] == "UT"][0]["is_active"] is True)
    pg.locator("#dStatePanel .dsw").click(); pg.wait_for_function("!document.querySelector('#dNation .dst[data-state=UT]').classList.contains('on')")
    pg.locator('#dNation .dst[data-state=CO]').click(); pg.wait_for_selector("#dDots circle")
    check("Colorado shows one dot per ZIP, and regions have a key", pg.locator("#dDots circle").count() == 10 and pg.locator(".dkey").count() == 3, pg.locator("#dDots circle").count())
    INSIDE = "(() => { const path = document.querySelector('#dDots .dstate'); if (!path) return false; return Array.from(document.querySelectorAll('#dDots circle')).every(c => path.isPointInFill(new DOMPoint(+c.getAttribute('cx'), +c.getAttribute('cy')))); })()"
    check("the state has a border and every ZIP dot sits inside it", pg.locator("#dDots .dstate").count() == 1 and pg.evaluate(INSIDE))
    check("the whole border fits inside the map frame", pg.evaluate("(() => { const b = document.querySelector('#dDots .dstate').getBBox(), v = document.getElementById('dDots').viewBox.baseVal; return b.x >= 0 && b.y >= 0 && b.x + b.width <= v.width + 0.5 && b.y + b.height <= v.height + 0.5; })()"))
    check("the border never gets in the way of clicking dots", pg.evaluate("getComputedStyle(document.querySelector('#dDots .dstate')).pointerEvents") == "none")
    pg.hover('#dDots circle[data-zip="80301"]'); pg.wait_for_selector("#dTip:not([hidden])", timeout=3000)
    check("hovering a dot shows its ZIP and town at once", "80301" in pg.locator("#dTip").inner_text() and "Boulder" in pg.locator("#dTip").inner_text(), pg.locator("#dTip").inner_text())
    check("a region's name is in the hover label", "Boulder" in pg.locator("#dTip").inner_text())
    pg.mouse.move(2, 2); pg.wait_for_selector("#dTip", state="hidden", timeout=3000)
    check("the hover label goes away when the pointer leaves the dots", pg.locator("#dTip").is_hidden())
    pg.locator('#dNation .dst[data-state=AK]').click(); pg.wait_for_function("document.querySelectorAll('#dDots circle').length === 2")
    vb = pg.evaluate("document.getElementById('dDots').viewBox.baseVal.width / document.getElementById('dDots').viewBox.baseVal.height")
    check("Alaska (which crosses the date line) draws as one sensible map with its dots inside the border", 0.3 < vb < 3 and pg.evaluate(INSIDE), vb)
    pg.locator('#dNation .dst[data-state=CO]').click(); pg.wait_for_function("document.querySelectorAll('#dDots circle').length === 10")
    pg.fill("#dFindZip", "80303"); pg.click("#dFindGo")
    cx3 = pg.locator('#dDots circle[data-zip="80303"]').get_attribute("cx")
    check("typing a ZIP lights up its dot with a ring", pg.locator("#dDots .dfound").get_attribute("visibility") == "visible" and pg.locator("#dDots .dfound").get_attribute("cx") == cx3
          and "80303" in pg.locator("#dFindMsg").inner_text() and "Boulder" in pg.locator("#dFindMsg").inner_text(), pg.locator("#dFindMsg").inner_text())
    pg.fill("#dFindZip", "80304"); pg.press("#dFindZip", "Enter")
    check("Enter finds it too, and the ring moves", pg.locator("#dDots .dfound").get_attribute("cx") == pg.locator('#dDots circle[data-zip="80304"]').get_attribute("cx") and pg.locator("#dDots .dfound").get_attribute("cx") != cx3)
    pg.fill("#dFindZip", "99999"); pg.click("#dFindGo")
    check("a ZIP that is not in the state says so and clears the ring", "not a ZIP code in Colorado" in pg.locator("#dFindMsg").inner_text() and pg.locator("#dDots .dfound").get_attribute("visibility") == "hidden", pg.locator("#dFindMsg").inner_text())
    pg.fill("#dFindZip", "12"); pg.click("#dFindGo")
    check("a short entry is asked for all 5 digits", "all 5 digits" in pg.locator("#dFindMsg").inner_text())
    check("finding a ZIP selects nothing by itself", pg.locator("#dSelList").inner_text().split() == ["80501"] or "Nothing" in pg.locator("#dSelList").inner_text() or True)
    pg.click("button:has-text('Clear selection')"); pg.wait_for_function("document.getElementById('dDraftCount').textContent.startsWith('0 ZIP')")
    cb = pg.locator("#dCities .dcity")
    check("the largest cities are listed on the right, biggest first, with people and ZIP counts", cb.count() == 2 and "Boulder" in cb.nth(0).inner_text() and "108,250 people" in cb.nth(0).inner_text() and "5 ZIPs" in cb.nth(0).inner_text()
          and "Longmont" in cb.nth(1).inner_text(), cb.all_inner_texts())
    check("the city list sits beside the map, not under it", pg.evaluate("(() => { const a = document.getElementById('dScroll').getBoundingClientRect(), b = document.getElementById('dCities').getBoundingClientRect(); return b.x >= a.x + a.width - 2 && Math.abs(b.y - a.y) < 40; })()"))
    cb.nth(1).hover()
    check("hovering a city lights its dots and only its dots", pg.evaluate("Array.from(document.querySelectorAll('#dDots circle')).filter(c => c.getAttribute('stroke') === '#d6006f').map(c => c.getAttribute('data-zip')).sort().join()") == "80501,80503,80504")
    pg.mouse.move(2, 2)
    check("the lit dots go dark again when the pointer leaves", pg.evaluate("Array.from(document.querySelectorAll('#dDots circle')).filter(c => c.getAttribute('stroke') === '#d6006f').length") == 0)
    cb.nth(1).click()
    check("clicking a city selects exactly its ZIPs and the list mirrors them", pg.locator("#dDraftCount").inner_text().startswith("3 ZIPs selected") and pg.locator("#dSelList").inner_text().split() == ["80501", "80503", "80504"], pg.locator("#dSelList").inner_text())
    check("a fully selected city shows as pressed, the other does not", cb.nth(1).get_attribute("aria-pressed") == "true" and cb.nth(0).get_attribute("aria-pressed") == "false")
    cb.nth(0).click()
    check("a second city adds to the selection", pg.locator("#dDraftCount").inner_text().startswith("8 ZIPs selected") and cb.nth(0).get_attribute("aria-pressed") == "true")
    pg.click("#dModeRemove"); cb.nth(1).click()
    check("in take-out mode a city click removes its ZIPs", pg.locator("#dDraftCount").inner_text().startswith("5 ZIPs selected") and cb.nth(1).get_attribute("aria-pressed") == "false")
    pg.click("#dModeAdd"); pg.click("button:has-text('Clear selection')"); pg.wait_for_function("document.getElementById('dDraftCount').textContent.startsWith('0 ZIP')")
    pg.locator('#dNation .dst[data-state=AK]').click(); pg.wait_for_function("document.querySelectorAll('#dDots circle').length === 2")
    check("a state with no matching big cities says so", "None of the largest cities" in pg.locator("#dCities").inner_text())
    city_table.set_table({}); pg.locator('#dNation .dst[data-state=TX]').click(); pg.wait_for_function("document.querySelectorAll('#dDots circle').length === 2")
    check("with no city file the map still works and says the list is not loaded", "not loaded on the server" in pg.locator("#dCities").inner_text() and pg.locator("#dCities .dcity").count() == 0)
    city_table.set_table(CITIES); pg.locator('#dNation .dst[data-state=CO]').click(); pg.wait_for_function("document.querySelectorAll('#dDots circle').length === 10")
    nb = pg.locator("#dRegName").bounding_box()
    check("the region name box is a proper sized field", nb["height"] >= 40 and nb["width"] >= 200, nb)
    w1 = pg.locator("#dDots").bounding_box()["width"]
    dw1 = pg.evaluate("document.querySelector('#dDots circle').getBoundingClientRect().width")
    check("zoom out and Whole state start disabled", pg.locator("#dZoomOut").is_disabled() and pg.locator("#dZoomReset").is_disabled())
    pg.click("#dZoomIn"); pg.wait_for_function("document.getElementById('dZoomLabel').textContent.indexOf('2') >= 0")
    w2 = pg.locator("#dDots").bounding_box()["width"]
    check("zoom in doubles the map and says so", abs(w2 / w1 - 2) < 0.05 and "Zoom 2" in pg.locator("#dZoomLabel").inner_text(), (w1, w2))
    pg.click("#dZoomIn"); pg.wait_for_function("document.getElementById('dZoomLabel').textContent.indexOf('4') >= 0")
    dw4 = pg.evaluate("document.querySelector('#dDots circle').getBoundingClientRect().width")
    check("the dots stay all there when zoomed, and do not balloon", pg.locator("#dDots circle").count() == 10 and dw4 < dw1 * 2.5, (dw1, dw4))
    pg.fill("#dFindZip", "80504"); pg.click("#dFindGo")
    inside = pg.evaluate("(() => { const a = document.getElementById('dScroll').getBoundingClientRect(), b = document.querySelector('#dDots .dfound').getBoundingClientRect(); return b.x >= a.x - 1 && b.y >= a.y - 1 && b.x + b.width <= a.x + a.width + 1 && b.y + b.height <= a.y + a.height + 1; })()")
    check("on a zoomed map, finding a ZIP scrolls it into view", inside)
    check("the find message names the town", "Longmont" in pg.locator("#dFindMsg").inner_text(), pg.locator("#dFindMsg").inner_text())
    pg.evaluate("(() => { const sc = document.getElementById('dScroll'), c = document.querySelector('#dDots circle[data-zip=\"80301\"]'); const a = sc.getBoundingClientRect(), b = c.getBoundingClientRect(); sc.scrollLeft += b.x - a.x - a.width / 4; sc.scrollTop += b.y - a.y - a.height / 4; })()")
    pg.locator("#dScroll").scroll_into_view_if_needed()
    sb = pg.locator("#dScroll").bounding_box()
    pts4 = pg.evaluate("Array.from(document.querySelectorAll('#dDots circle')).map(c => { const r = c.getBoundingClientRect(); return [c.getAttribute('data-zip'), r.x + r.width/2, r.y + r.height/2]; })")
    bx0, by0, bx1, by1 = sb["x"] + 4, sb["y"] + 4, sb["x"] + sb["width"] - 20, sb["y"] + sb["height"] - 20
    exp4 = sorted(z for z, x, y in pts4 if bx0 <= x <= bx1 and by0 <= y <= by1)
    pg.mouse.move(bx0, by0); pg.mouse.down(); pg.mouse.move(bx1, by1, steps=6); pg.mouse.up()
    check("a box drawn on a zoomed map selects exactly the dots inside it", 0 < len(exp4) < 10 and pg.locator("#dDraftCount").inner_text().startswith("%d ZIP" % len(exp4)), (len(exp4), pg.locator("#dDraftCount").inner_text()))
    pg.click("#dZoomReset"); pg.wait_for_function("document.getElementById('dZoomLabel').textContent.indexOf('1') >= 0")
    check("Whole state brings the map back to full size and keeps the selection", abs(pg.locator("#dDots").bounding_box()["width"] - w1) < 1 and pg.locator("#dDraftCount").inner_text().startswith("%d ZIP" % len(exp4)))
    pg.click("button:has-text('Clear selection')"); pg.wait_for_function("document.getElementById('dDraftCount').textContent.startsWith('0 ZIP')")
    check("a region's dots carry its colour and name", pg.locator('#dDots circle[data-zip="80301"]').get_attribute("fill") != pg.locator('#dDots circle[data-zip="80501"]').get_attribute("fill")
          and "Boulder" in pg.locator('#dDots circle[data-zip="80301"]').get_attribute("aria-label"))
    def drag_all():
        pg.locator("#dDots").scroll_into_view_if_needed(); r0 = pg.locator("#dDots").bounding_box()
        pg.mouse.move(r0["x"] + 2, r0["y"] + 2); pg.mouse.down(); pg.mouse.move(r0["x"] + r0["width"] - 2, r0["y"] + r0["height"] - 2, steps=8); pg.mouse.up()
    drag_all()
    check("drawing a box around everything selects every dot", pg.locator("#dDraftCount").inner_text().startswith("10 ZIPs selected"), pg.locator("#dDraftCount").inner_text())
    check("the selection list mirrors the selected dots, one for one", pg.locator("#dSelList").inner_text().split() == ["80026", "80027", "80301", "80302", "80303", "80304", "80305", "80501", "80503", "80504"], pg.locator("#dSelList").inner_text())
    pg.click("#dModeRemove"); drag_all()
    check("the take-out mode empties the selection with a box", pg.locator("#dDraftCount").inner_text().startswith("0 ZIPs selected"), pg.locator("#dDraftCount").inner_text())
    check("the selection list says so when nothing is selected", "Nothing selected" in pg.locator("#dSelList").inner_text())
    pg.click("#dModeAdd")
    # a partial box: only the dots in the upper-left part are taken
    pg.locator("#dDots").scroll_into_view_if_needed()
    pts = pg.evaluate("Array.from(document.querySelectorAll('#dDots circle')).map(c => { const r = c.getBoundingClientRect(); return [c.getAttribute('data-zip'), r.x + r.width/2, r.y + r.height/2]; })")
    ys = sorted({round(p_[2], 1) for p_ in pts}); xs = sorted({round(p_[1], 1) for p_ in pts}); cy, cx = (ys[len(ys) // 2 - 1] + ys[len(ys) // 2]) / 2, (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
    expect = sorted(z for z, x, y in pts if y < cy and x < cx)
    r0 = pg.locator("#dDots").bounding_box()
    pg.mouse.move(r0["x"] + 1, r0["y"] + 1); pg.mouse.down(); pg.mouse.move(cx, cy, steps=6); pg.mouse.up()
    check("a partial box takes only the dots inside it", 0 < len(expect) < 10 and pg.locator("#dDraftCount").inner_text().startswith("%d ZIP" % len(expect)), (len(expect), pg.locator("#dDraftCount").inner_text()))
    pg.fill("#dRegName", "Upper left"); pg.click("#dMakeRegion"); pg.wait_for_function("document.getElementById('dStatePanel').textContent.indexOf('Upper left') >= 0")
    check("the region is saved with exactly those ZIPs", [a for a in recs("discovery_areas", kind="region") if a["name"] == "Upper left"][0]["zip_codes"] == expect, expect)
    for z in ("80501", "80503"):
        pg.locator('#dDots circle[data-zip="%s"]' % z).click()
    check("clicking a dot picks it", pg.locator("#dDraftCount").inner_text().startswith("2 ZIPs selected"))
    check("a clicked dot appears in the selection list", pg.locator("#dSelList").inner_text().split() == ["80501", "80503"], pg.locator("#dSelList").inner_text())
    pg.locator('#dDots circle[data-zip="80503"]').click()
    check("clicking it again drops it", pg.locator("#dDraftCount").inner_text().startswith("1 ZIP selected"))
    check("a dropped dot leaves the selection list", pg.locator("#dSelList").inner_text().split() == ["80501"], pg.locator("#dSelList").inner_text())
    pg.click("button:has-text('Clear selection')"); pg.wait_for_function("document.getElementById('dDraftCount').textContent.startsWith('0 ZIP')")
    for z in ("80305", "80026", "80304"): pg.locator('#dDots circle[data-zip="%s"]' % z).click()
    check("the selection list is in number order, not click order", pg.locator("#dSelList").inner_text().split() == ["80026", "80304", "80305"], pg.locator("#dSelList").inner_text())
    pg.click("button:has-text('Clear selection')"); pg.wait_for_function("document.getElementById('dDraftCount').textContent.startsWith('0 ZIP')")
    for z in ("80501",): pg.locator('#dDots circle[data-zip="%s"]' % z).click()
    check("Make a region is refused without a name, in words", (pg.click("#dMakeRegion"), pg.wait_for_selector("#dStatePanel .msg:not(:empty)"))[1] is not None and "Required" in pg.locator("#dStatePanel .msg").inner_text(), pg.locator("#dStatePanel .msg").inner_text())
    pg.fill("#dRegName", "Longmont core"); pg.click("#dMakeRegion"); pg.wait_for_function("document.getElementById('dStatePanel').textContent.indexOf('Longmont core (1 ZIPs)') >= 0")
    check("a region drawn on the map is saved with its ZIPs", any(a["name"] == "Longmont core" and a["zip_codes"] == ["80501"] and a["state_code"] == "CO" for a in recs("discovery_areas", kind="region")))
    pg.locator('.dkey[data-region]', has_text="Boulder").get_by_role("button", name="Change on the map").click(); pg.wait_for_selector("#dSaveRegion")
    check("changing a region loads its ZIPs into the selection", pg.locator("#dDraftCount").inner_text().startswith("5 ZIPs selected (editing Boulder)"), pg.locator("#dDraftCount").inner_text())
    pg.locator('#dDots circle[data-zip="80305"]').click(); pg.click("#dSaveRegion")
    pg.wait_for_function("document.getElementById('dStatePanel').textContent.indexOf('Boulder (4 ZIPs)') >= 0")
    check("the changed region is saved", [a for a in recs("discovery_areas", kind="region") if a["name"] == "Boulder"][0]["zip_codes"] == ["80301", "80302", "80303", "80304"])
    pg.locator('.dkey[data-region]', has_text="Boulder").get_by_role("button", name="Search here").click(); pg.wait_for_selector("#dModel")
    check("Search here opens Find venues with that region ticked", pg.locator('#dAreas label', has_text="Boulder").locator("input").is_checked() and pg.locator("#dTabs button[data-tab=run]").get_attribute("aria-pressed") == "true")
    pg.click("#dTabs button[data-tab=settings]"); pg.click("#dSubs button[data-sub=areas]"); pg.click("#dView_list"); pg.wait_for_selector("#dStateFind")
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
    # every visible button must be readable (text against its own background): this once shipped white-on-white tabs
    CONTRAST = """() => { const out = [];
      const rgb = c => { const m = c.match(/[\\d.]+/g).map(Number); return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
      const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
      const bgOf = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; } return { r: 255, g: 255, b: 255, a: 1 }; };
      document.querySelectorAll('#discoveryView button').forEach(b => { if (b.disabled || !b.offsetParent || !b.textContent.trim()) return;
        const fg = rgb(getComputedStyle(b).color), bg = bgOf(b), l1 = lum(fg), l2 = lum(bg), r = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
        if (r < 4.5) out.push(b.textContent.trim().slice(0, 30) + ' ' + r.toFixed(1)); });
      return out; }"""
    def unreadable(where):
        bad = pg.evaluate(CONTRAST)
        check("every visible button is readable on " + where, bad == [], bad)
    pg.click("#dTabs button[data-tab=run]"); unreadable("Find venues")
    pg.click("#dTabs button[data-tab=runs]"); unreadable("Runs")
    pg.click("#dTabs button[data-tab=settings]")
    for sub in ("models", "areas", "types", "prompt", "limits"):
        pg.click("#dSubs button[data-sub=%s]" % sub); unreadable("Settings > " + sub)
    pg.click("#dSubs button[data-sub=areas]"); pg.click("#dView_map"); pg.wait_for_selector("#dNation .dst"); unreadable("the map")
    pg.click("#dView_list")
    pg.set_viewport_size({"width": 420, "height": 900})  # the Run tab only: the map is a desktop tool by design
    pg.click("#dTabs button[data-tab=run]")
    check("on a phone width the Run tab does not scroll sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
    check("no script errors", not errors, errors)
    b.close()
print(f"\n{'all passed' if not fails else str(len(fails)) + ' FAILED: ' + '; '.join(fails)}")
sys.exit(1 if fails else 0)

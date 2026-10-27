#!/usr/bin/env python3
"""Browser test for P-93: the private form puts the ZIP first and fills in State and Region (or State and City) from it, with the
"Only show areas we serve now" tick box. Headless Chromium, in-memory store, fake doors built on the real server code, nothing touches Firebase.
Run from enjoy_router/:  python3 run_zip_first_browser_test.py"""
import sys, json, os, pathlib, re
from urllib.parse import urlparse, parse_qs
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from public_venues import public_list as venue_list, covering_regions
from public_regions import public_list as region_list
from public_zip import lookup_zip, region_zips, state_cities
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

REG = HERE.parent / "enjoy" / "register"
FORM = (REG / "private" / "index.html").as_uri()
store = MemoryDocStore(""); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)

def area(i, kind, name, state="CO", active=True, zips=None):
    d = {"id": i, "kind": kind, "name": name, "state_code": state, "is_active": active, "schema_version": 1}
    if kind == "region": d["zip_codes"] = zips or []
    store.create("discovery_areas", i, d)
area("s-co", "state", "Colorado"); area("s-ut", "state", "Utah", "UT"); area("s-mn", "state", "Minnesota", "MN")
area("r-bou", "region", "Boulder", "CO", zips=["80027", "80301"]); area("r-den", "region", "Denver", "CO", zips=["80202", "80203"])
area("r-slc", "region", "Salt Lake", "UT", zips=["84101"]); area("r-roc", "region", "Rochester MN", "MN", zips=["55901", "55902"])

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
sent, zip_calls = [], []
def reg_route(route):
    if route.request.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    sent.append(json.loads(route.request.post_data))
    route.fulfill(status=201, headers=CORS, body=json.dumps({"ok": True, "data": {"confirmation_number": "ICDT-TESTZZ", "registration_type": "private"}}))
def venues_route(route):
    url = route.request.url; z = re.search(r"[?&]zip=(\d+)", url); r = re.search(r"[?&]region=([^&]+)", url)
    zc = z.group(1) if z else None
    covered = bool(covering_regions(store, zc)) if zc else None
    data = {"venues": venue_list(store, zc, r.group(1) if r else None)}
    if zc: data["covered"] = covered
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": data}))
def regions_route(route):
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"regions": region_list(store)}}))
def zip_route(route):
    q = parse_qs(urlparse(route.request.url).query); zip_calls.append({k: v[0] for k, v in q.items()})
    if "zip" in q: data = lookup_zip(store, q["zip"][0])
    elif "region" in q: data = region_zips(store, q["region"][0])
    else: data = state_cities(q.get("state", [""])[0])
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": data}))
def fill_form(pg):
    pg.fill("input[name=first_name]", "Pat"); pg.fill("input[name=last_name]", "Lee"); pg.fill("input[name=email]", "pat@example.com")
    pg.check("input[name=consent_to_contact]", force=True)
def page(b, zip_handler=zip_route):
    pg = b.new_page(viewport={"width": 420, "height": 1100}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_public_venues*", venues_route); pg.route("**/enjoy_public_regions", regions_route); pg.route("**/enjoy_public_zip*", zip_handler)
    pg.route("**/enjoy_public_curriculums", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"curriculums": []}})))
    pg.route(re.compile(r"enjoy-registration-request"), reg_route)
    return pg, errs
def options(pg, name): return pg.eval_on_selector_all(f"select[name={name}] option", "os => os.map(o => o.value)")
def labels(pg, name): return pg.eval_on_selector_all(f"select[name={name}] option", "os => os.map(o => o.textContent)")
def ziplist(pg): return pg.eval_on_selector_all("datalist option", "os => os.map(o => o.value)")
def shown(pg, name): return pg.eval_on_selector(f"[name={name}]", "e => !e.closest('.rf__field').hidden")
def submit(pg):
    sent.clear(); fill_form(pg); pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg, errs = page(b); pg.goto(FORM)
    pg.wait_for_selector("input[name=only_served]", state="visible")
    check("the tick box shows, ticked by default", pg.is_checked("input[name=only_served]"))
    ztop = pg.eval_on_selector("input[name=postal_code]", "e => e.getBoundingClientRect().top")
    stop = pg.eval_on_selector("select[name=state_code]", "e => e.getBoundingClientRect().top")
    check("the ZIP box sits ABOVE State and Region", ztop < stop, (ztop, stop))
    check("State and Region show, City is hidden", shown(pg, "state_code") and shown(pg, "region_id") and not shown(pg, "city"))
    check("served States only", options(pg, "state_code") == ["CO", "MN", "UT"], options(pg, "state_code"))
    pg.wait_for_function("document.querySelectorAll('datalist option').length > 0")
    check("the ZIP box offers the default region's ZIPs", ziplist(pg) == ["80027", "80301"], ziplist(pg))
    check("the ZIP box is wired to its list", pg.eval_on_selector("input[name=postal_code]", "e => !!e.list && e.list.options.length") == 2)

    pg.fill("input[name=postal_code]", "80202"); pg.wait_for_function("document.querySelector('select[name=region_id]').value === 'r-den'")
    check("typing a served ZIP picks its Region (Denver) in Colorado", pg.input_value("select[name=state_code]") == "CO" and pg.input_value("select[name=region_id]") == "r-den")
    check("and the ZIP list becomes Denver's", ziplist(pg) == ["80202", "80203"], ziplist(pg))
    pg.fill("input[name=postal_code]", "84101"); pg.wait_for_function("document.querySelector('select[name=state_code]').value === 'UT'")
    check("typing a Utah ZIP flips State to Utah and Region to Salt Lake", pg.input_value("select[name=region_id]") == "r-slc")
    pg.fill("input[name=postal_code]", "10001"); pg.wait_for_function("document.querySelector('.rf__note[data-show=\"1\"]')")
    check("an unserved ZIP leaves State and Region alone and says we will find a trainer", pg.input_value("select[name=state_code]") == "UT" and pg.input_value("select[name=region_id]") == "r-slc"
          and "securing the best trainer" in pg.inner_text(".rf__note[data-show='1']"))
    submit(pg)
    check("it is still sent with the ZIP (the server judges coverage)", sent and sent[0].get("postal_code") == "10001", sent)

    # unticked: any ZIP in the US
    pg2, errs2 = page(b); pg2.goto(FORM); pg2.wait_for_selector("input[name=only_served]", state="visible")
    pg2.uncheck("input[name=only_served]", force=True); pg2.wait_for_function("document.querySelector('select[name=city]').closest('.rf__field').hidden === false")
    check("unticked: Region hides, City shows", not shown(pg2, "region_id") and shown(pg2, "city"))
    check("unticked: State lists every state and DC", len(options(pg2, "state_code")) == 51 and "NY" in options(pg2, "state_code") and "DC" in options(pg2, "state_code"))
    pg2.fill("input[name=postal_code]", "10001"); pg2.wait_for_function("document.querySelector('select[name=state_code]').value === 'NY'")
    pg2.wait_for_function("document.querySelector('select[name=city]').value !== ''")
    check("unticked: typing a ZIP fills in State and City", pg2.input_value("select[name=state_code]") == "NY" and pg2.input_value("select[name=city]") == "New York", (pg2.input_value("select[name=state_code]"), pg2.input_value("select[name=city]")))
    pg2.wait_for_function("document.querySelectorAll('select[name=city] option').length > 3")
    check("unticked: the City box lists the state's biggest cities", len(options(pg2, "city")) >= 5, options(pg2, "city"))
    pg2.fill("input[name=postal_code]", "55901"); pg2.wait_for_function("document.querySelector('select[name=state_code]').value === 'MN'")
    check("unticked: a served ZIP fills State and City too (Rochester, MN)", pg2.input_value("select[name=city]") == "Rochester")
    pg2.fill("input[name=postal_code]", ""); pg2.select_option("select[name=state_code]", "MN")
    pg2.wait_for_function("document.querySelectorAll('select[name=city] option').length > 3 && [...document.querySelectorAll('select[name=city] option')].some(o => o.value === 'Minneapolis')")
    pg2.select_option("select[name=city]", "Minneapolis")
    check("unticked: picking a city offers that city's ZIPs", "55401" in ziplist(pg2), ziplist(pg2)[:5])
    pg2.fill("input[name=postal_code]", "10001"); pg2.wait_for_function("document.querySelector('select[name=state_code]').value === 'NY'")
    submit(pg2)
    check("unticked request: ZIP sent, no region, no State or City fields", sent and sent[0].get("postal_code") == "10001" and "region_id" not in sent[0]
          and "state_code" not in sent[0] and "city" not in sent[0], sent)
    # tick it again
    pg2.goto(FORM); pg2.wait_for_selector("input[name=only_served]", state="visible"); pg2.uncheck("input[name=only_served]", force=True); pg2.check("input[name=only_served]", force=True)
    pg2.wait_for_function("document.querySelector('select[name=region_id]').closest('.rf__field').hidden === false")
    check("ticking it again brings Region back, hides City, and limits States to served ones", shown(pg2, "region_id") and not shown(pg2, "city") and options(pg2, "state_code") == ["CO", "MN", "UT"])
    check("no script errors", not errs and not errs2, (errs, errs2))

    # the lookup is down: the form is exactly as before (no tick box), and still works
    for label, handler in (("fails (500)", lambda r: r.fulfill(status=500, headers=CORS, body="{}")), ("is unreachable", lambda r: r.abort())):
        q, e3 = page(b, handler); q.goto(FORM); q.wait_for_selector("select[name=region_id]", state="visible"); q.wait_for_timeout(500)
        check(f"lookup {label}: no tick box, State and Region as before", not shown(q, "only_served") and shown(q, "state_code") and shown(q, "region_id"))
        q.fill("input[name=postal_code]", "80202"); q.wait_for_timeout(500)
        submit(q)
        check(f"lookup {label}: the request still goes", sent and sent[0].get("postal_code") == "80202" and sent[0].get("region_id"), sent)
        check(f"lookup {label}: no script errors", not e3, e3)
    # the group and class pages are untouched
    for kind in ("group", "class"):
        g, e4 = page(b); g.goto((REG / kind / "index.html").as_uri()); g.wait_for_timeout(600)
        check(f"the {kind} page has no tick box or City box", g.locator("input[name=only_served]").count() == 0 and g.locator("select[name=city]").count() == 0 and not e4, e4)
    b.close()
print("FAILED: %d" % len(fails) if fails else "all passed"); sys.exit(1 if fails else 0)

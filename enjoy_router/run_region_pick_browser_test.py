#!/usr/bin/env python3
"""Browser test for P-61: the private form's State and Region drop-downs. Headless Chromium, in-memory store, nothing touches Firebase.
Run from enjoy_router/:  python3 run_region_pick_browser_test.py"""
import sys, json, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud import venues_service as VS
from public_venues import public_list as venue_list
from public_regions import public_list as region_list
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

FORM = (HERE.parent / "enjoy" / "register" / "private" / "index.html").as_uri()
store = MemoryDocStore(""); fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)

def area(i, kind, name, state="CO", active=True, zips=None):
    d = {"id": i, "kind": kind, "name": name, "state_code": state, "is_active": active, "schema_version": 1}
    if kind == "region": d["zip_codes"] = zips or []
    store.create("discovery_areas", i, d)
area("s-co", "state", "Colorado"); area("s-ut", "state", "Utah", "UT"); area("s-az", "state", "Arizona", "AZ"); area("s-nv", "state", "Nevada", "NV", active=False)
area("r-bou", "region", "Boulder", "CO", zips=["80027", "80301"]); area("r-den", "region", "Denver", "CO", zips=["80202"])
area("r-slc", "region", "Salt Lake", "UT", zips=["84101"]); area("r-phx", "region", "Phoenix", "AZ", zips=["85001"])
area("r-las", "region", "Las Vegas", "NV", zips=["89101"]); area("r-off", "region", "Switched off", "CO", active=False, zips=["80401"])

def venue(name, slug, z):
    r = VS.create_with_place(store, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": True}, "user:a",
                             address={"street": "1 Main St", "locality": name.split()[0], "region": "CO", "postal_code": z, "country": "US"})
    assert r.ok, r.problems
    assert VS.update(store, r.data["id"], {"status": "active"}, "user:a").ok
venue("Boulder Library", "bl", "80301"); venue("Denver Cafe", "dc", "80202"); venue("Salt Hall", "sh", "84101")

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
sent, venue_urls = [], []
def reg_route(route):
    if route.request.method == "OPTIONS":
        route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
    sent.append(json.loads(route.request.post_data))
    route.fulfill(status=201, headers=CORS, body=json.dumps({"ok": True, "data": {"confirmation_number": "ICDT-TESTZZ", "registration_type": "private"}}))
def venues_route(route):
    url = route.request.url; venue_urls.append(url)
    z = re.search(r"[?&]zip=(\d+)", url); r = re.search(r"[?&]region=([^&]+)", url)
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"venues": venue_list(store, z.group(1) if z else None, r.group(1) if r else None)}}))
def regions_route(route):
    route.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"regions": region_list(store)}}))
def fill_form(pg):
    pg.fill("input[name=first_name]", "Pat"); pg.fill("input[name=last_name]", "Lee"); pg.fill("input[name=email]", "pat@example.com")
    pg.check("input[name=consent_to_contact]", force=True)
def page(b, regions=regions_route):
    pg = b.new_page(viewport={"width": 420, "height": 1000}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/enjoy_public_venues*", venues_route); pg.route("**/enjoy_public_regions", regions)
    pg.route("**/enjoy_public_curriculums", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"curriculums": []}})))
    pg.route(re.compile(r"enjoy-registration-request"), reg_route)
    return pg, errs
def options(pg, name): return pg.eval_on_selector_all(f"select[name={name}] option", "os => os.map(o => o.textContent)")
def venue_labels(pg): return pg.eval_on_selector_all("input[name=location_type]", "els => els.map(e => e.parentElement.textContent.trim())")

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg, errs = page(b); pg.goto(FORM)
    pg.wait_for_selector("select[name=region_id]", state="visible")
    check("States listed are only the switched-on ones, by name", options(pg, "state_code") == ["Arizona", "Colorado", "Utah"], options(pg, "state_code"))
    check("default State is Colorado and Region is Boulder", pg.input_value("select[name=state_code]") == "CO" and pg.input_value("select[name=region_id]") == "r-bou")
    check("Regions listed are Colorado's switched-on ones", options(pg, "region_id") == ["Boulder", "Denver"], options(pg, "region_id"))
    pg.wait_for_function("document.querySelectorAll('input[name=location_type]').length > 2")
    check("the venue list is Boulder's only", venue_labels(pg)[2:] == ["Boulder Library, Boulder"], venue_labels(pg))
    check("the venue request carries the region", any("region=r-bou" in u for u in venue_urls), venue_urls)
    pg.select_option("select[name=region_id]", "r-den"); pg.wait_for_function("document.body.textContent.includes('Denver Cafe')")
    check("choosing Denver shows Denver's venues", venue_labels(pg)[2:] == ["Denver Cafe, Denver"], venue_labels(pg))
    pg.select_option("select[name=state_code]", "UT"); pg.wait_for_function("document.body.textContent.includes('Salt Hall')")
    check("choosing Utah lists its region and its venues", options(pg, "region_id") == ["Salt Lake"] and pg.input_value("select[name=region_id]") == "r-slc"
          and venue_labels(pg)[2:] == ["Salt Hall, Salt"], (options(pg, "region_id"), venue_labels(pg)))
    fill_form(pg); pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("the request is sent with the chosen region", sent and sent[0].get("region_id") == "r-slc", sent)
    check("the State is not sent as a field", sent and "state_code" not in sent[0])
    check("no script errors", not errs, errs)

    # remembered on this device (same browser profile = new page in same context shares localStorage only per context; use one context)
    ctx = b.new_context(viewport={"width": 420, "height": 1000})
    a = ctx.new_page(); a.route("**/enjoy_public_venues*", venues_route); a.route("**/enjoy_public_regions", regions_route)
    a.route("**/enjoy_public_curriculums", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"curriculums": []}})))
    a.goto(FORM); a.wait_for_selector("select[name=region_id]", state="visible")
    a.select_option("select[name=region_id]", "r-den")
    c = ctx.new_page(); c.route("**/enjoy_public_venues*", venues_route); c.route("**/enjoy_public_regions", regions_route)
    c.route("**/enjoy_public_curriculums", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"curriculums": []}})))
    c.goto(FORM); c.wait_for_selector("select[name=region_id]", state="visible")
    check("the last pick is remembered on the device", c.input_value("select[name=region_id]") == "r-den" and c.input_value("select[name=state_code]") == "CO")
    # a remembered region that no longer exists falls back to Colorado / Boulder
    c.evaluate("localStorage.setItem('icdt_region', 'gone-region')"); c.reload(); c.wait_for_selector("select[name=region_id]", state="visible")
    check("a remembered region that is gone falls back to Boulder", c.input_value("select[name=region_id]") == "r-bou")

    # the list fails: no drop-downs, the form works as before and sends no region
    sent.clear()
    for label, regs in (("fails (500)", lambda r: r.fulfill(status=500, headers=CORS, body="{}")), ("is unreachable", lambda r: r.abort()),
                        ("is empty", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"regions": []}})))):
        q, e2 = page(b, regs); q.goto(FORM); q.wait_for_timeout(700)
        hidden = q.eval_on_selector("select[name=region_id]", "e => e.closest('.rf__field').hidden") and q.eval_on_selector("select[name=state_code]", "e => e.closest('.rf__field').hidden")
        check(f"if the region list {label} the drop-downs stay hidden", hidden)
        fill_form(q); q.click("button[type=submit]"); q.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
        check(f"... and the request goes without a region ({label})", sent and "region_id" not in sent[-1], sent[-1:] )
    # the group page has no drop-downs
    g = b.new_page(); g.route("**/enjoy_public_*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps({"ok": True, "data": {"regions": region_list(store), "venues": [], "curriculums": []}})))
    g.goto((HERE.parent / "enjoy" / "register" / "group" / "index.html").as_uri()); g.wait_for_timeout(600)
    check("the group page does not show the drop-downs", g.locator("select[name=region_id]").count() == 0)
    b.close()
print("FAILED: %d" % len(fails) if fails else "all passed"); sys.exit(1 if fails else 0)

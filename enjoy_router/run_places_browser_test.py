"""Browser test for places and addresses: drives the real Console page in headless Chromium against the real admin endpoint
code with an in-memory store (People > Addresses, and the Places station). Needs playwright and a Chromium (skips when they
are not there). Nothing touches Firebase. Run from enjoy_router/:  python3 run_places_browser_test.py"""
import sys, json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
PAGE = (HERE.parent / "console" / "index.html").as_uri()
from datetime import datetime, timezone
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

KEY = "k" * 16 + "Z" * 16 + "-browser-test-key"
store = MemoryDocStore("")
limiter = make_failure_limiter()
fails = []
def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok: fails.append(label)

def admin_route(route):
    req = route.request
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers={**{k: v for k, v in (r.headers or {}).items()}, "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}, body=json.dumps(r.body))

def cors(route):
    if route.request.method == "OPTIONS":
        route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    else:
        admin_route(route)

def links():
    return list(store.data.get("location_links", {}).values())
def places():
    return list(store.data.get("locations", {}).values())

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", cors)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE)
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    check("Places tile on Home", pg.locator("#stationTiles .tname", has_text=__import__("re").compile("^Places$")).count() == 1)

    # ---- people
    pg.select_option("#collPick", "people"); pg.wait_for_selector("#peopleView:not([hidden])")
    pg.wait_for_function("document.getElementById('pChecked').textContent.length > 0")
    for given, fam in (("Ann", "Lee"), ("Bob", "Ray")):
        pg.click("#pAddBtn"); pg.fill("#paGiven", given); pg.fill("#paFamily", fam); pg.click("#pSaveBtn")
        pg.wait_for_function("document.getElementById('pNotice').textContent.indexOf('Added %s') === 0" % given)
    pg.wait_for_function("document.querySelectorAll('#pList li').length == 2")

    def open_addresses(name):
        li = pg.locator("#pList li", has_text=name)
        if "open" not in (li.get_attribute("class") or ""):
            li.locator("button.head").click()
        li.get_by_role("button", name="Addresses", exact=True).click()
        li.get_by_role("button", name="Add an address").wait_for()
        return li

    def fill_address(li, num, street, city="Boulder", state="CO", zipc="80302", since="", main=False):
        li.get_by_role("button", name="Add an address").click()
        form = li.locator("form.eform")
        form.get_by_label("Street address", exact=True).fill((num + " " + street).strip())
        form.get_by_label("City", exact=True).fill(city)
        form.get_by_label("State", exact=True).fill(state)
        form.get_by_label("ZIP code", exact=True).fill(zipc)
        if since: form.get_by_label("Since (optional)").fill(since)
        if main: form.get_by_label("This is the main one").check()
        return form

    li = open_addresses("Ann")
    check("no addresses yet", "No addresses yet." in li.inner_text())
    form = fill_address(li, "", "")
    form.get_by_label("City", exact=True).fill("Boulder")
    form.get_by_role("button", name="Save address").click()
    check("a city without a street address is refused on the street address box", "Add the street address" in form.inner_text() or "needs a street" in li.inner_text())
    form.get_by_label("Street address", exact=True).fill("1001 Arapahoe Ave")
    form.get_by_label("City", exact=True).fill("Boulder"); form.get_by_label("State", exact=True).fill("CO"); form.get_by_label("ZIP code", exact=True).fill("80302")
    form.get_by_label("Since (optional)").fill("13-45-2019")
    form.get_by_role("button", name="Save address").click()
    check("bad since date refused", "month first" in form.inner_text())
    form.get_by_label("Since (optional)").fill("06-2019"); form.get_by_label("This is the main one").check()
    form.get_by_role("button", name="Save address").click()
    li.locator(".mergebox").first.wait_for()
    txt = li.locator(".mergebox").first.inner_text()
    check("Ann's address shows relationship and main", "Lives here (main)" in txt)
    check("Ann's address text", "1001 Arapahoe Ave, Boulder, CO 80302" in txt)
    check("Ann's since date month first", "From Jun 2019" in txt)
    check("one place and one link saved", len(places()) == 1 and len(links()) == 1)
    check("link is for Ann and residential", links()[0]["relationship"] == "resides_at" and links()[0]["valid_from"] == "2019-06" and links()[0]["is_primary"] is True and places()[0]["is_residential"] is True)
    check("place has the US country and a primary civic address", places()[0]["addresses"][0]["country"] == "US" and places()[0]["addresses"][0]["usage"] == "civic")

    # Bob at the same address typed differently -> the ship offers the saved place
    li2 = open_addresses("Bob")
    form = fill_address(li2, "1001", "ARAPAHOE AVENUE", since="2020")
    form.get_by_role("button", name="Save address").click()
    li2.get_by_text("already saved").wait_for()
    check("saved place offered", "Use: 1001 Arapahoe Ave" in li2.inner_text())
    form.get_by_role("button", name="Continue").click()
    li2.locator(".mergebox").first.wait_for()
    check("Bob linked to the same place, none created", len(places()) == 1 and len(links()) == 2 and all(l["location_id"] == places()[0]["id"] for l in links()))

    # Ann moves: end her link
    li = pg.locator("#pList li", has_text="Ann")
    li.get_by_role("button", name="End", exact=True).click()
    li.get_by_label("Last day at this address (blank means today)").fill("03-31-2026")
    li.get_by_role("button", name="End this address").click()
    li.get_by_text("(ended)").wait_for()
    check("Ann's link shows ended with a month-first date", "until Mar 31, 2026" in li.inner_text())
    ann_link = [l for l in links() if l["valid_from"] == "2019-06"][0]
    check("stored as ended with ISO date", ann_link["status"] == "ended" and ann_link["valid_to"] == "2026-03-31")
    check("place still has Bob living there", places()[0]["is_residential"] is True)
    # a new address for Ann (the move)
    form = fill_address(li, "55", "Pine St", city="Lyons", zipc="80540", since="04-01-2026", main=True)
    li.get_by_role("button", name="Save address").click()
    li.get_by_text("55 Pine St").wait_for()
    check("a second place for the move, the first untouched", len(places()) == 2 and len(links()) == 3)

    # ---- places
    pg.select_option("#collPick", "places"); pg.wait_for_selector("#placesView:not([hidden])")
    pg.wait_for_function("document.getElementById('lChecked').textContent.length > 0")
    check("two places listed", pg.locator("#lCount").inner_text() == "2 places")
    arap = pg.locator("#lList li", has_text="Arapahoe")
    arap.locator("button.head").click()
    check("place card says someone lives here", "someone lives here" in arap.inner_text())
    arap.get_by_role("button", name="Show who is linked here").click()
    arap.get_by_text("Bob Ray").wait_for()
    t = arap.inner_text()
    check("who is linked: Bob current, Ann ended", "Bob Ray" in t and "Ann Lee" in t and "(ended)" in t)
    pg.fill("#lSearch", "lyons"); check("search by address", pg.locator("#lList li").count() == 1)
    pg.fill("#lSearch", "")
    arap = pg.locator("#lList li", has_text="Arapahoe"); arap.locator("button.head").click()

    arap.get_by_role("button", name="Add GPS point").click()
    gf = arap.locator("form.eform")
    gf.get_by_label("Latitude").fill("100"); gf.get_by_label("Longitude").fill("-105.27")
    gf.get_by_role("button", name="Add GPS point").click()
    check("bad latitude refused", "-90 to 90" in arap.inner_text())
    gf.get_by_label("Latitude").fill("40.015"); gf.get_by_label("Longitude").fill("-105.2705"); gf.get_by_label("Label (optional)").fill("front door")
    gf.get_by_role("button", name="Add GPS point").click()
    pg.wait_for_function("document.getElementById('lNotice').textContent.indexOf('Saved') === 0")
    arap = pg.locator("#lList li", has_text="Arapahoe"); arap.locator("button.head").click()
    check("GPS point saved on the place", "GPS point: center of the place (front door)" in arap.inner_text() and "40.015, -105.2705" in arap.inner_text())
    check("stored as GeoJSON longitude first", [x for x in places() if x.get("addresses") and x["addresses"][0]["street"] == "Arapahoe Ave"][0]["geometries"][0]["geometry"]["coordinates"] == [-105.2705, 40.015])
    arap.get_by_role("button", name="Add address").click()
    af = arap.locator("form.eform")
    af.get_by_label("What kind of address").select_option("mailing")
    af.get_by_label("PO box number (if it is a PO box)").fill("88"); af.get_by_label("City", exact=True).fill("Boulder"); af.get_by_label("ZIP code", exact=True).fill("80302")
    af.get_by_role("button", name="Add address").click()
    pg.wait_for_function("document.querySelectorAll('#lList li')[0] && document.getElementById('lNotice').textContent.indexOf('Saved') === 0")
    arap = pg.locator("#lList li", has_text="Arapahoe"); arap.locator("button.head").click()
    check("second address (PO box) added to the same place", "Mailing address" in arap.inner_text() and "PO Box 88" in arap.inner_text())
    arap.get_by_role("button", name="Retire").click()
    pg.locator("#lList li", has_text="Arapahoe").get_by_text("still linked").first.wait_for()
    check("retiring a linked place is refused with a clear message", "still linked" in pg.locator("#lList li", has_text="Arapahoe").inner_text())
    check("the place is still active", [x for x in places() if x.get("addresses") and x["addresses"][0].get("street") == "Arapahoe Ave"][0]["status"] == "active")
    arap = pg.locator("#lList li", has_text="Arapahoe")
    arap.get_by_role("button", name="Delete", exact=True).click(); arap.get_by_role("button", name="Delete place").click()
    pg.wait_for_timeout(500)
    check("deleting a linked place is refused", len([x for x in places() if "deleted_at" in x]) == 0)

    # add a place by itself
    pg.click("#lAddBtn")
    pg.locator("#lAddFields").get_by_label("GPS latitude (optional)").fill("40.0")
    pg.click("#lSaveBtn")
    check("GPS needs both numbers", "-180 to 180" in pg.locator("#lAddFields").inner_text())
    pg.locator("#lAddFields").get_by_label("GPS longitude (optional)").fill("-105.3")
    pg.locator("#lAddFields").get_by_label("Name of the place (optional)").fill("Trail head")
    pg.locator("#lAddFields").get_by_label("Time zone (optional)").fill("Mars/Base")
    pg.click("#lSaveBtn")
    pg.wait_for_function("document.getElementById('lFMsg').textContent.length > 0")
    check("bad time zone named", "time zone" in pg.locator("#lFMsg").inner_text().lower())
    pg.locator("#lAddFields").get_by_label("Time zone (optional)").fill("America/Denver")
    pg.click("#lSaveBtn")
    pg.wait_for_function("document.getElementById('lNotice').textContent.indexOf('Saved Trail head') === 0")
    check("place with only a name and GPS saved", any(x.get("name") == "Trail head" and x["geometries"][0]["role"] == "center" for x in places()))
    # P-94: the super admin edits a place's time zone from a short drop-down of the eight US zones
    th = pg.locator("#lList li", has_text="Trail head"); th.locator("button.head").click()
    th.get_by_role("button", name="Edit", exact=True).click()
    zsel = th.get_by_label("Time zone", exact=True)
    check("P-94 the Places edit form offers the time zone as a drop-down of the US zones", zsel.evaluate("e => e.tagName") == "SELECT" and zsel.locator("option").count() == 9 and zsel.input_value() == "America/Denver")
    zsel.select_option("America/Phoenix"); th.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('lNotice').textContent.indexOf('Saved') === 0")
    check("P-94 the chosen zone is saved on the place", [x for x in places() if x.get("name") == "Trail head"][0].get("time_zone") == "America/Phoenix")
    # a standard admin never finds or sets a time zone: the same form has no such field
    pg.evaluate("window.__me = window.ConsoleKit.me; window.ConsoleKit.me = function () { return Object.assign({}, window.__me(), { is_super_admin: false }); }")
    pg.wait_for_timeout(800); th = pg.locator("#lList li", has_text="Trail head")
    if th.get_by_role("button", name="Edit", exact=True).count() == 0: th.locator("button.head").click()
    th.get_by_role("button", name="Edit", exact=True).click()
    check("P-94 a standard admin's edit form has no time zone field", th.get_by_label("Time zone", exact=True).count() == 0 and th.get_by_label("Name", exact=True).count() == 1)
    th.get_by_role("button", name="Cancel").click()
    pg.evaluate("window.ConsoleKit.me = window.__me")
    # same address from the station: heads up, nothing merged
    pg.click("#lAddBtn")
    f2 = pg.locator("#lAddFields")
    f2.get_by_label("Street address", exact=True).fill("1001 Arapahoe Ave"); f2.get_by_label("ZIP code", exact=True).fill("80302")
    pg.click("#lSaveBtn")
    pg.wait_for_function("document.getElementById('lNotice').textContent.indexOf('Heads up') >= 0")
    check("same address reported, nothing merged", len([x for x in places() if x.get("addresses") and x["addresses"][0].get("street") == "Arapahoe Ave"]) == 2)
    # the station is its own file (the People and Places extraction, PP-2)
    import re
    big = (HERE.parent / "console" / "console.js").read_text(); mine = (HERE.parent / "console" / "places.js").read_text() + (HERE.parent / "console" / "addresses.js").read_text()
    check("places.js and addresses.js are their own files; PlacesStation and ConsoleAddresses have every hook", pg.evaluate("typeof window.PlacesStation === 'object' && ['show','reset','forget','refresh'].every(k => typeof window.PlacesStation[k] === 'function') && ['addrForm','lProblems','locAddr','locSummary','placeInput','placeText','forgetSaved'].every(k => typeof window.ConsoleAddresses[k] === 'function')"))
    check("nothing of the Places station is left in console.js", not re.search(r"function (loadPlaces|renderPlaces|placeRow|placeActions|showLinked|resetPlaces|cszRead|cszRemember|savedPlacesList|venuePlaceLine|locSummary\(loc\))|lAddBtn|lList|LISSUE|LLABEL", big))
    check("places.js and addresses.js reach the big file only through the kit", "window.ConsoleKit" in mine and "ROSTER" not in mine)
    check("the kit forwards the address form to the station", pg.evaluate("typeof window.ConsoleKit.placeInput === 'function' && typeof window.ConsoleKit.lProblems === 'function'"))
    pg.select_option("#collPick", "places"); pg.wait_for_selector("#lList li")
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("sign-out empties the Places page", pg.evaluate("document.querySelectorAll('#lList li').length === 0 && document.getElementById('lCount').textContent === '' && document.getElementById('lChecked').textContent === '' && document.getElementById('lAddForm').hidden"))
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#lList li")
    check("signing back in loads the Places page again", pg.locator("#lCount").inner_text() != "")
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()

print("\nFAILED: " + ", ".join(fails) if fails else "\nOK: all places browser checks passed")
sys.exit(1 if fails else 0)

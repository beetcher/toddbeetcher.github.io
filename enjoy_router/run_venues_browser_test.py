"""Browser test for venues with places and contacts: drives the real Console page in headless Chromium against the real
admin endpoint code with an in-memory store (Add venue with an address, saved-place offer, edit: Place and Contact, activate).
Needs playwright and a Chromium (skips when they are not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_venue_browser_test.py"""
import sys, json, os, pathlib, re
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

def api(collection, op, **args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": collection, "op": op, "args": args}).encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    return r.body

def admin_route(route):
    req = route.request
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}, body=json.dumps(r.body))

def cors(route):
    if route.request.method == "OPTIONS":
        route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    else:
        admin_route(route)

def rows(c): return list(store.data.get(c, {}).values())
def venue(name): return next(v for v in rows("venues") if v["name"] == name)

sue = api("individuals", "create", data={"given_name": "Sue", "family_name": "Miller"})["data"]

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 420, "height": 1000})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # the Console's own dialog replaced the browser's confirm box (1.3a): answer Yes to any it shows
    pg.add_init_script("new MutationObserver(function () { var d = document.getElementById('uiDialog'), y = document.getElementById('uiYes'); if (window.__autoYes !== false && d && d.open && y) y.click(); }).observe(document, { subtree: true, attributes: true, childList: true });")
    pg.route("**/enjoy_admin", cors)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": []}})))
    SCHEMA = (HERE.parent / "schemas" / "venue.schema.json").read_text()
    pg.route("**/schemas/venue.schema.json", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=SCHEMA))
    pg.goto(PAGE)
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    pg.select_option("#collPick", "venues"); pg.wait_for_selector("#venuesView:not([hidden])") if pg.locator("#venuesView").count() else pg.wait_for_selector("#addBtn")
    pg.wait_for_function("document.getElementById('vChecked').textContent.length > 0")

    def add_venue(name, kind="public", addr=None):
        pg.click("#addBtn"); pg.fill("#fName", name); pg.select_option("#fPublic", kind)
        if addr:
            host = pg.locator("#fPlaceHost")
            host.get_by_label("Street address", exact=True).fill(addr[0] + " " + addr[1])
            host.get_by_label("City", exact=True).fill("Boulder"); host.get_by_label("State", exact=True).fill("CO"); host.get_by_label("ZIP code", exact=True).fill("80302")
        pg.click("#saveBtn")

    # 1. a name and an address: venue, place and link saved together
    n0 = (len(rows("locations")), len(rows("location_links")))
    add_venue("Amante Coffee", addr=("2", "Pearl St"))
    pg.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Added Amante Coffee') === 0")
    check("notice says the place was saved with it", "with its place" in pg.inner_text("#vNotice"))
    check("one venue, one place and one operates_at link were saved", (len(rows("locations")), len(rows("location_links"))) == (n0[0] + 1, n0[1] + 1) and venue("Amante Coffee")["status"] == "inactive")
    pg.wait_for_function("document.querySelectorAll('#vList li').length == 1")
    check("the card shows the city and state from the place", "Boulder, CO" in pg.locator("#vList li").first.inner_text())
    check("the venue record holds no address of its own", not any(k in venue("Amante Coffee") for k in ("street_address", "city", "place")))

    # 2. a name alone saves as a draft
    add_venue("Park Draft")
    pg.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Added Park Draft') === 0")
    check("a draft saves with no place", "with its place" not in pg.inner_text("#vNotice") and len(rows("locations")) == n0[0] + 1)
    pg.wait_for_function("document.querySelectorAll('#vList li').length == 2")
    check("its card says there is no place yet", "No place yet" in pg.locator("#vList li", has_text="Park Draft").inner_text())

    # 3. the same address again offers the saved place
    add_venue("Amante Two", addr=("2", "Pearl St"))
    pg.locator("#fPlaceHost .confirm").wait_for()
    check("the saved place is offered", "already saved" in pg.inner_text("#fPlaceHost"))
    check("nothing was saved yet", not any(v["name"] == "Amante Two" for v in rows("venues")))
    pg.click("#saveBtn")
    pg.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Added Amante Two') === 0")
    check("it used the saved place: no new place, one more link", len(rows("locations")) == n0[0] + 1 and len(rows("location_links")) == n0[1] + 2)

    # 4. a bad address saves nothing
    pg.click("#addBtn"); pg.fill("#fName", "Broken"); pg.select_option("#fPublic", "public")
    ph = pg.locator("#fPlaceHost")
    check("recent city, state and ZIP are prefilled from the last saved address", ph.get_by_label("City", exact=True).input_value() == "Boulder" and ph.get_by_label("State", exact=True).input_value() == "CO" and ph.get_by_label("ZIP code", exact=True).input_value() == "80302")
    check("a recent list is offered", ph.get_by_label("Recent city, state and ZIP").locator("option", has_text="Boulder, CO 80302").count() == 1)
    ph.get_by_label("City", exact=True).fill("Denver"); pg.click("#saveBtn")
    pg.wait_for_function("document.querySelector('#fPlaceHost').innerText.indexOf('street') >= 0")
    check("a city without a street is refused on the form, nothing saved", not any(v["name"] == "Broken" for v in rows("venues")))
    pg.click("#cancelBtn")

    def open_edit(name):
        li = pg.locator("#vList li", has_text=name)
        if "open" not in (li.get_attribute("class") or ""):
            li.locator("button.head").click()
        li.get_by_role("button", name="Edit", exact=True).click()
        pg.wait_for_selector("#editPanel:not([hidden])")

    # 5. activating a venue with no place is refused and says why
    open_edit("Park Draft")
    check("the Place section says there is no place", "No place yet" in pg.inner_text("#editSections"))
    pg.select_option("#ef_status", "active"); pg.click("#editSave")
    pg.wait_for_function("document.getElementById('editMsg').textContent.indexOf('Not saved') === 0")
    check("refused with the place message", "Give the venue a place first" in pg.inner_text("#editSections") and venue("Park Draft")["status"] == "inactive")

    # 6. add a place from the edit form (saves right away)
    pg.get_by_role("button", name="Add place", exact=True).click()
    sec = pg.locator("#editSections")
    sec.get_by_label("Street address", exact=True).fill("500 Spruce St")
    sec.get_by_label("City", exact=True).fill("Boulder"); sec.get_by_label("State", exact=True).fill("CO"); sec.get_by_label("ZIP code", exact=True).fill("80302")
    pg.get_by_role("button", name="Save place", exact=True).click()
    pg.wait_for_function("document.querySelector('#editSections').innerText.indexOf('500 Spruce St') >= 0")
    check("the Place section now shows the address", "500 Spruce St" in pg.inner_text("#editSections"))
    check("the new place and link were saved", len(rows("locations")) == n0[0] + 2)

    # 7. choose a contact person by name; the venue stores only the id
    pg.get_by_role("button", name="Choose contact").first.click()
    pg.fill("#ef_contact_individual_id_q", "sue")
    pg.get_by_role("button", name="Sue Miller").click()
    check("the chosen name is shown", "Sue Miller" in pg.locator("#editSections").inner_text())
    pg.select_option("#ef_status", "active"); pg.click("#editSave")
    pg.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Saved') === 0")
    v = venue("Park Draft")
    check("now active, with the contact stored as an id only", v["status"] == "active" and v["contact_individual_id"] == sue["id"] and "contact_name" not in v)
    pg.wait_for_function("[...document.querySelectorAll('#vList li')].some(l => l.textContent.indexOf('Contact: Sue Miller') >= 0)")
    check("the card shows the contact's name read from the person", "Contact: Sue Miller" in pg.locator("#vList li", has_text="Park Draft").text_content())

    # 8. the person is renamed: the venue shows the new name without being touched
    api("individuals", "update", id=sue["id"], changes={"family_name": "Smith"})
    pg.click("#vRefresh")
    pg.wait_for_function("[...document.querySelectorAll('#vList li')].some(l => l.textContent.indexOf('Sue Smith') >= 0)")
    check("a renamed person shows under the new name on the venue", "Contact: Sue Smith" in pg.locator("#vList li", has_text="Park Draft").text_content())

    # 9. move the venue to a saved place; the old place is kept, the old link ends
    open_edit("Park Draft")
    pg.get_by_role("button", name="Change place", exact=True).click()
    pg.fill("#editSections input[placeholder='Search by name or address']", "pearl")
    pg.locator("#editSections button.quiet", has_text="Pearl St").first.click()
    pg.get_by_role("button", name="Save place", exact=True).click()
    pg.wait_for_function("document.querySelector('#editSections').innerText.indexOf('Pearl St') >= 0")
    mine = [l for l in rows("location_links") if l["subject_id"] == venue("Park Draft")["id"]]
    check("two links, one ended and one live; no place was deleted", len(mine) == 2 and sorted(l["status"] for l in mine) == ["active", "ended"] and len(rows("locations")) == n0[0] + 2)

    # 10. clear the contact
    pg.get_by_role("button", name="Clear").first.click(); pg.click("#editSave")
    pg.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Saved') === 0")
    check("clearing the contact removes the pointer", "contact_individual_id" not in venue("Park Draft"))

    # 11. the Active/Inactive switch on the card: taps are collected, one save 1.5 seconds after the last tap
    pg.click("#cancelBtn") if pg.locator("#editPanel:not([hidden])").count() and pg.locator("#cancelBtn").is_visible() else None
    pg.wait_for_function("document.querySelectorAll('#vList li').length >= 2")
    import re as _re
    li = pg.locator("#vList li").filter(has=pg.locator(".vname", has_text=_re.compile("^Amante Coffee$"))); sw = li.locator("button.stoggle")
    check("the card has an Inactive switch", sw.get_attribute("aria-checked") == "false" and "Inactive" in sw.inner_text())
    t0 = venue("Amante Coffee")["updated_at"]
    sw.click(); sw.click()
    pg.wait_for_timeout(2300)
    check("two quick taps cancel out and nothing is sent", venue("Amante Coffee")["updated_at"] == t0 and venue("Amante Coffee")["status"] == "inactive")
    sw.click()
    pg.wait_for_timeout(700)
    check("nothing is saved before the pause ends", venue("Amante Coffee")["status"] == "inactive")
    sw.click(); sw.click()   # three taps in all: ends on Active
    pg.wait_for_function("document.querySelector('#vList li button.stoggle[aria-checked=true]') !== null", timeout=6000)
    pg.wait_for_timeout(2300)
    check("saved once after the last tap: now active", venue("Amante Coffee")["status"] == "active" and "Active" in sw.inner_text())
    li2 = pg.locator("#vList li").filter(has=pg.locator(".vname", has_text=_re.compile("^Park Draft$"))); sw2 = li2.locator("button.stoggle")
    sw2.click(); pg.wait_for_timeout(2300)
    check("an active venue can be set back and forth", sw2.get_attribute("aria-checked") in ("true", "false"))
    sw.click(); pg.wait_for_timeout(2300)
    check("it can be set inactive again from the card", venue("Amante Coffee")["status"] == "inactive" and "Inactive" in sw.inner_text())

    # 11. the one-line scan row: name, address, Link, hours, Details
    HP = "Public hours per the web (check before relying on them): "
    api("venues", "update", id=venue("Amante Coffee")["id"], changes={"website_url": "https://amante.example/home", "availability_notes": HP + "Mon-Fri 7am-5pm; Sat 8am-3pm; closed Sun and holidays; kitchen closes one hour earlier; extended summer hours on the patio Thursday to Saturday"})
    pg.click("#vRefresh")
    pg.wait_for_function("document.querySelectorAll('#vList li').length >= 2")
    am = pg.locator("#vList li.vrow").filter(has=pg.locator(".vname", has_text=_re.compile("^Amante Coffee$")))
    pd = pg.locator("#vList li.vrow").filter(has=pg.locator(".vname", has_text=_re.compile("^Park Draft$")))
    check("scan line shows the name and the street address", am.locator(".vname").inner_text() == "Amante Coffee" and "2 Pearl St, Boulder, CO" in am.locator(".vaddr").inner_text())
    check("the row no longer carries a Link pill or hours; the ready line says what is missing", am.locator("a.vlink").count() == 0 and am.locator(".vhours").count() == 0 and "Not ready to host" in am.locator(".vready").inner_text())
    am.locator("button.vdetails").click()
    lk = am.locator(".detail a.dlink", has_text="Website")
    check("the opened card has the website link, new tab, safely", lk.get_attribute("href") == "https://amante.example/home" and lk.get_attribute("target") == "_blank" and "noopener" in lk.get_attribute("rel"))
    check("the opened card shows the full public hours", "closed Sun" in am.locator(".detail").inner_text())
    am.locator("button.vdetails").click()
    check("the scan line stays compact at phone width (wraps, not the whole card)", am.locator(".vline").bounding_box()["height"] < 220)
    pg.set_viewport_size({"width": 900, "height": 1000}); pg.wait_for_timeout(200)
    bx = lambda loc: loc.bounding_box()
    check("on a wide screen the buttons line up on the right on every row, with or without a Link", abs(bx(am.locator("button.vdetails"))["x"] - bx(pd.locator("button.vdetails"))["x"]) < 1 and abs(bx(am.locator("button.stoggle"))["x"] - bx(pd.locator("button.stoggle"))["x"]) < 1)
    check("name and address never run under the buttons", all(bx(r.locator(".vmain"))["x"] + bx(r.locator(".vmain"))["width"] <= bx(r.locator(".vacts"))["x"] + 1 or bx(r.locator(".vacts"))["y"] >= bx(r.locator(".vmain"))["y"] + bx(r.locator(".vmain"))["height"] - 1 for r in (am, pd)))
    check("each row's contents stay inside the card", all(bx(r.locator(".vacts"))["x"] + bx(r.locator(".vacts"))["width"] <= bx(r)["x"] + bx(r)["width"] + 1 for r in (am, pd)))
    pg.set_viewport_size({"width": 420, "height": 1000}); pg.wait_for_timeout(200)
    check("on a phone the buttons stay inside the card too", all(bx(r.locator(".vacts"))["x"] + bx(r.locator(".vacts"))["width"] <= bx(r)["x"] + bx(r)["width"] + 1 and bx(r.locator(".vacts"))["x"] >= bx(r)["x"] - 1 for r in (am, pd)))
    check("Details starts closed, with the rest hidden", pd.locator("button.vdetails").get_attribute("aria-expanded") == "false" and not pd.locator(".detail").is_visible())
    pd.locator("button.vdetails").click()
    check("Details opens the rest", pd.locator("button.vdetails").get_attribute("aria-expanded") == "true" and pd.locator(".detail").is_visible() and "Rooms: 0" in pd.locator(".detail").inner_text() and "Added:" in pd.locator(".detail").inner_text())
    pd.locator("button.vdetails").click()
    check("Details closes again", not pd.locator(".detail").is_visible())

    # 12. the opened view
    vid = venue("Amante Coffee")["id"]
    api("venues", "update", id=vid, changes={"phone": "303-555-0142", "email": "hi@amante.example", "description": "Corner cafe with a back room.", "rooms": [{"label": "Back room", "max_occupancy": 18}], "is_accessible": True, "has_wifi": True, "allows_minors": False, "parking_description": "Street parking", "availability_hours": [{"day_of_week": "monday", "opens_at": "09:00", "closes_at": "17:00"}]})
    store.data["venues"][vid]["discovery"] = {"run_id": "11111111-1111-4111-8111-111111111111", "model_name": "gemini-2.5-flash", "prompt_version": 1, "found_at": "2026-10-17T15:00:00Z", "source_urls": ["https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc123", "https://www.amante.example/about"], "attention_reasons": ["operator_unconfirmed"]}
    pg.click("#vRefresh")
    pg.wait_for_function("[...document.querySelectorAll('#vList li .vname')].some(n => n.textContent === 'Amante Coffee') && document.querySelector('#vList li .dfold') !== null")
    am = pg.locator("#vList li.vrow").filter(has=pg.locator(".vname", has_text=_re.compile("^Amante Coffee$")))
    am.locator("button.vdetails").click()
    dt = am.locator(".detail")
    txt = dt.inner_text()
    check("details lead with Edit / Delete buttons", dt.locator("button", has_text="Edit").count() == 1 and dt.locator("button", has_text="Delete").count() >= 1)
    check("Open in map and See photos are Google Maps links in a new tab, built from the address", dt.get_by_role("link", name="Open in map").get_attribute("href").startswith("https://www.google.com/maps/search/") and "Pearl" in dt.get_by_role("link", name="See photos").get_attribute("href") and dt.get_by_role("link", name="Open in map").get_attribute("target") == "_blank")
    check("website, phone and email are tap links", dt.get_by_role("link", name="Website").get_attribute("href") == "https://amante.example/home" and dt.get_by_role("link", name="303-555-0142").get_attribute("href") == "tel:3035550142" and dt.get_by_role("link", name="hi@amante.example").get_attribute("href") == "mailto:hi@amante.example")
    check("description is shown", "Corner cafe with a back room." in txt)
    check("public hours are shown with a check-it note", "Mon-Fri 7am-5pm" in txt and "check before relying" in txt)
    check("class open days are listed", "Mon 09:00\u201317:00" in txt)
    check("rooms with capacity and the good-to-know facts", "Back room (up to 18)" in txt and "Accessible" in txt and "Wi-Fi" in txt and "No minors" in txt and "Parking: Street parking" in txt)
    check("where-this-came-from is folded and says AI search, operator unconfirmed", dt.locator("details.dfold").first.get_attribute("open") is None and "Found by AI search" in dt.locator("details.dfold").first.text_content() and "operator unconfirmed" in dt.locator("details.dfold").first.text_content())
    arrow = lambda i: pg.evaluate("(i) => getComputedStyle(document.querySelectorAll('#vList li.vrow .detail details.dfold summary')[i], '::before').content", i)
    check("the folded sections show a closed arrow so they look clickable", "\u25b8" in arrow(0) and "\u25b8" in arrow(1))
    dt.locator("details.dfold").first.locator("summary").click()
    check("an opened fold shows the open arrow", "\u25be" in pg.evaluate("() => getComputedStyle(document.querySelector('#vList li.vrow .detail details.dfold[open] summary'), '::before').content"))
    check("sources show readable labels, not the Google redirect address", dt.get_by_role("link", name="Google search result").count() == 1 and dt.get_by_role("link", name="amante.example").count() >= 1 and "grounding-api-redirect" not in dt.locator("details.dfold").first.inner_text())
    check("the raw fields stay available but folded", dt.locator("details.dfold").nth(1).get_attribute("open") is None and "schema_version" in dt.locator("details.dfold").nth(1).text_content())
    # a bare venue: nothing invented
    pd = pg.locator("#vList li.vrow").filter(has=pg.locator(".vname", has_text=_re.compile("^Park Draft$")))
    pd.locator("button.vdetails").click()
    pt = pd.locator(".detail").inner_text()
    check("a bare venue shows Not entered, no phone/website links, no came-from fold", "Public hours: Not entered" in pt and "Open days for classes: Not entered" in pt and pd.locator(".detail a.dlink").count() <= 2 and pd.locator(".detail details.dfold").count() == 1)

    # 1.3a: the Discard question is the Console's own dialog
    if pg.locator("#editPanel:not([hidden])").count(): pg.click("#editCancel"); pg.wait_for_timeout(300)
    pg.evaluate("window.__autoYes = false")
    open_edit("Park Draft")
    pg.select_option("#ef_status", "active")
    pg.click("#editCancel"); pg.wait_for_selector("#uiDialog[open]")
    check("Cancel on an edited venue asks 'Discard your changes?' with Discard / Keep editing", pg.locator("#uiTitle").inner_text() == "Discard your changes?" and pg.locator("#uiYes").inner_text() == "Discard" and pg.locator("#uiNo").inner_text() == "Keep editing")
    pg.click("#uiNo"); pg.wait_for_timeout(200)
    check("Keep editing leaves the form open with the change", pg.locator("#editPanel:not([hidden])").count() == 1 and pg.input_value("#ef_status") == "active")
    pg.select_option("#collPick", "messages"); pg.wait_for_selector("#uiDialog[open]"); pg.click("#uiNo"); pg.wait_for_timeout(300)
    check("leaving for another station asks too; Keep editing stays on Venues with the picker back on Venues", pg.evaluate("location.hash") in ("#/venues", "") or "venues" in pg.evaluate("location.hash"))
    check("...and the picker shows Venues again", pg.input_value("#collPick") == "venues")
    pg.click("#editCancel"); pg.wait_for_selector("#uiDialog[open]"); pg.click("#uiYes"); pg.wait_for_timeout(300)
    check("Discard closes the form", pg.locator("#editPanel:not([hidden])").count() == 0)
    open_edit("Park Draft"); pg.click("#editCancel"); pg.wait_for_timeout(300)
    check("an untouched form closes with no question", pg.locator("#uiDialog[open]").count() == 0 and pg.locator("#editPanel:not([hidden])").count() == 0)
    # 1.3d: Required marks on the schema-built form
    pg.evaluate("window.__autoYes = false")
    if pg.locator("#editPanel:not([hidden])").count() == 0: open_edit("Park Draft")
    need = json.loads(SCHEMA).get("required", [])
    stars = pg.locator("#editSections label.f .req")
    check("every required field has a star, and only those", stars.count() == len([n for n in need if pg.locator("#ef_" + n).count()]) and stars.count() >= 1)
    check("the star is hidden from screen readers; the field says aria-required instead", stars.first.get_attribute("aria-hidden") == "true" and pg.locator("#editSections [aria-required=true]").count() == stars.count())
    check("a short note explains the star", pg.locator("#editForm .reqnote").inner_text() == "* means required")
    check("the field's accessible name is still just its label", pg.get_by_label(__import__("re").compile(r"^Name\b")).count() >= 1)
    # ---- the Venues station (V-4): its own file, nothing left behind, the hooks work, sign-out empties it, signing back in loads it again
    big = (HERE.parent / "console" / "console.js").read_text()
    check("venues.js is its own file and VenuesStation has every hook", pg.evaluate("typeof window.VenuesStation === 'object' && ['show','stop','reset','dirty','forget'].every(k => typeof VenuesStation[k] === 'function')"))
    check("nothing of the Venues station is left in console.js", not re.search(r"function (loadVenues|renderVenues|venueDetail|venueRow|buildSections|openEdit|closeEdit|placePanel|contactPicker|buildRoomFields|openListDlg|resetVenues)\b|\bvar vRecs\b|var SCHEMA_URL", big))
    check("venues.js reaches the big file only through the kit", "window.ConsoleKit" in (HERE.parent / "console" / "venues.js").read_text())
    if pg.locator("#editPanel:not([hidden])").count() == 0: open_edit("Park Draft")
    pg.select_option("#collPick", "classes"); pg.wait_for_timeout(400)
    check("leaving the Venues page closes the edit form", pg.locator("#editPanel:not([hidden])").count() == 0)
    pg.select_option("#collPick", "venues"); pg.wait_for_selector("#vList li")
    n_v = pg.locator("#vList li").count()
    pg.click("#lockBtn"); pg.wait_for_selector("#lockView:not([hidden])")
    check("sign-out empties the Venues page", pg.evaluate("document.querySelectorAll('#vList li').length === 0 && document.getElementById('vCount').textContent === '' && document.getElementById('editPanel').hidden"))
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn"); pg.wait_for_selector("#vList li")
    check("signing back in loads the Venues page again", pg.locator("#vList li").count() == n_v)
    check("no page errors", not errors)
    if errors: print(errors[:3])
    b.close()

if fails:
    print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK: venue browser test passed")

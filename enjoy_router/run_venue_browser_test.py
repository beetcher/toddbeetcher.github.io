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
    pg.on("dialog", lambda d: d.accept())
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
    pg.get_by_role("button", name="Choose person").first.click()
    pg.fill("#ef_contact_individual_id_q", "sue")
    pg.get_by_role("button", name="Sue Miller").click()
    check("the chosen name is shown", "Sue Miller" in pg.locator("#editSections").inner_text())
    pg.select_option("#ef_status", "active"); pg.click("#editSave")
    pg.wait_for_function("document.getElementById('vNotice').textContent.indexOf('Saved') === 0")
    v = venue("Park Draft")
    check("now active, with the contact stored as an id only", v["status"] == "active" and v["contact_individual_id"] == sue["id"] and "contact_name" not in v)
    pg.wait_for_function("document.querySelector('#vList li').innerText.indexOf('Contact: Sue Miller') >= 0 || [...document.querySelectorAll('#vList li')].some(l => l.innerText.indexOf('Contact: Sue Miller') >= 0)")
    check("the card shows the contact's name read from the person", "Contact: Sue Miller" in pg.locator("#vList li", has_text="Park Draft").inner_text())

    # 8. the person is renamed: the venue shows the new name without being touched
    api("individuals", "update", id=sue["id"], changes={"family_name": "Smith"})
    pg.click("#vRefresh")
    pg.wait_for_function("[...document.querySelectorAll('#vList li')].some(l => l.innerText.indexOf('Sue Smith') >= 0)")
    check("a renamed person shows under the new name on the venue", "Contact: Sue Smith" in pg.locator("#vList li", has_text="Park Draft").inner_text())

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
    pg.select_option("#vFilter", "") if pg.locator("#vFilter").count() else None
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

    check("no page errors", not errors)
    if errors: print(errors[:3])
    b.close()

if fails:
    print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK: venue browser test passed")

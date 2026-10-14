"""Browser test for the Organizations station: drives the real Console page in headless Chromium against the real
admin endpoint code with an in-memory store. Needs playwright and a Chromium (skips when not there). Nothing touches Firebase.
Run from enjoy_router/:  python3 run_organization_browser_test.py"""
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
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

def admin_route(route):
    req = route.request
    r = handle_admin(req.method, req.headers.get("authorization", ""), (req.post_data or "").encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    route.fulfill(status=r.status, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}, body=json.dumps(r.body))

def cors(route):
    if route.request.method == "OPTIONS":
        route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    else:
        admin_route(route)


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(viewport={"width": 375, "height": 800})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("**/enjoy_admin", cors)
    pg.route("**/enjoy_console_records*", lambda r: r.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}, body=json.dumps({"ok": True, "data": {"records": []}})))
    pg.goto(PAGE)
    pg.fill("#keyInput", KEY); pg.click("#unlockBtn")
    pg.wait_for_selector("#homeView:not([hidden])")
    check("Organizations tile on Home", pg.locator("#stationTiles .tile .tname", has_text="Organizations").count() == 1)
    pg.select_option("#collPick", "organizations")
    pg.wait_for_selector("#organizationsView:not([hidden])")
    pg.wait_for_function("document.getElementById('roChecked').textContent.length > 0")
    check("empty state", pg.locator("#roEmpty").is_visible())
    check("no sideways scroll at 375 px", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    pg.click("#roAddBtn"); pg.click("#roSaveBtn")
    check("name required", pg.locator("#roA_name ~ .ferr").inner_text() == "Required.")
    pg.fill("#roA_name", "Ozo Coffee"); pg.locator("#roA_kinds label", has_text="Business").locator("input").check()
    pg.fill("#roA_short_name", "Ozo"); pg.fill("#roA_website_url", "ozo"); pg.fill("#roA_email", "  Hello@Example.COM ")
    pg.click("#roSaveBtn")
    pg.wait_for_function("document.querySelector('#roA_website_url ~ .ferr').textContent.length > 0")
    check("bad web address shown on its field", "format" in pg.locator("#roA_website_url ~ .ferr").inner_text().lower())
    pg.fill("#roA_website_url", "https://example.com/ozo"); pg.click("#roSaveBtn"); pg.wait_for_selector("#roList li")
    txt = pg.locator("#roList").inner_text()
    check("listed with kind and short name", "Ozo Coffee" in txt and "Business" in txt and "Ozo" in txt, txt)
    check("added notice", "Added Ozo Coffee" in pg.locator("#roNotice").inner_text())
    saved = [r for r in store.data.get("organizations", {}).values()]
    check("saved tidy: email lowercased, kinds list", len(saved) == 1 and saved[0].get("email") == "hello@example.com" and saved[0].get("kinds") == ["business"], saved)
    pg.click("#roAddBtn"); pg.fill("#roA_name", "Boulder Valley School District"); pg.locator("#roA_kinds label", has_text="School district").locator("input").check()
    pg.fill("#roA_short_name", "BVSD"); pg.click("#roSaveBtn")
    pg.wait_for_function("document.querySelectorAll('#roList li').length == 2")
    check("two organizations, sorted by name", pg.locator("#roList li .vname").all_inner_texts() == ["Boulder Valley School District", "Ozo Coffee"], pg.locator("#roList li .vname").all_inner_texts())
    pg.fill("#roSearch", "bvsd")
    check("search finds by short name", pg.locator("#roList li").count() == 1 and "shown of 2" in pg.locator("#roCount").inner_text(), pg.locator("#roCount").inner_text())
    pg.fill("#roSearch", "")
    pg.wait_for_function("document.querySelectorAll('#roList li').length == 2")
    li = pg.locator("#roList li", has_text="Ozo Coffee")
    li.locator("button.head").click(); li.get_by_role("button", name="Edit", exact=True).click()
    form = li.locator("form.eform")
    form.locator("summary").click()
    form.locator("textarea[id$='_identifiers']").fill("nonsense")
    form.get_by_role("button", name="Save changes").click()
    check("bad identifier line refused on its field", "type: value" in form.locator("textarea[id$='_identifiers'] ~ .ferr").inner_text())
    form.locator("textarea[id$='_identifiers']").fill("EIN: 00-0000000")
    form.locator("textarea[id$='_aliases']").fill("Ozo's\nOzo Roasters")
    form.locator("input[id$='_founded_date']").fill("2005")
    form.get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.getElementById('roNotice').textContent.indexOf('Saved') === 0")
    rec = [r for r in store.data["organizations"].values() if r["name"] == "Ozo Coffee"][0]
    check("identifier and aliases saved", rec.get("identifiers") == [{"type": "ein", "value": "00-0000000"}] and rec.get("aliases") == ["Ozo's", "Ozo Roasters"] and rec.get("founded_date") == "2005", rec)
    pg.wait_for_function("document.getElementById('roList').textContent.indexOf('00-0000000') >= 0")
    check("card shows the identifier", True)
    pg.fill("#roSearch", "roasters")
    check("search finds by other name", pg.locator("#roList li").count() == 1)
    pg.fill("#roSearch", "")
    # closed leaves the Active list, shows under Closed
    li = pg.locator("#roList li", has_text="Boulder Valley"); li.locator("button.head").click(); li.get_by_role("button", name="Edit", exact=True).click()
    li.locator("form.eform select").select_option("closed"); li.locator("form.eform").get_by_role("button", name="Save changes").click()
    pg.wait_for_function("document.querySelectorAll('#roList li').length == 1")
    check("closed leaves the Active list", "Boulder" not in pg.locator("#roList").inner_text())
    pg.select_option("#roFilter", "closed")
    check("closed shows under Closed", pg.locator("#roList li", has_text="Boulder Valley").count() == 1)
    # one-tap switch
    pg.select_option("#roFilter", "")
    pg.wait_for_selector("#roList li button.stoggle")
    li = pg.locator("#roList li", has_text="Ozo Coffee"); sw = li.locator("button.stoggle")
    sw.click(); pg.wait_for_timeout(2400)
    check("the switch saves inactive after the pause", [r["status"] for r in store.data["organizations"].values() if r["name"] == "Ozo Coffee"] == ["inactive"])
    # delete
    li = pg.locator("#roList li", has_text="Boulder Valley"); li.locator("button.head").click()
    li.get_by_role("button", name="Delete", exact=True).click(); li.get_by_role("button", name="Delete organization").click()
    pg.wait_for_function("document.querySelectorAll('#roList li').length == 1")
    check("deleted", "Deleted" in pg.locator("#roNotice").inner_text())
    check("deleted record kept, marked", any("deleted_at" in r for r in store.data["organizations"].values() if r["name"].startswith("Boulder")))
    pg.click("#organizationsView .manualBtn")
    check("Organizations manual opens", pg.locator("#manual h2", has_text="Organizations").is_visible())
    check("no sideways scroll after use", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
    check("no page errors", errors == [])
    if errors: print(errors)
    b.close()
print("\n%s" % ("FAILED: " + ", ".join(fails) if fails else "OK: all organization browser checks passed"))
sys.exit(1 if fails else 0)

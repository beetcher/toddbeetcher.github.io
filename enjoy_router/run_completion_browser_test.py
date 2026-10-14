#!/usr/bin/env python3
"""Browser test for the completion link: the private page opened with ?r=<token> shows the request filled in, saves ONLY what changed to that
same request, and refuses politely when the link is wrong or the request is already placed. Headless Chromium, in-memory store.
Run from enjoy_router/:  python3 run_completion_browser_test.py"""
import sys, json, os, pathlib, uuid
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone
from core import Schemas, handle_registration_request
from crud.memory_doc_store import MemoryDocStore
from crud import attendances_service as AT, individuals_service as IS, scheduled_classes_crud as CL
from memory_store import MemoryStore
from ratelimit import RateLimiter
import request_completion as RC
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

FORM = (HERE.parent / "enjoy" / "register" / "private" / "index.html").as_uri()
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)))
    if not ok: fails.append(label)

NOW = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
VEN, CUR1, CUR2 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
schemas = Schemas.load()
reg = MemoryStore([], [{"id": VEN, "status": "active", "is_public_venue": True}], [{"id": CUR1, "status": "active"}, {"id": CUR2, "status": "active"}])
ds = MemoryDocStore(""); limiter = RateLimiter(rules=((600, 1000),))
ds.create("venues", VEN, {"id": VEN, "status": "active", "is_public_venue": True})
for c in (CUR1, CUR2): ds.create("curriculums", c, {"id": c, "status": "active"})
def make(email, **kw):
    body = {"registration_type": "private", "idempotency_key": str(uuid.uuid4()), "first_name": "Sam", "last_name": "Test", "email": email, "consent_to_contact": True,
            "presented_cost_cents": 50000, "presented_cost_basis": "per_session", "duration_minutes_requested": 120, **kw}
    r = handle_registration_request(body, reg, schemas, now=NOW); assert r.outcome == "created", (r.error_code, r.field_errors)
    ds.create(RC.COLLECTION, r.doc["id"], dict(r.doc)); return r.doc
FULL = make("sam@example.com", is_requester_attending=True, has_minors_present=False, attendee_count=2, postal_code="80026", curriculum_id=CUR2,
            location_type="off_site", preferred_venue_id=VEN, what_they_want="Plan a trip", requested_date="2026-12-01")
PLACED = make("placed@example.com")
ind = IS.create(ds, {"given_name": "P", "family_name": "L"}, "user:admin", now=NOW).data
cls = CL.create(ds, {"title": "Private session", "slug": "p9", "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
                     "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2}, "user:admin", now=NOW).data
assert AT.create(ds, {"individual_id": ind["id"], "scheduled_class_id": cls["id"], "role": "student", "request_id": PLACED["id"]}, "user:admin", now=NOW).ok
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Content-Type": "application/json"}
LIST = {"ok": True, "data": {"curriculums": [{"id": CUR1, "title": "Start here with AI"}, {"id": CUR2, "title": "Photos and memories"}]}}
VENUES = {"ok": True, "data": {"venues": [{"id": VEN, "name": "Boulder Library", "town": "Boulder", "miles": 3.2}]}}

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    posts, gets, newregs = [], [], []
    def completion(route):
        rq = route.request
        if rq.method == "OPTIONS":
            route.fulfill(status=204, headers={**CORS, "Access-Control-Allow-Methods": "*"}); return
        params = dict(pair.split("=", 1) for pair in rq.url.split("?", 1)[1].split("&")) if "?" in rq.url else {}
        raw = (rq.post_data or "").encode()
        if rq.method == "POST": posts.append(json.loads(rq.post_data))
        else: gets.append(params.get("t"))
        r = RC.handle_completion(rq.method, params, raw, "v", ds, schemas, limiter, NOW)
        route.fulfill(status=r.status, headers=CORS, body=json.dumps(r.body))
    def page(token, errs=None):
        pg = b.new_page(viewport={"width": 420, "height": 1000})
        if errs is not None: pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/enjoy_public_venues*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps(VENUES)))
        pg.route("**/enjoy_public_curriculums*", lambda r: r.fulfill(status=200, headers=CORS, body=json.dumps(LIST)))
        pg.route("**/enjoy_request_completion*", completion)
        pg.route("**/enjoy-registration-request*", lambda r: (newregs.append(1), r.abort()))
        pg.goto(FORM + ("?r=" + token if token else "")); return pg
    def stored(): return ds.get(RC.COLLECTION, FULL["id"])

    # ---- a good link
    errs = []; pg = page(FULL["completion_token"], errs)
    pg.wait_for_selector("button[type=submit]:has-text('Save my details')")
    pg.wait_for_selector("select[name=curriculum_id] option[value]:not([value=''])", state="attached")
    pg.wait_for_selector("input[name=location_type][value='venue:%s']" % VEN, state="attached")
    check("the page says it is finishing a request and names it", "Finish your request" in pg.inner_text("h1") and FULL["confirmation_number"] in pg.inner_text(".reg__note:not(:first-of-type), main"))
    check("name and email are filled in and cannot be edited", pg.input_value("input[name=first_name]") == "Sam" and pg.input_value("input[name=email]") == "sam@example.com"
          and pg.eval_on_selector("input[name=email]", "e => e.readOnly") and pg.eval_on_selector("input[name=first_name]", "e => e.readOnly"))
    check("the details section is open with their answers", pg.evaluate("document.querySelector('details.rf__more').open") and pg.input_value("input[name=attendee_count]") == "2"
          and pg.input_value("textarea[name=what_they_want]") == "Plan a trip" and pg.input_value("input[name=requested_date]") == "2026-12-01")
    check("their ZIP, curriculum and venue are chosen", pg.input_value("input[name=postal_code]") == "80026" and pg.input_value("select[name=curriculum_id]") == CUR2
          and pg.is_checked("input[name=location_type][value='venue:%s']" % VEN))
    check("taking part and minors answers are filled in", pg.is_checked("input[name=is_requester_attending][value=yes]") and pg.is_checked("input[name=has_minors_present][value=no]"))
    check("the OK-to-contact box and checklist are out of the way", not pg.locator("input[name=consent_to_contact]").is_visible() and not pg.locator("#rf-need").is_visible())
    check("the link was read once with the right token", gets == [FULL["completion_token"]], gets)
    # change one thing
    pg.fill("input[name=how_heard]", "A friend"); pg.click("button[type=submit]")
    pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("only the changed answer is sent", len(posts) == 1 and posts[0]["changes"] == {"how_heard": "A friend"} and posts[0]["t"] == FULL["completion_token"], posts)
    check("no name, email, key or type is sent", not ({"first_name", "email", "idempotency_key", "registration_type", "consent_to_contact"} & set(posts[0]["changes"])))
    check("the thank-you shows the same confirmation number", "Your details are saved" in pg.inner_text("#rf-done h2") and FULL["confirmation_number"] in pg.inner_text("#rf-done"))
    check("the same request was updated", stored()["how_heard"] == "A friend" and stored()["updated_by"] == "web:completion" and stored()["confirmation_number"] == FULL["confirmation_number"])
    check("no new request was sent to the registration endpoint", not newregs)
    check("nothing was saved as a draft on this device", pg.evaluate("window.localStorage.getItem('icdt_reg_draft_private')") is None)
    check("no script errors", not errs, errs)
    # change several, clear one
    posts.clear(); pg = page(FULL["completion_token"]); pg.wait_for_selector("button[type=submit]:has-text('Save my details')")
    pg.wait_for_selector("input[name=location_type][value='venue:%s']" % VEN, state="attached")
    pg.fill("input[name=attendee_count]", "3"); pg.fill("textarea[name=what_they_want]", ""); pg.select_option("select[name=curriculum_id]", CUR1)
    pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('rf-done').getAttribute('data-show') === '1'")
    check("changes and a cleared answer are sent as such", posts and posts[0]["changes"] == {"attendee_count": 3, "what_they_want": None, "curriculum_id": CUR1}, posts)
    s = stored()
    check("saved: count and curriculum changed, the cleared answer gone, the venue and ZIP kept", s["attendee_count"] == 3 and s["curriculum_id"] == CUR1 and "what_they_want" not in s
          and s["preferred_venue_id"] == VEN and s["postal_code"] == "80026")
    # a server refusal shows on the page
    posts.clear(); pg = page(FULL["completion_token"]); pg.wait_for_selector("button[type=submit]:has-text('Save my details')")
    pg.fill("input[name=postal_code]", "80026"); pg.fill("input[name=requested_date]", "2026-10-01")
    pg.click("button[type=submit]"); pg.wait_for_timeout(600)
    check("a date in the past is stopped on the page and nothing is sent", pg.locator(".rf__error[data-show='1']").count() >= 1 and not posts)

    # ---- bad links
    gets.clear(); pg = page("A" * 43)
    pg.wait_for_function("document.querySelector('.reg__note') && document.body.innerText.indexOf('did not open a request') >= 0")
    check("an unknown link falls back to an ordinary new request form", pg.locator("form#rf").is_visible() and "Schedule a one on one" in pg.inner_text("h1") and pg.locator("input[name=first_name]").input_value() == ""
          and not pg.eval_on_selector("input[name=first_name]", "e => e.readOnly"))
    gets.clear(); pg = page("abc"); pg.wait_for_selector("input[name=first_name]")
    check("a link of the wrong shape is ignored without asking the server", not gets and pg.locator("form#rf").is_visible() and "Schedule a one on one" in pg.inner_text("h1"))
    # ---- already placed
    pg = page(PLACED["completion_token"])
    pg.wait_for_function("document.body.innerText.indexOf('already been scheduled') >= 0")
    check("a placed request says so and offers no form", not pg.locator("form#rf").is_visible() and PLACED["confirmation_number"] in pg.inner_text("main"))
    b.close()
print("\n" + ("FAILED: " + "; ".join(fails) if fails else "OK: all completion-link browser checks pass")); sys.exit(1 if fails else 0)

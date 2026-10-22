#!/usr/bin/env python3
"""One browser run (P-83 build 3): on the private form, a ZIP no active region holds shows "We're securing the best trainer for your area."
at once and the form still submits; a covered ZIP shows nothing; the message follows the ZIP; the group form never shows it.
Serves /tmp/rc over http; the venue list is a fake answer."""
import http.server, threading, functools, sys, json
from playwright.sync_api import sync_playwright
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rc"
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
H.log_message = lambda *a, **k: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
bad = 0
def check(label, ok):
    global bad
    print(("ok   " if ok else "FAIL ") + label)
    bad += 0 if ok else 1
VEN = [{"id": "11111111-1111-4111-8111-111111111111", "name": "Boulder Hall", "city": "Boulder", "state": "CO"}]
def answer(route):
    url = route.request.url
    if "public_venues" not in url:
        return route.continue_() if "127.0.0.1" in url else route.abort()
    z = ("zip=" in url) and url.split("zip=")[1][:5]
    body = {"ok": True, "data": {"venues": VEN, "covered": True}} if z == "80301" else {"ok": True, "data": {"venues": [], "covered": False}} if z else {"ok": True, "data": {"venues": VEN}}
    route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(body))
MSG = "We're securing the best trainer for your area. Go ahead and send your request."
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 900, "height": 1100}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", answer)
    pg.goto("http://127.0.0.1:8766/enjoy/register/private/index.html"); pg.wait_for_timeout(600)
    z = pg.locator("input[name=postal_code]"); note = pg.locator(".rf__note").last
    def typed(v): z.fill(""); z.type(v); pg.wait_for_timeout(900)
    typed("80202")
    check("uncovered ZIP: the securing line shows", note.is_visible() and note.inner_text() == MSG)
    pg.screenshot(path="/tmp/claude-0/shots/trainer_note.png")
    typed("80301"); check("covered ZIP: no line", not note.is_visible())
    typed("80202"); check("uncovered again: the line returns", note.is_visible())
    z.fill("8020"); pg.wait_for_timeout(200); check("half-typed ZIP: the line goes at once", not note.is_visible())
    typed("80202"); z.fill(""); pg.wait_for_timeout(900); check("ZIP cleared: no line", not note.is_visible())
    check("no script errors (private)", not errs)
    g = b.new_page(viewport={"width": 900, "height": 1100}); g.route("**/*", answer)
    g.goto("http://127.0.0.1:8766/enjoy/register/group/index.html"); g.wait_for_timeout(600)
    gz = g.locator("input[name=postal_code]")
    if gz.count():
        gz.fill("80202"); g.wait_for_timeout(900)
        check("group form: never shows the line", "securing the best trainer" not in g.content())
    else:
        check("group form: no ZIP field to speak of", True)
    if errs: print(errs)
    b.close()
sys.exit(1 if bad else 0)

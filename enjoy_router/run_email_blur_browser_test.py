#!/usr/bin/env python3
"""One browser run: the private form checks email and ZIP when the cursor leaves the field. Serves /tmp/rc over http."""
import http.server, threading, functools, sys, pathlib
from playwright.sync_api import sync_playwright
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rc"
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
H.log_message = lambda *a, **k: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
bad = 0
def check(label, ok):
    global bad
    print(("ok   " if ok else "FAIL ") + label)
    bad += 0 if ok else 1
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 900, "height": 1100}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if "127.0.0.1" not in r.request.url else r.continue_())
    pg.goto("http://127.0.0.1:8765/enjoy/register/private/index.html"); pg.wait_for_timeout(600)
    em = pg.locator("input[name=email]"); err = pg.locator("#" + (em.get_attribute("id") or "") + "-err")
    def leave(v):
        em.fill(v); pg.keyboard.press("Tab"); pg.wait_for_timeout(120)
        return err.inner_text().strip(), err.is_visible()
    t, vis = leave("joinlaunchnow@gmail+barry")
    check("plus typo: red message shown at once on leaving: " + t, vis and "+barry" in t and "joinlaunchnow+barry@gmail.com" in t)
    check("field is outlined red", em.get_attribute("aria-invalid") == "true")
    pg.screenshot(path="/tmp/claude-0/shots/email_blur_plus.png")
    t, vis = leave("joinlaunchnow@gmail.com+barry"); check("plus after .com: suggestion: " + t, vis and "joinlaunchnow+barry@gmail.com" in t)
    t, vis = leave("no-at-sign.com"); check("no @: " + t, vis and "needs an @" in t)
    t, vis = leave("a@@b.com"); check("two @: " + t, vis and "only have one @" in t)
    t, vis = leave("a b@c.com"); check("spaces: " + t, vis and "spaces" in t)
    t, vis = leave("name@gmail"); check("no dot: " + t, vis and ".com" in t)
    # live clearing: while the message is showing, fixing the entry clears it at once
    em.fill("name@gmail"); pg.keyboard.press("Tab"); em.focus(); pg.keyboard.type(".com"); pg.wait_for_timeout(120)
    check("message clears while typing once the address is right", not err.is_visible() and em.get_attribute("aria-invalid") is None)
    check("checklist ticks Your email", "✓" in pg.locator("text=Your email").first.inner_text())
    t, vis = leave(""); check("empty field: no scolding on Tab", not vis)
    t, vis = leave("name+test24@gmail.com"); check("plus tag before @ is fine", not vis)
    t, vis = leave("pat@gmial.com"); note = pg.locator(".rf__note")
    check("typo domain: soft question, not an error", not vis and note.is_visible() and "pat@gmail.com" in note.inner_text())
    pg.screenshot(path="/tmp/claude-0/shots/email_blur_typo.png")
    pg.locator(".rf__use", has_text="Yes").click(); pg.wait_for_timeout(100)
    check("Yes, use that fixes the field", em.input_value() == "pat@gmail.com" and not note.is_visible())
    for bad_dom, want in (("joinlaunchnow+barry22@gmali.com", "joinlaunchnow+barry22@gmail.com"), ("a@gnail.com", "a@gmail.com"), ("a@hotmial.com", "a@hotmail.com")):
        t, vis = leave(bad_dom)
        check("caught slip %s -> %s" % (bad_dom, want), not vis and note.is_visible() and want in note.inner_text())
    for fine in ("a@mail.com", "a@ymail.com", "a@smithco.com", "a@gmail.com", "a@boulderschools.net"):
        t, vis = leave(fine)
        check("not questioned: " + fine, not note.is_visible())
    t, vis = leave("a@gmali.com"); pg.locator(".rf__use", has_text="No").click(); pg.wait_for_timeout(100)
    check("No, keep mine hides the question", not note.is_visible() and em.input_value() == "a@gmali.com")
    t, vis = leave("a@gmali.com"); check("...and it is not asked again for the same address", not note.is_visible())
    zip_ = pg.locator("input[name=postal_code]")
    zip_.fill("5484"); pg.keyboard.press("Tab"); pg.wait_for_timeout(100)
    zerr = pg.locator("#" + zip_.get_attribute("id") + "-err")
    check("short ZIP: message shown: " + zerr.inner_text(), zerr.is_visible() and "five-digit" in zerr.inner_text())
    zip_.fill("54843"); pg.wait_for_timeout(100); check("ZIP message clears when right", not zerr.is_visible())
    check("no script errors", not errs)
    if errs: print(errs)
    b.close()
print("\nOK" if not bad else "\n%d FAILED" % bad); sys.exit(1 if bad else 0)

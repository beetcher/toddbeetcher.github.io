#!/usr/bin/env python3
"""Browser test (Console step 1.5): the sign-in screen carries the logo and hero picture from the settings file (split screen on desktop, a band on a phone); Home has no picture and no ship talk; a licensee can swap logo, picture, name and tab icons in console-config.js alone. Run from enjoy_router/:  python3 run_console_signin_screen_browser_test.py"""
import sys, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

CON = HERE.parent / "console"
PAGE = (CON / "index.html").as_uri()
CONFIG_SRC = (CON / "console-config.js").read_text()
SHOTS = pathlib.Path("/tmp/claude-0/shots"); SHOTS.mkdir(parents=True, exist_ok=True)
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

def launch(p):
    exe = "/opt/pw-browsers/chromium"
    return p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
def open_page(b, w, config=None):
    ctx = b.new_context(viewport={"width": w, "height": 900}); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    if config is not None:
        pg.route("**/console-config.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=config))
    pg.goto(PAGE); pg.wait_for_selector("#lockView:not([hidden])"); pg.wait_for_timeout(300)
    return pg, errs
def box(pg, sel): return pg.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; }", sel)

html = (CON / "index.html").read_text()
home = html[html.index('<section id="homeView"'):html.index('<div class="stations">')]
check("Home markup has no picture", "<img" not in home and "<figure" not in home)
check("Home has no ship talk in the welcome ('Welcome aboard', 'production console will look different', 'bridge')", not re.search(r"aboard|will look different|bridge", home, re.I))
check("the settings file names logo, logoSmall, hero (image, alt) and icons", all(k in CONFIG_SRC for k in ("logo:", "logoSmall:", "hero:", "image:", "alt:", "icons:")))

with sync_playwright() as p:
    b = launch(p)

    pg, errs = open_page(b, 1440)
    h, f = box(pg, "#lockHero"), box(pg, ".lockpanel")
    check("desktop: picture and sign-in panel sit side by side, picture on the left", h["r"] <= f["l"] + 1 and abs(h["t"] - f["t"]) < 400 and h["l"] < f["l"], (h, f))
    check("desktop: the picture loaded", pg.evaluate("document.getElementById('heroImg').naturalWidth") > 0)
    check("desktop: logo loaded and the title says 'LAUNCH Console'", pg.evaluate("document.getElementById('lockLogo').naturalWidth") > 0 and pg.inner_text("#lockTitle") == "LAUNCH Console")
    check("desktop: the picture has a description for screen readers", len(pg.get_attribute("#heroImg", "alt") or "") > 20)
    check("desktop: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth") <= 1440)
    check("desktop: the form still works (key box, Unlock, Remember all visible)", all(pg.locator(s).is_visible() for s in ("#keyInput", "#unlockBtn", "#rememberBox")))
    check("desktop: the top bar logo comes from the settings and the link names the brand", pg.get_attribute("#brand", "aria-label") == "LAUNCH Console: go to Home" and "launch-tile-mobile" in pg.get_attribute("#brand img", "src"))
    check("desktop: the tab icons come from the settings", "console-favicon-32" in pg.get_attribute("#icon32", "href") and "console-touch-180" in pg.get_attribute("#iconTouch", "href"))
    check("desktop: no page errors", not errs, errs)
    pg.screenshot(path=str(SHOTS / "signin-1440.png"))

    pg, errs = open_page(b, 1024)
    h, f = box(pg, "#lockHero"), box(pg, ".lockpanel")
    check("1024 wide: still side by side, nothing sideways", h["r"] <= f["l"] + 1 and pg.evaluate("document.documentElement.scrollWidth") <= 1024, (h, f))

    pg, errs = open_page(b, 390)
    h, f = box(pg, "#lockHero"), box(pg, ".lockpanel")
    check("phone: the picture is a band above the sign-in panel", h["b"] <= f["t"] + 1 and h["w"] > 300, (h, f))
    check("phone: the band is short (under 215 px) so the form stays near the top", h["h"] < 215, h)
    check("phone: the Unlock button is on the first screen", box(pg, "#unlockBtn")["b"] < 844)
    check("phone: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth") <= 390)
    pg.screenshot(path=str(SHOTS / "signin-390.png"))

    # a licensee changes only the settings file
    swapped = CONFIG_SRC.replace('brandName: "LAUNCH"', 'brandName: "Acme Academy"').replace('logo: "assets/console-touch-180.png"', 'logo: "assets/launch-tile.webp"') \
        .replace('image: "assets/bridge.webp"', 'image: "assets/launch-tile.webp"').replace('caption: ""', 'caption: "Learn here"').replace('console-favicon-32.png', 'console-favicon-48.png')
    assert swapped != CONFIG_SRC and "Acme Academy" in swapped
    pg, errs = open_page(b, 1440, swapped)
    check("swap: title uses the new brand name", pg.inner_text("#lockTitle") == "Acme Academy Console" and pg.inner_text("#appName") == "Acme Academy")
    check("swap: the new logo and picture are shown", "launch-tile.webp" in pg.get_attribute("#lockLogo", "src") and "launch-tile.webp" in pg.get_attribute("#heroImg", "src") and pg.get_attribute("#lockLogo", "alt") == "Acme Academy")
    check("swap: the picture caption shows when given", pg.is_visible("#heroCap") and pg.inner_text("#heroCap").lower() == "learn here")
    check("swap: the tab icon follows the settings", "console-favicon-48" in pg.get_attribute("#icon32", "href"))
    check("swap: the top bar link names the new brand", pg.get_attribute("#brand", "aria-label") == "Acme Academy Console: go to Home")
    check("swap: no page errors", not errs, errs)

    # no hero configured: no empty hole, the form is centred
    nohero = re.sub(r'image: "assets/bridge.webp",', '', CONFIG_SRC)
    assert nohero != CONFIG_SRC
    pg, errs = open_page(b, 1440, nohero)
    f = box(pg, ".lockpanel")
    check("no picture configured: the picture block is hidden and the form is centred", not pg.is_visible("#lockHero") and abs((f["l"] + f["r"]) / 2 - 720) < 40, f)
    check("no picture configured: no page errors", not errs, errs)
    b.close()

print("\n%d failed" % len(fails) if fails else "\nall passed"); sys.exit(1 if fails else 0)

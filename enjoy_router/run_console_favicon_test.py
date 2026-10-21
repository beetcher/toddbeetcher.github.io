#!/usr/bin/env python3
"""Console favicon test: the Console page carries its own icon links (so it never falls back to the site's /favicon.ico), every link points at a
real PNG of the size it claims, the touch icon is square 180, and the page loads each image in a real browser.
Run from enjoy_router/:  python3 run_console_favicon_test.py"""
import sys, re, struct, pathlib, os
HERE = pathlib.Path(__file__).resolve().parent; CON = HERE.parent / "console"
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)
html = (CON / "index.html").read_text(encoding="utf-8")
head = html.split("</head>")[0]
links = re.findall(r'<link\s+rel="(icon|apple-touch-icon)"([^>]*)>', head)
def attr(a, n):
    m = re.search(n + r'="([^"]*)"', a); return m.group(1) if m else ""
icons = [(attr(a, "href"), attr(a, "sizes")) for r, a in links if r == "icon"]
touch = [attr(a, "href") for r, a in links if r == "apple-touch-icon"]
check("F1 the Console page declares its own icons (16, 32 and 48)", sorted(s for _, s in icons) == ["16x16", "32x32", "48x48"], icons)
check("F2 and a touch icon", len(touch) == 1, touch)
def png_size(path):
    b = path.read_bytes()
    if b[:8] != b"\x89PNG\r\n\x1a\n": return None
    return struct.unpack(">II", b[16:24])
for href, sizes in icons:
    p = CON / href; want = tuple(int(x) for x in sizes.split("x"))
    check("F3 %s exists, is a PNG and is %s" % (href, sizes), p.exists() and png_size(p) == want, png_size(p) if p.exists() else "missing")
for href in touch:
    p = CON / href; check("F4 touch icon %s is a 180 square PNG" % href, p.exists() and png_size(p) == (180, 180))
check("F5 the icon links come before the title and no script block carries them", head.index('rel="icon"') < head.index("<title>"))
check("F6 icon files are the Console's own, not the site's", all("console-" in h for h, _ in icons) and all("console-" in h for h in touch))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("note: playwright not installed, browser half skipped"); sys.exit(1 if fails else 0)
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    pg = b.new_page(); pg.goto((CON / "index.html").as_uri())
    res = pg.evaluate("""() => Promise.all([...document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')].map(l => new Promise(r => { const i = new Image(); i.onload = () => r([l.getAttribute('href'), i.naturalWidth]); i.onerror = () => r([l.getAttribute('href'), 0]); i.src = l.href; })))""")
    check("F7 the browser loads every icon image", len(res) == 4 and all(w > 0 for _, w in res), res)
    b.close()
print("\nOK: all favicon checks pass" if not fails else "\nFAILED: " + "; ".join(fails)); sys.exit(1 if fails else 0)

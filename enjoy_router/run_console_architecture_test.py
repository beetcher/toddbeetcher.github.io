#!/usr/bin/env python3
"""Console architecture rules (console/ARCHITECTURE.md), checked without a browser.

  1. console.js may not grow past CAP. It only shrinks. Extract a station, then LOWER the cap to the new size (never raise it).
  2. Every station file has a browser test: enjoy_router/run_<name>*_browser_test.py that loads console/index.html.
  3. Every script in console/ is loaded by index.html, every script index.html loads exists, and the order is legal
     (shared files, then console.js, then station files).
  4. A station file reaches the big file only through ConsoleKit, and exposes window.<Name>Station with show and reset.

Run from enjoy_router/:  python3 run_console_architecture_test.py
CONSOLE_DIR (environment) points the test at another copy of console/ (used to prove the test can fail)."""
import os, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
CON = pathlib.Path(os.environ.get("CONSOLE_DIR") or (HERE.parent / "console"))
CAP = 6214          # lines in console.js after the Attendance chip filters (2026-10-23; Messages extraction left it at 6,216). LOWER this after each extraction; never raise it.
SHARED = ["firebase-config.js", "console-config.js", "ui.js", "filters.js"]   # load before console.js
LEGACY = "console.js"
fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

big = (CON / LEGACY).read_text()
n = len(big.split("\n")) - (1 if big.endswith("\n") else 0)
check("console.js has not grown: %d lines, cap %d" % (n, CAP), n <= CAP, "grew by %d lines; new station code goes in its own file (console/ARCHITECTURE.md)" % (n - CAP))
if n < CAP - 50: print("note: console.js is %d lines, well under the cap of %d; lower CAP in this test" % (n, CAP))

html = (CON / "index.html").read_text()
loaded = re.findall(r'<script src="([^"]+\.js)"></script>', html)
on_disk = sorted(p.name for p in CON.glob("*.js"))
check("every script in console/ is loaded by index.html", sorted(set(on_disk) - set(loaded)) == [], sorted(set(on_disk) - set(loaded)))
check("every script index.html loads exists", sorted(set(loaded) - set(on_disk)) == [], sorted(set(loaded) - set(on_disk)))
check("index.html has no inline script", not re.search(r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", html))
stations = [f for f in loaded if f not in SHARED and f != LEGACY]
order_ok = all(f in loaded for f in SHARED + [LEGACY]) and all(loaded.index(f) < loaded.index(LEGACY) for f in SHARED) and all(loaded.index(f) > loaded.index(LEGACY) for f in stations)
check("load order: shared files, then console.js, then the station files", order_ok, loaded)
check("filters.js loads after ui.js", loaded.index("filters.js") > loaded.index("ui.js"))

for f in stations:
    name = f[:-3]; src = (CON / f).read_text()
    tests = sorted(HERE.glob("run_%s*_browser_test.py" % name))
    check("%s has a browser test (run_%s*_browser_test.py) that loads the Console page" % (f, name),
          any("console" in t.read_text() and "index.html" in t.read_text() for t in tests), [t.name for t in tests])
    check("%s reaches the big file only through ConsoleKit" % f, "window.ConsoleKit" in src)
    glob = re.search(r"window\.(\w+Station)\s*=\s*\{", src)
    check("%s exposes window.<Name>Station" % f, bool(glob))
    if glob:
        body = src[glob.end():]
        check("%s has show and reset, and console.js calls show" % f, re.search(r"\bshow\s*:", body) is not None and re.search(r"\breset\s*:", body) is not None and (glob.group(1) + ".show") in big, glob.group(1))
        check("%s is reset when the Console locks" % f, (glob.group(1) + ".reset") in big, glob.group(1))

print("\n" + ("all passed" if not fails else "%d FAILED: %s" % (len(fails), "; ".join(fails))))
sys.exit(1 if fails else 0)

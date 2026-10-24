#!/usr/bin/env python3
"""Console architecture rules (console/ARCHITECTURE.md), checked without a browser.

  1. console.js may not grow past CAP. It only shrinks. Extract a station, then LOWER the cap to the new size (never raise it).
  2. Every station file has a browser test: enjoy_router/run_<name>*_browser_test.py that loads console/index.html.
  3. Every script in console/ is loaded by index.html, every script index.html loads exists, and the order is legal
     (shared files, then console.js, then station files).
  4. A station file reaches the big file only through ConsoleKit, and exposes window.<Name>Station with show and reset.
  5. Dependency direction (R-0): a shared file never mentions a station; a station never mentions another station's global.
     The shared files that load after console.js (names.js, dialogs.js) reach the core only through ConsoleKit too.
  6. Every ConsoleKit item has an owner line in the "Who owns what" section of console/ARCHITECTURE.md.

Run from enjoy_router/:  python3 run_console_architecture_test.py
CONSOLE_DIR (environment) points the test at another copy of console/ (used to prove the test can fail)."""
import os, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
CON = pathlib.Path(os.environ.get("CONSOLE_DIR") or (HERE.parent / "console"))
CAP = 5708          # lines in console.js after R-4 (requests.js left it). LOWER this after each extraction; never raise it.
SHARED = ["firebase-config.js", "console-config.js", "ui.js", "filters.js"]   # load before console.js
SHARED_AFTER = ["names.js", "dialogs.js"]   # shared data / dialogs: load AFTER console.js (they use the kit) and BEFORE the stations; not stations
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
shared_after = [f for f in loaded if f in SHARED_AFTER]
stations = [f for f in loaded if f not in SHARED and f != LEGACY and f not in SHARED_AFTER]
order_ok = all(f in loaded for f in SHARED + [LEGACY]) and all(loaded.index(f) < loaded.index(LEGACY) for f in SHARED) \
    and all(loaded.index(f) > loaded.index(LEGACY) for f in shared_after + stations) \
    and all(loaded.index(a) < loaded.index(s) for a in shared_after for s in stations)
check("load order: shared files, then console.js, then names/dialogs, then the station files", order_ok, loaded)
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

# 5. dependency direction
station_globals = {}
for f in stations:
    m = re.search(r"window\.(\w+Station)\s*=\s*\{", (CON / f).read_text())
    if m: station_globals[f] = m.group(1)
for f in SHARED + shared_after:
    src = (CON / f).read_text()
    check("%s (shared) never mentions a station" % f, not re.search(r"\b\w+Station\b", src), re.findall(r"\b\w+Station\b", src)[:3])
for f in shared_after:
    src = (CON / f).read_text()
    check("%s reaches the big file only through ConsoleKit" % f, "window.ConsoleKit" in src)
    check("%s exposes window.Console<Thing> and not a *Station" % f, re.search(r"window\.Console[A-Z]\w*\s*=\s*\{", src) is not None)
for f in stations:
    src = (CON / f).read_text()
    others = [g for o, g in station_globals.items() if o != f]
    bad = [g for g in others if re.search(r"\b%s\b" % g, src)]
    check("%s never mentions another station" % f, not bad, bad)

# 6. every kit item has an owner line in ARCHITECTURE.md ("Who owns what")
blk = re.search(r"window\.ConsoleKit\s*=\s*\{", big)
kit_items = []
if blk:
    depth, i, line_comment = 1, blk.end(), False
    seg = []
    while i < len(big) and depth > 0:
        c = big[i]
        if line_comment:
            if c == "\n": line_comment = False
        elif big.startswith("//", i): line_comment = True
        else:
            if c in "{([": depth += 1
            elif c in "})]": depth -= 1
            if depth == 1: seg.append(c)
        i += 1
    kit_items = re.findall(r"(?:^|[,{]\s*)(\w+)\s*:", "".join(seg))
arch = (CON / "ARCHITECTURE.md").read_text()
owns = arch.split("## Who owns what", 1)[1] if "## Who owns what" in arch else ""
check("ARCHITECTURE.md has a 'Who owns what' section", bool(owns))
missing = [k for k in kit_items if not re.search(r"`%s[`(\s,]" % k, owns)]
check("every ConsoleKit item (%d) has an owner line" % len(kit_items), kit_items != [] and not missing, missing)

print("\n" + ("all passed" if not fails else "%d FAILED: %s" % (len(fails), "; ".join(fails))))
sys.exit(1 if fails else 0)

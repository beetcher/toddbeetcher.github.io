#!/usr/bin/env python3
"""Mutation check for the launch screen (P-79): break each rule in console/console.js (and console.css) on purpose and run_launch_screen_browser_test.py must fail.
Restores the file afterwards. Run from enjoy_router/:  python3 mutate_launch_page.py"""
import os, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent; CON = HERE.parent / "console"; JS = CON / "console.js"; CSS = CON / "console.css"
M = [
 ("the launch screen never starts", 'unlockSeq;\n    launchStart();', 'unlockSeq;\n    '),
 ("the sign-in buttons stay while it shows", '$("googleBox").hidden = true; $("keyBox").hidden = true; $("swapLink").hidden = true; $("lockMsg").textContent = "";\n    $("launching")', '$("lockMsg").textContent = "";\n    $("launching")'),
 ("it does not open on the first line", '$("launching").hidden = false; launchStage(1);', '$("launching").hidden = false; launchStage(2);'),
 ("the second stage never shows", 'setTimeout(function () { launchStage(2); }, 700)', 'setTimeout(function () { }, 700)'),
 ("the third stage never shows", 'ME = r.body.data; launchStage(3);', 'ME = r.body.data;'),
 ("stages can go backwards", 'if (!launching || n <= launchN) return;', 'if (!launching) return;'),
 ("the slow line never shows", 'launchN = 9; $("launchLine").textContent = LAUNCH_SLOW;', 'launchN = 9;'),
 ("the slow line comes too early", 'launchN = 9; $("launchLine").textContent = LAUNCH_SLOW; } }, 8000)', 'launchN = 9; $("launchLine").textContent = LAUNCH_SLOW; } }, 800)'),
 ("no Liftoff", '$("launchLine").textContent = "Liftoff!";', ''),
 ("the launch screen stays after success", 'setTimeout(function () { launchStop(); ok(); }, 350);', 'setTimeout(function () { ok(); }, 350);'),
 ("a failure leaves the launch screen up", 'key = ""; launchStop();\n        $("lockMsg").textContent = "Launch aborted: "', 'key = "";\n        $("lockMsg").textContent = "Launch aborted: "'),
 ("a failure has no Launch aborted prefix", '"Launch aborted: " + problem(res.status)', 'problem(res.status)'),
 ("a lock leaves the launch screen up", 'function lock(message) {\n    launchStop();', 'function lock(message) {'),
 ("the form does not come back after a stop", '$("googleBox").hidden = launchSaved.g; $("keyBox").hidden = launchSaved.k; $("swapLink").hidden = launchSaved.s;', ''),
 ("the tab icon never spins", 'launchStage(1); spinIcons(true);', 'launchStage(1);'),
 ("the tab icon is not put back", 'if (iconKeep) { iconKeep.forEach(function (k) { k.el.setAttribute("href", k.href); }); iconKeep = null; }', 'if (iconKeep) { iconKeep = null; }'),
 ("the tab icon spins under reduced motion", 'try { if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return; } catch (e) {}', ''),
 ("the tile does not pulse under reduced motion", '@media (prefers-reduced-motion: reduce) { #launching img { animation: launchPulse 2.4s ease-in-out infinite; } }', ''),
 ("the tile does not spin", '#launching img { display: block; margin: 0 auto 18px; animation: launchSpin 2.8s linear infinite; }', '#launching img { display: block; margin: 0 auto 18px; }'),
 ("a second Google press is not ignored", 'if (!auth || launching) return;', 'if (!auth) return;'),
 ("the key form ignores a second press no more", 'e.preventDefault(); if (launching) return;', 'e.preventDefault();'),
]
survivors = []; env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for label, a, b in M:
    PAGE = CSS if a.startswith(("@media", "#launching")) else JS   # the style rules live in console.css, everything else in console.js
    src = PAGE.read_text(encoding="utf-8")
    if src.count(a) != 1: print("CANNOT APPLY:", label, src.count(a)); survivors.append(label + " (pattern)"); continue
    PAGE.write_text(src.replace(a, b), encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-B", str(HERE / "run_launch_screen_browser_test.py")], capture_output=True, text=True, timeout=400, cwd=HERE, env=env)
        caught = r.returncode != 0
    finally:
        PAGE.write_text(src, encoding="utf-8")
    print(("caught   " if caught else "SURVIVED ") + label, flush=True)
    if not caught: survivors.append(label)
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)

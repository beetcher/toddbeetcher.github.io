#!/usr/bin/env python3
"""Mutation check for the Console inactivity sign-out: break each rule in console/console.js and console/access.js on purpose and
run_console_timeout_browser_test.py must fail. Restores both files afterwards. Run from enjoy_router/:  python3 mutate_console_timeout.py"""
import subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
IDX = HERE.parent / "console" / "console.js"; ACC = HERE.parent / "console" / "access.js"
GOOD = {IDX: IDX.read_text(encoding="utf-8"), ACC: ACC.read_text(encoding="utf-8")}
M = [
 (IDX, "default is not 10", 'IDLE_DEFAULT = 10,', 'IDLE_DEFAULT = 99,'),
 (IDX, "no warning in the last minute", 'IDLE_WARN_MS = 60000', 'IDLE_WARN_MS = 0'),
 (IDX, "never signs out", 'if (left <= 0) { idleWarn(0); lock(', 'if (left <= -1e12) { idleWarn(0); lock('),
 (IDX, "activity does not reset the clock", 'if (!key) return; idleTouch(); if (idleShown) idleWarn(0); }', 'if (!key) return; if (idleShown) idleWarn(0); }'),
 (IDX, "a Discovery run does not hold the sign-out", 'if (idleBusy()) idleTouch();', ''),
 (IDX, "unreadable setting opens the door to 480", 'if (!recs) return;', 'if (!recs) { idleMinutes = 480; return; }'),
 (IDX, "no record means 480, not 10", 'recs.length ? recs[0].session_timeout_minutes : IDLE_DEFAULT); idleSet', 'recs.length ? recs[0].session_timeout_minutes : 480); idleSet'),
 (IDX, "the saved number is not used", 'idleMinutes = idleClamp(recs.length ? recs[0].session_timeout_minutes : IDLE_DEFAULT);', 'idleMinutes = IDLE_DEFAULT;'),
 (IDX, "the last known number is ignored at start", 'idleMinutes = idleClamp(idleGet(IDLE_MIN) || IDLE_DEFAULT);', 'idleMinutes = IDLE_DEFAULT;'),
 (IDX, "the number is not clamped", 'return n >= 1 && n <= 480 ? n : IDLE_DEFAULT;', 'return n >= 1 ? n : IDLE_DEFAULT;'),
 (IDX, "an idle remembered key still signs in", 'if (saved.key && idleStaleAtLoad) {', 'if (false) {'),
 (IDX, "an idle remembered key is left in the browser", "idleStaleAtLoad = false; setKey('', false); idleDrop(IDLE_AT);", "idleStaleAtLoad = false; idleDrop(IDLE_AT);"),
 (IDX, "an idle restored Google session carries on", 'if (idleStaleAtLoad) { idleStaleAtLoad = false; idleDrop(IDLE_AT); try { auth.signOut();', 'if (false) { idleStaleAtLoad = false; idleDrop(IDLE_AT); try { auth.signOut();'),
 (IDX, "a deliberate Google sign-in is dropped as stale", '$("lockMsg").textContent = ""; idleStaleAtLoad = false;', '$("lockMsg").textContent = "";'),
 (IDX, "Lock leaves the saved clock behind", 'function idleEnd() { idleWarn(0); idleDrop(IDLE_AT); }', 'function idleEnd() { idleWarn(0); }'),
 (IDX, "signing in does not start the clock", 'idleStaleAtLoad = false; idleStart();', 'idleStaleAtLoad = false;'),
 (IDX, "'1 minutes' plural", 'idleWarn(0); lock("You were signed out after " + idleMinutes + " minute" + (idleMinutes === 1 ? "" : "s")', 'idleWarn(0); lock("You were signed out after " + idleMinutes + " minute" + "s"'),
 (ACC, "the box shows to a delegate", 'if (!isDelegate()) wrap.appendChild(signInBox());', 'wrap.appendChild(signInBox());'),
 (ACC, "0 is accepted", '+t < 1 || +t > 480', '+t < 0 || +t > 480'),
 (ACC, "481 is accepted", '+t < 1 || +t > 480', '+t < 1 || +t > 999'),
 (ACC, "a fraction is accepted", '/^\\d{1,3}$/.test(t)', '/^[\\d.]{1,3}$/.test(t)'),
 (ACC, "this window is not told the new number", 'K.sessionMinutes(n);', ''),
]
# not listed: "Stay signed in does not reset the clock" is an equivalent change, because pressing the button is already a pointer press that resets the clock.
survivors = []
try:
    for f, label, a, b in M:
        g = GOOD[f]
        if g.count(a) != 1: print("CANNOT APPLY:", label, g.count(a)); survivors.append(label + " (pattern)"); continue
        f.write_text(g.replace(a, b), encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "run_console_timeout_browser_test.py")], capture_output=True, text=True, timeout=400)
        caught = r.returncode != 0
        print(("caught  " if caught else "SURVIVED ") + label, flush=True)
        if not caught: survivors.append(label)
        f.write_text(g, encoding="utf-8")
finally:
    for f, g in GOOD.items(): f.write_text(g, encoding="utf-8")
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)

#!/usr/bin/env python3
"""Mutation check for the Inspector's Console page (P-78): break each piece of view-only behaviour in the page on purpose and
run_inspector_browser_test.py must fail. Restores every file afterwards. Run from enjoy_router/:  python3 mutate_inspector_page.py"""
import os, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent; C = HERE.parent / "console"
IDX = C / "index.html"; ACC = C / "access.js"
M = [
 ("an inspector is not allowed every station by can()", IDX, "ME.is_super_admin === true || ME.inspector === true || (ME.capabilities", "ME.is_super_admin === true || (ME.capabilities"),
 ("an inspector cannot open the admin stations", IDX, "!!(ME && (ME.is_super_admin || ME.inspector))", "!!(ME && ME.is_super_admin)"),
 ("an inspector gets no Change history button", IDX, "(ME.is_super_admin !== true && ME.inspector !== true)) return null;", "(ME.is_super_admin !== true)) return null;"),
 ("the page lets a write leave for the server", IDX, "if (ME && ME.inspector && !VIEW_READS[op]) {", "if (false) {"),
 ("a read is treated as a write", IDX, "var VIEW_READS = { list: 1, get: 1,", "var VIEW_READS = { get: 1,"),
 ("the View only band never shows", IDX, '$("viewOnly").hidden = !on;', '$("viewOnly").hidden = true;'),
 ("buttons that appear later are not switched off", IDX, "viewObs.observe(document.body, { childList: true, subtree: true });", ""),
 ("Edit is not switched off", IDX, "/^(edit|save|", "/^(save|"),
 ("Delete is not switched off", IDX, "|save|delete|remove|", "|save|remove|"),
 ("Put in a class is not switched off", IDX, "|invite|put in|create|", "|invite|create|"),
 ("status switches stay live", IDX, 'b.classList.contains("stoggle") || VIEW_WRITE.test(t)', 'VIEW_WRITE.test(t)'),
 ("Lock leaves the page in view-only mode", IDX, 'ME = null; $("who").hidden = true; viewOnlyMode(false); idleEnd();', 'ME = null; $("who").hidden = true; idleEnd();'),
 ("the page shows a super admin the band", IDX, 'viewOnlyMode(!!(ME && ME.inspector));', 'viewOnlyMode(!!ME);'),
 ("Access says an inspector sees nothing", ACC, 'if (viewOnlyRole(role)) return "Inspector: sees everything, changes nothing";', ''),
 ("Access shows an inspector the limited view", ACC, "m.is_super_admin !== true && m.inspector !== true && m.method", "m.is_super_admin !== true && m.method"),
]
survivors = []
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for label, f, a, b in M:
    src = f.read_text(encoding="utf-8")
    if src.count(a) != 1: print("CANNOT APPLY:", label, src.count(a)); survivors.append(label + " (pattern)"); continue
    f.write_text(src.replace(a, b), encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-B", str(HERE / "run_inspector_browser_test.py")], capture_output=True, text=True, timeout=300, cwd=HERE, env=env)
        caught = r.returncode != 0
    finally:
        f.write_text(src, encoding="utf-8")
    print(("caught   " if caught else "SURVIVED ") + label, flush=True)
    if not caught: survivors.append(label)
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)

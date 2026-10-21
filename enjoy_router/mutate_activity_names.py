#!/usr/bin/env python3
"""Mutation check for the Activity name lookup: break each rule in console/activity.js on purpose and the names browser test must fail.
Restores the file afterwards. Run from enjoy_router/:  python3 mutate_activity_names.py"""
import subprocess, sys, pathlib, shutil
HERE = pathlib.Path(__file__).resolve().parent
F = HERE.parent / "console" / "activity.js"; GOOD = F.read_text(encoding="utf-8"); BAK = F.with_suffix(".js.bak")
M = [
 ("no lookup: person shows the id", 'if (kind === "user") return S.names[rest] || rest;', 'if (kind === "user") return rest;'),
 ("fallback is a vague label, not the id", 'if (kind === "user") return S.names[rest] || rest;', 'if (kind === "user") return S.names[rest] || "A signed-in person";'),
 ("fallback is a role", 'if (kind === "user") return S.names[rest] || rest;', 'if (kind === "user") return S.names[rest] || "super admin";'),
 ("actor fields inside entries not translated", 'if (ACTOR_FIELDS[c.field]) { var a = jsonStr(text); if (a) return actorName(a); }', 'if (false) { var a = jsonStr(text); if (a) return actorName(a); }'),
 ("hover title removed", 'by.title = String(e.created_by || "");', ''),
 ("hover title is the name", 'by.title = String(e.created_by || "");', 'by.title = actorName(e.created_by);'),
 ("lookup repeated every load", 'need.forEach(function (id) { S.tried[id] = 1; });', ''),
 ("a person with no name stores 'undefined'", 'if (p && p.id && p.display_name && String(p.display_name).trim())', 'if (p && p.id)'),
 ("filter by name not translated", 'f[S.mode] = S.mode === "created_by" ? actorId(S.value) : S.value;', 'f[S.mode] = S.value;'),
 ("'Admin key' not accepted in the filter", '"admin key": "user:admin", ', ''),
 ("names not fetched before a typed name", '!S.allNames) ? (S.allNames = true, fetchNames())', '!S.allNames) ? (S.allNames = true, Promise.resolve(false))'),
 ("name match is case sensitive", 'return String(S.names[id]).toLowerCase() === low;', 'return String(S.names[id]) === t;'),
 ("two people with one name still picks one", 'return hits.length === 1 ? "user:" + hits[0] : t;', 'return hits.length >= 1 ? "user:" + hits[0] : t;'),
 ("a failed lookup throws", '}, function () { return false; });', '});'),
 ("two people with one name: no message", 'S.msg = "More than one person has that name. Type the user id instead.";', ''),
 ("search no longer sees the name", 'actorName(e.created_by), e.created_by, e.record_id];', 'e.created_by, e.record_id];'),
 ("names not cleared on lock", 'pending: null, openIds: {}, names: {}, tried: {}, allNames: false }; var v = $("activityView")', 'pending: null, openIds: {}, names: S.names, tried: S.tried, allNames: false }; var v = $("activityView")'),
 ("no redraw after the names arrive", 'if (got && my === S.seq) draw();', ''),
]
survivors = []
try:
    for label, a, b in M:
        if GOOD.count(a) != 1: print("CANNOT APPLY:", label, GOOD.count(a)); survivors.append(label + " (pattern)"); continue
        F.write_text(GOOD.replace(a, b), encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "run_activity_names_browser_test.py")], capture_output=True, text=True, timeout=300)
        caught = r.returncode != 0
        print(("caught  " if caught else "SURVIVED ") + label)
        if not caught: survivors.append(label)
finally:
    F.write_text(GOOD, encoding="utf-8")
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)

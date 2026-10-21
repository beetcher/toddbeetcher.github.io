"""Mutation check for the activity log (P-46): break each rule on purpose and prove run_activity_tests.py notices.

    python3 mutate_activity.py

Works on a throw-away copy of the repo, so nothing real is touched. Every mutation must make the tests FAIL; a mutation the tests survive
means a rule in ACTIVITY_EVENT_GUIDE.md section 3 is not really tested. Exit 0 only when every mutation was caught.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
L, S, E, P = "enjoy_router/crud/activity_log.py", "enjoy_router/crud/activity_store.py", "enjoy_router/crud/activity_events_crud.py", "enjoy_router/access/policy.py"

# (rule, file, exact text, replacement)
MUTATIONS = [
    ("1 entry not written with the change (separate step)", S, "            self.inner.create(AL.COLLECTION, entry[\"id\"], entry, tx=t)\n        self._together(write, tx)\n\n    def update",
     "            pass\n        self._together(write, tx)\n        self.inner.create(AL.COLLECTION, entry[\"id\"], entry)\n\n    def update"),
    ("1 update entry not written", S, "            self.inner.update(base, id, set_fields, delete_fields, expected_updated_at, tx=t)\n            self.inner.create(AL.COLLECTION, entry[\"id\"], entry, tx=t)",
     "            self.inner.update(base, id, set_fields, delete_fields, expected_updated_at, tx=t)"),
    ("1 create entry not written", S, "            self.inner.create(base, id, doc, tx=t)\n            self.inner.create(AL.COLLECTION, entry[\"id\"], entry, tx=t)",
     "            self.inner.create(base, id, doc, tx=t)"),
    ("1 endpoint create allowed", E, "create = update = soft_delete = _refused", "update = soft_delete = _refused\ncreate = lambda *a, **k: success({})"),
    ("1 endpoint update allowed", E, "create = update = soft_delete = _refused", "create = soft_delete = _refused\nupdate = lambda *a, **k: success({})"),
    ("1 endpoint soft_delete allowed", E, "create = update = soft_delete = _refused", "create = update = _refused\nsoft_delete = lambda *a, **k: success({})"),
    ("1 policy: read open to everyone", P, "\"activity_events\": (SUPER_ONLY,),                     # the activity log: only a super admin reads it", "\"activity_events\": (),                     # the activity log"),
    ("1 policy: write open to everyone", P, "\"activity_events\": (SUPER_ONLY,),                     # written by the ActivityStore only, never through a door", "\"activity_events\": (),                     # x"),
    ("2 pending map ignored (chained writes lose entries)", S, "before = pend[(base, id)] if (base, id) in pend else self.inner.get(base, id)", "before = self.inner.get(base, id)"),
    ("2 after-state not tracked", S, "            pend[(base, id)] = AL.apply_changes(before, set_fields, delete_fields)\n", "            pass\n"),
    ("2 create not tracked", S, "            self._pending(tx)[(base, id)] = copy.deepcopy(doc)\n", "            pass\n"),
    ("3 x_pii fields copied", L, "return collection in WITHHOLD_COLLECTIONS or field in personal or field in WITHHOLD_FIELDS.get(collection, ())",
     "return collection in WITHHOLD_COLLECTIONS or field in WITHHOLD_FIELDS.get(collection, ())"),
    ("3 restricted-details values copied", L, "return collection in WITHHOLD_COLLECTIONS or", "return False or"),
    ("3 by-name withholding dropped", L, "or field in WITHHOLD_FIELDS.get(collection, ())", ""),
    ("3 display_name withholding dropped", L, "frozenset({\"display_name\", \"birth_country\"})", "frozenset({\"birth_country\"})"),
    ("3 notes withholding dropped", L, "frozenset({\"notes\", \"organization_name\"})", "frozenset({\"organization_name\"})"),
    ("3 google_uid withholding dropped", L, "{\"google_uid\"}", "{\"x_none\"}"),
    ("3 withheld label (name) used as record_label", L, "not is_withheld(collection, personal, f)", "True"),
    ("3 withheld flag missing", L, "        c[\"values_withheld\"] = True\n", "        pass\n"),
    ("4 stamps listed as changes", L, "for k in sorted(touched - STAMPS - quiet):", "for k in sorted(touched - quiet):"),
    ("4 stamp-only write logs", L, "    if not changed:\n        return None\n", "    if not changed and not touched:\n        return None\n"),
    ("4 unchanged value logged as change", L, "if (b is _MISSING) != (a is _MISSING) or (b is not _MISSING and canon(b) != canon(a)):", "if True:"),
    ("4 quiet fields not quiet", L, "for k in sorted(touched - STAMPS - quiet):", "for k in sorted(touched - STAMPS):"),
    ("4 timeout writes logged", S, "if info is None or timeout is not None:", "if info is None:"),
    ("5 activity_events itself logged", L, "frozenset({\"activity_events\", \"communication_logs\", \"journal_events\", \"discovery_runs\"})", "frozenset({\"communication_logs\", \"journal_events\", \"discovery_runs\"})"),
    ("5 communication_logs logged", L, "\"activity_events\", \"communication_logs\",", "\"activity_events\","),
    ("5 journal_events logged", L, "\"journal_events\", \"discovery_runs\"", "\"discovery_runs\""),
    ("5 discovery_runs logged", L, "\"journal_events\", \"discovery_runs\"", "\"journal_events\""),
    ("5 unknown collections logged / crash", L, "return None if hit is None else (collection, hit[0], hit[1])", "return (collection, collection, frozenset())"),
    ("5 nothing logged", L, "    if collection in EXCLUDED_COLLECTIONS:\n        return None", "    if True:\n        return None"),
    ("7 missing actor not defaulted", L, "FALLBACK_ACTOR = \"system:unattributed\"", "FALLBACK_ACTOR = \"system:other\""),
    ("7 invalid actor accepted", L, "if isinstance(c, str) and ACTOR_PATTERN.match(c):", "if isinstance(c, str) and c:"),
    ("action: deleted detected as edited", L, "        action = \"deleted\"", "        action = \"edited\""),
    ("action: restored detected as edited", L, "        action = \"restored\"", "        action = \"edited\""),
    ("deleter not used as actor", L, "set_fields.get(\"deleted_by\") if action == \"deleted\" else None, ", ""),
    ("related ids: record's own id missing", L, "    out = [record_id]\n", "    out = []\n"),
    ("related ids: no cap", L, "return out[:MAX_RELATED]", "return out"),
    ("related ids: list fields ignored", L, "for x in (v if isinstance(v, list) else [v]):", "for x in [v]:"),
    ("related ids: payer/payee ignored", L, "RELATED_PATHS = ((\"payer\", \"party_id\"), (\"payee\", \"party_id\"))", "RELATED_PATHS = ()"),
    ("related ids: after-state ignored", L, "related_ids(record_id, before, after)", "related_ids(record_id, before)"),
    ("related ids: before-state ignored", L, "related_ids(record_id, before, after)", "related_ids(record_id, after)"),
    ("label: not cut", L, "return v.strip()[:MAX_LABEL]", "return v.strip()"),
    ("values: not cut", L, "return (s[:MAX_VALUE_CHARS], True) if len(s) > MAX_VALUE_CHARS else (s, False)", "return (s, False)"),
    ("values: cut without truncated flag", L, "    if cut:\n        c[\"truncated\"] = True\n", "    pass\n"),
    ("changes: not capped", L, "return changes[:MAX_CHANGES], max(0, len(changes) - MAX_CHANGES)", "return changes, 0"),
    ("changes: omitted count not kept", L, "    if omitted:\n        e[\"fields_omitted\"] = omitted\n", "    pass\n"),
    ("sequence not increasing", S, "            if ms <= self._last_ms:\n                ms = self._last_ms + 1\n", "            pass\n"),
    ("list: newest-first reversed", E, "descending = order.startswith(\"-\")", "descending = not order.startswith(\"-\")"),
    ("list: limit not capped", E, "n = max(1, min(limit, MAX_LIMIT))", "n = max(1, limit)"),
    ("list: two filters allowed", E, "    if len(filters) > 1:\n", "    if len(filters) > 99:\n"),
    ("list: unknown filter allowed", E, "problems += [{\"field\": k, \"issue\": \"not_supported\"}] if k not in _LIST_FILTERS else _filter_problem(k, v)", "problems += _filter_problem(k, v) if k in _LIST_FILTERS else []"),
    ("list: related_ids filter is equality", E, "\"array_contains\" if k == \"related_ids\" else \"==\"", "\"==\""),
    ("created: stamp ignored", L, "created_at = doc.get(\"created_at\") if _stamp_ok(doc.get(\"created_at\")) else", "created_at = "),
    ("get: bad id accepted", E, "if not (isinstance(id, str) and UUID_PATTERN.match(id)):", "if False:"),
    ("store: reads not passed through", S, "        return self.inner.get(base, id)\n\n    def query", "        return None\n\n    def query"),
]


def run(work):
    r = subprocess.run([sys.executable, "enjoy_router/run_activity_tests.py"], cwd=work, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr)[-400:]


def main():
    only = sys.argv[1:]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mut_"))
    work = tmp / "repo"
    ignore = shutil.ignore_patterns("venv", "__pycache__", "node_modules", ".git", "*.tgz", "*.png", "firestore-debug.log")
    shutil.copytree(ROOT / "enjoy_router", work / "enjoy_router", ignore=ignore)
    shutil.copytree(ROOT / "schemas", work / "schemas", ignore=ignore)
    code, out = run(work)
    if code != 0:
        print("UNMUTATED RUN FAILS - fix the tests first:\n" + out)
        return 2
    survivors, bad = [], []
    for rule, rel, old, new in MUTATIONS:
        if only and not any(o in rule for o in only):
            continue
        p = work / rel
        src = p.read_text()
        if src.count(old) != 1:
            bad.append((rule, f"pattern found {src.count(old)} times in {rel}"))
            continue
        p.write_text(src.replace(old, new))
        try:
            code, out = run(work)
        except subprocess.TimeoutExpired:
            code, out = 1, "timeout"
        finally:
            p.write_text(src)
        print(("caught   " if code != 0 else "SURVIVED ") + rule, flush=True)
        if code == 0:
            survivors.append(rule)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(MUTATIONS) - len(survivors) - len(bad)} caught, {len(survivors)} survived, {len(bad)} could not be applied")
    for r, why in bad:
        print("  CANNOT APPLY:", r, "-", why)
    for r in survivors:
        print("  SURVIVED:", r)
    return 1 if survivors or bad else 0


sys.exit(main())

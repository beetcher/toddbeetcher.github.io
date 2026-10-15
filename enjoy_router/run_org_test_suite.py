#!/usr/bin/env python3
"""Load or remove the organization test suite on the LIVE system (the admin door, the real collections).
Run from enjoy_router/:
    python3 run_org_test_suite.py load       puts the test organizations, places, venues and links in
    python3 run_org_test_suite.py cleanup    takes every one of them out again (soft delete)
    python3 run_org_test_suite.py status     says how many test records are there
Every record carries the note "LAUNCH test data". The load refuses to run twice. The key is read from
.env.launch-ai-workshop and never printed. The list of created ids is saved in .env.org_test_suite_ids.json (the .env name keeps
it out of git); cleanup uses it, and finds the records by their marker if it is gone."""
import json, pathlib, sys, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bulk_load, org_test_suite_data as D

BASE = "https://us-central1-launch-ai-workshop.cloudfunctions.net/"
MANIFEST = HERE / ".env.org_test_suite_ids.json"


def read_key():
    env = HERE / ".env.launch-ai-workshop"
    key = next((l.split("=", 1)[1].strip().strip('"\'') for l in env.read_text().splitlines() if l.startswith("ICDT_ADMIN_KEY=")), "") if env.exists() else ""
    if len(key) < 32:
        sys.exit("no admin key found in .env.launch-ai-workshop")
    return key


def make_call(key):
    def call(coll, op, **args):
        body = json.dumps({"collection": coll, "op": op, "args": args}).encode()
        for attempt in range(3):
            req = urllib.request.Request(BASE + "enjoy_admin", data=body, method="POST",
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    return r.status, json.loads(r.read() or b"{}")
            except urllib.error.HTTPError as e:
                try:
                    out = json.loads(e.read() or b"{}")
                except ValueError:
                    out = {}
                if e.code in (429, 503) and attempt < 2:      # not executed: safe to try again
                    time.sleep(2 + attempt * 3)
                    continue
                return e.code, out
            except Exception as e:                            # a timeout may have been executed: never repeat a write
                return 0, {"error": {"code": type(e).__name__}}
    return call


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode not in ("load", "cleanup", "status"):
        sys.exit(__doc__)
    call = make_call(read_key())
    if mode == "status":
        found = bulk_load.find_existing(call, D.MARKER)
        print(f"{len(found)} test organizations and venues are in the system." + ("" if found else " Nothing to clean up."))
        return 0
    if mode == "load":
        if MANIFEST.exists():
            sys.exit("A saved load already exists (" + MANIFEST.name + "). Run cleanup first.")
        if bulk_load.find_existing(call, D.MARKER):
            sys.exit("Test records are already in the system. Run cleanup first.")
        ids = bulk_load.new_manifest()
        try:
            res = bulk_load.load(D.build(), call, ids=ids)
        finally:
            MANIFEST.write_text(json.dumps(ids))
        print("\nDone.", json.dumps(res["counts"]))
        for n in res["notes"]:
            print("  note:", n)
        for e in res["errors"]:
            print("  REFUSED:", e)
        print("Saved the ids to", MANIFEST.name)
        return 1 if res["errors"] else 0
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else bulk_load.scan_manifest(call, D.MARKER)
    out = bulk_load.cleanup(call, manifest)
    for e in out["errors"]:
        print("  could not remove:", e)
    if not out["errors"] and MANIFEST.exists():
        MANIFEST.unlink()
    print(f"\nRemoved {out['deleted']} records.")
    return 1 if out["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

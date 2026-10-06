#!/usr/bin/env python3
"""Run the registration test records against a RUNNING endpoint over HTTP.

    python3 enjoy_router/run_http_tests.py --url http://127.0.0.1:5101/demo-icdt/us-central1/enjoy_registration_request

With the Firebase emulator, also set FIRESTORE_EMULATOR_HOST (for example 127.0.0.1:8180) and pass
--project demo-icdt. The script then clears the emulator's collections, seeds the test classes, runs
every test, and reads the stored documents back to check them. Without FIRESTORE_EMULATOR_HOST it
checks the replies only (stored-document expectations are skipped).

It refuses to touch Firestore unless FIRESTORE_EMULATOR_HOST is set, so it can never write to a real project.
The endpoint must be using the clock in setup.now: start the emulator with ICDT_FIXED_NOW=2026-10-06T17:00:00Z (see README).
Needs: pip install jsonschema (and firebase-admin, for the Firestore view).
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from core import Schemas  # noqa: E402
from run_tests import DEFAULT_RECORDS, run  # noqa: E402


class HttpEndpoint:
    last_outcome = None
    counter = 0

    def __init__(self, url, setup, schemas, project, origin):
        self.url, self.origin = url, origin
        self.db = None
        if os.environ.get("FIRESTORE_EMULATOR_HOST"):
            from google.cloud import firestore
            self.db = firestore.Client(project=project)
            self.requests_name = schemas.collection
            self.classes_name = schemas.class_collection
            self._reset(setup["scheduled_classes"])

    def _reset(self, classes):
        for name in (self.requests_name, "idempotency_keys", self.classes_name):
            for snap in self.db.collection(name).stream():
                snap.reference.delete()
        for c in classes:
            self.db.collection(self.classes_name).document(c["id"]).set(c)

    def send(self, body):
        # A different visitor address per test, so the rate limit (5 per 10 minutes) does not interfere.
        self.counter += 1
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Origin": self.origin,
                                              "X-Forwarded-For": f"203.0.113.{self.counter}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, self._json(r.status, r.read())
        except urllib.error.HTTPError as e:
            return e.code, self._json(e.code, e.read())
        except urllib.error.URLError as e:
            sys.exit(f"cannot reach {self.url}: {e.reason}\nIs the emulator running, and is the URL right?")

    @staticmethod
    def _json(status, raw):
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            # Not JSON: the emulator or the function itself answered. Show enough to diagnose.
            sys.exit(f"HTTP {status} with a body that is not JSON. First 300 characters:\n{raw[:300].decode('utf-8', 'replace')}\n"
                     "Check the emulator's terminal for errors and confirm the URL.")

    def docs(self):
        if self.db is None:
            return None
        snaps = sorted(self.db.collection(self.requests_name).stream(), key=lambda s: s.create_time)
        return [s.to_dict() for s in snaps]


def check_cors(url, origin):
    """A browser preflight from the site must be allowed; one from a stranger must not."""
    fails = []
    for o, want in ((origin, True), ("https://evil.example", False)):
        req = urllib.request.Request(url, method="OPTIONS", headers={
            "Origin": o, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                allowed = r.headers.get("Access-Control-Allow-Origin") == o
        except urllib.error.HTTPError as e:
            allowed = e.headers.get("Access-Control-Allow-Origin") == o
        print(f"{'ok  ' if allowed == want else 'FAIL'} CORS preflight from {o} is {'allowed' if want else 'refused'}")
        if allowed != want:
            fails.append(f"CORS preflight from {o}: allowed={allowed}, expected {want}")
    return fails


def check_rate_limit(url, origin):
    """Six requests from one visitor address: the sixth must be refused with 429 rate_limited."""
    codes = []
    for _ in range(6):
        req = urllib.request.Request(url, data=b"{}", method="POST", headers={
            "Content-Type": "application/json", "Origin": origin, "X-Forwarded-For": "198.51.100.77"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                codes.append(r.status)
        except urllib.error.HTTPError as e:
            codes.append(e.code)
    ok = codes[:5] == [400] * 5 and codes[5] == 429
    print(f"{'ok  ' if ok else 'FAIL'} rate limit: six requests from one address give {codes}")
    return [] if ok else [f"rate limit: expected five 400s then a 429, got {codes}"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--project", default="demo-icdt")
    ap.add_argument("--origin", default="https://beetcher.com")
    ap.add_argument("--records", default=str(DEFAULT_RECORDS))
    a = ap.parse_args()
    schemas = Schemas.load()
    setup = json.loads(pathlib.Path(a.records).read_text())["setup"]
    ep = HttpEndpoint(a.url, setup, schemas, a.project, a.origin)
    if ep.db is None:
        print("note: FIRESTORE_EMULATOR_HOST is not set, so stored documents are not checked (replies only)\n")
    fails = run(a.records, ep, schemas)
    fails += check_cors(a.url, a.origin)
    fails += check_rate_limit(a.url, a.origin)
    if fails:
        print(f"\nFAILED: {len(fails)} problem(s)")
        return 1
    print("\nOK: the running endpoint passes every test record")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run schemas/examples/registration_request.test_records.json against the endpoint.

    python3 enjoy_router/run_tests.py                 # the core, in memory (default)
    python3 enjoy_router/run_tests.py --handler       # core plus the HTTP handler, in memory
    python3 enjoy_router/run_http_tests.py --url ...  # a running endpoint (see that file)

Every mode uses the same runner (run()), so the same expectations apply everywhere. Each
test runs in file order against one endpoint seeded from setup.scheduled_classes, with the
clock fixed at setup.now. A test passes when every expectation it states is met: ok,
error_code, field_errors (exact set), stored, snapshot, stored_fields, no_previous_id,
previous_id_of, replay_of, discarded_as_spam. Replies must carry nothing but the
confirmation number and type. Where the stored documents can be seen, each must also pass
the schema and carry every server field.

An endpoint adapter has: send(body) -> (http_status, envelope), docs() -> list of stored
requests or None when they cannot be seen, and optional last_outcome.
Needs: pip install jsonschema
"""
import json
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from core import HTTP_STATUS, Schemas, handle_registration_request  # noqa: E402
from memory_store import MemoryStore  # noqa: E402

DEFAULT_RECORDS = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "examples" / "registration_request.test_records.json"


def build_body(case, by_name, depth=0):
    if depth > 10:
        raise RuntimeError("request_from loop")
    if "request_from" in case:
        body = dict(build_body(by_name[case["request_from"]], by_name, depth + 1))
        body.update(case.get("override", {}))
        for k in case.get("remove", []):
            body.pop(k, None)
        return body
    return dict(case["request"])


class CoreEndpoint:
    """The core, called directly, with an in-memory store."""
    def __init__(self, schemas, setup):
        self.schemas = schemas
        self.now = datetime.fromisoformat(setup["now"].replace("Z", "+00:00"))
        self.store = MemoryStore(setup["scheduled_classes"])
        self.last_outcome = None

    def send(self, body):
        r = handle_registration_request(body, self.store, self.schemas, now=self.now)
        self.last_outcome = r.outcome
        return r.status, r.envelope

    def docs(self):
        return self.store.requests


class HandlerEndpoint(CoreEndpoint):
    """The HTTP handler (method, size, JSON, rate limit) over the core, called directly."""
    def __init__(self, schemas, setup):
        super().__init__(schemas, setup)
        from handler import handle_http
        from ratelimit import RateLimiter
        self._handle = handle_http
        # Many tests share one visitor, so the limit is set high here; the limiter is tested in run_handler_checks.
        self.limiter = RateLimiter(rules=((600, 1000),))

    def send(self, body):
        r = self._handle("POST", json.dumps(body).encode(), "test-visitor", self.store, self.schemas, self.limiter, self.now)
        self.last_outcome = None
        return r.status, r.body


def run(records_path, endpoint, schemas, verbose=True):
    data = json.loads(pathlib.Path(records_path).read_text())
    cases = data["tests"]
    by_name = {c["name"]: c for c in cases}
    stored_by_test = {}   # test name -> stored doc
    answered = {}         # test name -> confirmation number replied
    fails = []

    for c in cases:
        exp = c["expect"]
        docs = endpoint.docs()
        before = len(docs) if docs is not None else None
        status, env = endpoint.send(build_body(c, by_name))
        problems = []

        if env.get("ok") != exp["ok"]:
            problems.append(f"ok is {env.get('ok')}, expected {exp['ok']}")
        if env.get("ok"):
            if status not in (200, 201):
                problems.append(f"HTTP status {status}, expected 200 or 201")
            if set(env.get("data", {})) != {"confirmation_number", "registration_type"}:
                problems.append("reply carries more than confirmation_number and registration_type")
        else:
            err = env.get("error", {})
            if err.get("code") != exp.get("error_code"):
                problems.append(f"error code {err.get('code')}, expected {exp.get('error_code')}")
            elif status != HTTP_STATUS.get(err.get("code")):
                problems.append(f"HTTP status {status}, expected {HTTP_STATUS.get(err.get('code'))}")
            if "field_errors" in exp:
                got = sorted(f["field"] for f in err.get("field_errors", []))
                if got != sorted(exp["field_errors"]):
                    problems.append(f"field_errors {got}, expected {sorted(exp['field_errors'])}")
        if exp.get("discarded_as_spam") and endpoint.last_outcome not in (None, "discarded_spam"):
            problems.append(f"outcome {endpoint.last_outcome}, expected discarded_spam")
        if "replay_of" in exp:
            if endpoint.last_outcome not in (None, "replay"):
                problems.append(f"outcome {endpoint.last_outcome}, expected replay")
            if env.get("data", {}).get("confirmation_number") != answered.get(exp["replay_of"]):
                problems.append("replay did not return the original confirmation number")

        if docs is not None:
            docs = endpoint.docs()
            created = len(docs) - before
            if created not in (0, 1):
                problems.append(f"{created} documents stored for one request")
            if "stored" in exp and (created == 1) != exp["stored"]:
                problems.append(f"stored {created == 1}, expected {exp['stored']}")
            doc = docs[-1] if created == 1 else None
            if doc is not None:
                stored_by_test[c["name"]] = doc
                bad = [e.message[:60] for e in schemas.validator.iter_errors(doc)]
                if bad:
                    problems.append(f"stored document fails the schema: {bad[0]}")
                for k in schemas.server_required:
                    if k not in doc:
                        problems.append(f"stored document lacks server field {k}")
                if "snapshot" in exp:
                    got = {k: doc.get(k) for k in schemas.snapshot_fields}
                    if got != exp["snapshot"]:
                        problems.append(f"snapshot {got}, expected {exp['snapshot']}")
                elif "scheduled_class_id" not in doc and any(k in doc for k in schemas.snapshot_fields):
                    problems.append("snapshot present without a class pick")
                for k, v in exp.get("stored_fields", {}).items():
                    if doc.get(k) != v:
                        problems.append(f"stored {k} is {doc.get(k)!r}, expected {v!r}")
                if exp.get("no_previous_id") and "previous_id" in doc:
                    problems.append("previous_id present, expected none")
                if "previous_id_of" in exp:
                    want = stored_by_test.get(exp["previous_id_of"], {}).get("id")
                    if doc.get("previous_id") != want:
                        problems.append("previous_id does not point at the earlier request")
                if doc.get("confirmation_number") != env.get("data", {}).get("confirmation_number"):
                    problems.append("stored confirmation number differs from the reply")
            elif "snapshot" in exp or "stored_fields" in exp:
                problems.append("expected a stored document")

        if env.get("ok"):
            answered[c["name"]] = env["data"]["confirmation_number"]

        if verbose:
            print(f"{'ok  ' if not problems else 'FAIL'} {c['name']}")
            for p in problems:
                print(f"       - {p}")
        fails += [f"{c['name']}: {p}" for p in problems]

    docs = endpoint.docs()
    if docs is not None:
        expected_stored = sum(1 for c in cases if c["expect"].get("stored"))
        if len(docs) != expected_stored:
            fails.append(f"end state: {len(docs)} documents stored, expected {expected_stored}")
        numbers = [d["confirmation_number"] for d in docs]
        if len(numbers) != len(set(numbers)):
            fails.append("end state: duplicate confirmation numbers")
    return fails


def run_extra_checks(schemas, verbose=True):
    """Things the 30 records do not cover: odd bodies, an empty honeypot, a simulated race, and the rate limiter."""
    from core import DuplicateIdempotencyKey
    from handler import handle_http
    from ratelimit import RateLimiter
    data = json.loads(DEFAULT_RECORDS.read_text())
    now = datetime.fromisoformat(data["setup"]["now"].replace("Z", "+00:00"))
    first = data["tests"][0]["request"]
    fails = []

    def check(label, ok):
        if verbose:
            print(f"{'ok  ' if ok else 'FAIL'} extra: {label}")
        if not ok:
            fails.append(f"extra: {label}")

    for label, body in (("null body", None), ("list body", []), ("string body", "x"), ("empty object", {})):
        r = handle_registration_request(body, MemoryStore([]), schemas, now=now)
        check(f"{label} is refused with validation_failed", r.error_code == "validation_failed")

    st = MemoryStore([])
    r = handle_registration_request({**first, "website": ""}, st, schemas, now=now)
    check("an empty honeypot field is ignored and the request is stored", r.outcome == "created" and "website" not in st.requests[0])

    # Two copies of one submission at the same moment: the second finds nothing at first, then loses the race.
    class RacyStore(MemoryStore):
        def find_by_idempotency_key(self, key):
            return None if self._hide else super().find_by_idempotency_key(key)
    rs = RacyStore([])
    rs._hide = False
    handle_registration_request(first, rs, schemas, now=now)
    rs._hide = True
    orig_put = rs.put_request

    def put_then_reveal(doc):
        rs._hide = False
        orig_put(doc)
    rs.put_request = put_then_reveal
    r = handle_registration_request(first, rs, schemas, now=now)
    check("a simultaneous duplicate becomes a replay, not a second document", r.outcome == "replay" and len(rs.requests) == 1)

    lim = RateLimiter(rules=((600, 5), (86400, 30)))
    results = [lim.allow("v", 1000.0 + i) for i in range(7)]
    check("rate limit: 5 allowed in 10 minutes, then refused", results == [True] * 5 + [False] * 2)
    check("rate limit: allowed again after the window", lim.allow("v", 1000.0 + 601))
    day = RateLimiter(rules=((600, 5), (86400, 30)))
    allowed = sum(day.allow("d", 1000.0 + i * 601) for i in range(40))
    check("rate limit: 30 per day cap holds", allowed == 30)
    check("rate limit: visitors are counted separately", lim.allow("someone-else", 1000.0))

    cases = [("GET", b"", 405), ("POST", b"{not json", 400), ("POST", b"x" * (64 * 1024 + 1), 413)]
    for method, raw, want in cases:
        r = handle_http(method, raw, "k", MemoryStore([]), schemas, RateLimiter(), now)
        check(f"handler: {method} with {len(raw)} bytes gives HTTP {want}", r.status == want)
    limited = RateLimiter(rules=((600, 1),))
    handle_http("POST", json.dumps(first).encode(), "k", MemoryStore([]), schemas, limited, now)
    r = handle_http("POST", json.dumps(first).encode(), "k", MemoryStore([]), schemas, limited, now)
    check("handler: second request over the limit gives rate_limited, 429 and Retry-After",
          r.status == 429 and r.body["error"]["code"] == "rate_limited" and "Retry-After" in r.headers)

    class Boom(MemoryStore):
        def get_class(self, class_id):
            raise RuntimeError("secret detail jane@example.com")
    cls_request = next(c["request"] for c in data["tests"] if c["name"] == "t05_class_pick_with_space")
    r = handle_http("POST", json.dumps(cls_request).encode(), "k", Boom([]), schemas, RateLimiter(), now)
    check("handler: a crash gives a plain server_error that reveals nothing",
          r.status == 500 and r.body["error"]["code"] == "server_error" and "secret" not in json.dumps(r.body))
    return fails


def main() -> int:
    args = sys.argv[1:]
    use_handler = "--handler" in args
    paths = [a for a in args if not a.startswith("--")]
    records = pathlib.Path(paths[0]) if paths else DEFAULT_RECORDS
    schemas = Schemas.load()
    setup = json.loads(records.read_text())["setup"]
    endpoint = (HandlerEndpoint if use_handler else CoreEndpoint)(schemas, setup)
    fails = run(records, endpoint, schemas)
    if not use_handler and records == DEFAULT_RECORDS:
        fails += run_extra_checks(schemas)
    total = len(json.loads(records.read_text())["tests"])
    if fails:
        print(f"\nFAILED: {len(fails)} problem(s)")
        return 1
    print(f"\nOK: all {total} test records pass ({'handler' if use_handler else 'core'}, in memory)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

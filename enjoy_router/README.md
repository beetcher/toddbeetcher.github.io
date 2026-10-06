# enjoy_router

The registration endpoint for /enjoy, as its own Python codebase (separate from `router/`).

## Files

- `core.py`: the rules (honeypot, readOnly fields, email cleaning, validation, idempotency, past dates, names versus count, class pick and seat snapshot, repeat flag, server fields, self-check). No Firebase in it. Follows `schemas/REGISTRATION_REQUEST_GUIDE.md` section 6.
- `handler.py`: the HTTP-shaped part (method, size, JSON, rate limit, last-resort error). No Firebase in it.
- `ratelimit.py`: 5 requests per 10 minutes and 30 per day per visitor; visitors are salted hashes, never addresses.
- `firestore_store.py`: the Firestore store. Collection names come from `schemas/registry.json`. One internal collection, `idempotency_keys`, holds a marker per submission key, written in the same atomic batch as the request.
- `main.py`: the Firebase function `enjoy_registration_request` (POST). CORS, settings, and the wiring.
- `memory_store.py`: an in-memory store for tests.
- `run_tests.py`: runs the 30 test records in memory (core, or core plus handler with `--handler`) plus extra checks (odd bodies, a simulated race, the rate limiter, error handling).
- `run_http_tests.py`: runs the same records against a running endpoint over HTTP, and checks the stored Firestore documents when pointed at the emulator.
- `sync_schemas.py`: copies the schema files into `enjoy_router/schemas/` before a deploy (git-ignored copy).
- `firebase.json`, `.firebaserc`: emulator on its own ports (functions 5101, Firestore 8180, UI 4100) so it can run beside `router/`.

## Run the tests

    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    python3 run_tests.py              # core, in memory, plus extra checks
    python3 run_tests.py --handler    # core plus HTTP handler, in memory

## Run the emulator and test it over HTTP

Terminal 1 (from `enjoy_router/`, with `venv` set up as above):

    ICDT_FIXED_NOW=2026-10-06T17:00:00Z firebase emulators:start --only functions,firestore --project demo-icdt

`ICDT_FIXED_NOW` fixes the endpoint's clock to the tests' `setup.now` (so the date rules do not depend on the day you run them). `main.py` honors it only inside the emulator, never in a deployed function.
Terminal 2:

    source venv/bin/activate
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8180 python3 run_http_tests.py \
      --url http://127.0.0.1:5101/demo-icdt/us-central1/enjoy_registration_request --project demo-icdt

The `demo-` project name keeps the emulator from touching any real project. `run_http_tests.py` refuses to read or write Firestore unless `FIRESTORE_EMULATOR_HOST` is set.

## Deploy (later, when a project is chosen)

    python3 sync_schemas.py
    firebase deploy --only functions:enjoy --project <project>

Do not deploy a Firestore rules file from here to a project that another codebase shares (a rules deploy replaces the whole file). Lock the new collections against browser writes in the dedicated project's own rules. The endpoint writes with admin access, which bypasses rules.

## Decisions (Todd, 2026-10-06)

Confirmation number `ICDT-` plus 6 characters from `23456789BCDFGHJKMNPQRSTVWXYZ`; the price the visitor saw is stored and compared later by processing, never checked at submit; a requested date may be today or later (Mountain time); rate limit 5 per 10 minutes and 30 per day per visitor.

## Known limits

- The rate limiter keeps its counts in each running copy of the function, so several copies make the real limit a little looser. App Check and a shared counter come later.
- The visitor address is the last entry of `X-Forwarded-For` (the one Google's front end appends); earlier entries can be forged.
- Class capacity is read, not reserved: a request is not a registration, so no seat is held (by design).

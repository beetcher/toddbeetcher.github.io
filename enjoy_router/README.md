# enjoy_router

The registration endpoint for /enjoy, as its own Python codebase (separate from `router/`).

- `core.py`: the rules (honeypot, readOnly fields, email cleaning, validation, idempotency, past dates, names versus count, class pick and seat snapshot, repeat flag, server fields, self-check). No Firebase in it. Follows `schemas/REGISTRATION_REQUEST_GUIDE.md` section 6.
- `memory_store.py`: an in-memory store for tests. The Firestore store comes with the wrapper.
- `run_tests.py`: replays `schemas/examples/registration_request.test_records.json` against the core.
- `main.py`: the Firebase wrapper (HTTP, CORS, rate limit, Firestore). Not written yet.

Run the tests from the repo root:

    pip install -r enjoy_router/requirements.txt
    python3 enjoy_router/run_tests.py

Schemas are read from `schemas/` in the repo, or from `enjoy_router/schemas/` if a deploy copy is there, or from `ICDT_SCHEMA_DIR`. The collection names come from `schemas/registry.json`.

Decisions (Todd, 2026-10-06): confirmation number `ICDT-` plus 6 characters from `23456789BCDFGHJKMNPQRSTVWXYZ`; the price the visitor saw is stored and compared later by processing, never checked at submit; a requested date may be today or later (Mountain time); rate limit 5 per 10 minutes and 30 per day per IP, applied in the wrapper.

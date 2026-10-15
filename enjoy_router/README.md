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

### Standalone Brevo SMTP test (manual, sends one real email)

No packages beyond Python's standard library are needed. This is independent of
registration and Firebase. The SMTP transport is disabled by default; the script
enables it only with `--send`. Do not run the send command until Todd approves
the real test. From the repository root, in a local interactive terminal:

    python3 enjoy_router/run_smtp_test.py --send

Enter the SMTP key at the hidden prompt (an SMTP key, not a Brevo API key).
Never paste it into chat or the command itself. Input is refused if the terminal
cannot hide it. The key is used only in process memory, never written or logged.

The test uses `smtp-relay.brevo.com:587`, requires certificate-verified STARTTLS,
logs in as `bdeb44001@smtp-brevo.com`, and sends from
`Launch <toddbeetcher17@gmail.com>` to `toddbeetcher17@gmail.com`.
There is one attempt, capped at about ten seconds overall, with no automatic retry.
The SMTP worker is stopped at the deadline; no send continues in a background
thread. A timeout at any stage is reported as unknown.

`PASS` (exit 0) means Brevo accepted the message; check the inbox and spam folder
to verify delivery. `FAIL` or `UNKNOWN` exits nonzero and contains no server
response or credentials. An unknown result may already have sent the message:
check for delivery before retrying. Running without `--send` exits 2 without
prompting or connecting. No registration record is created or changed.

### Registration tests

    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    python3 run_tests.py              # core, in memory, plus extra checks
    python3 run_tests.py --handler    # core plus HTTP handler, in memory

## Communications (the CMS)

All outgoing email goes through one door, `comms.notify(...)` (packages `comms/` and
`launch_comms/`). `registration_service.py` calls it only for outcome `created`, after
the atomic request save; placement confirmations are triggered from
`crud/attendances_service.py`. Wording lives in `comm_template` records, every attempt is
one `communication_log` entry, and the mode is set by `ICDT_COMMS_MODE`
(`off` / `log_only` / `live`; `ICDT_CMS_ENABLED=true` still means live). Run
`seed_comms.py` (dry run by default) once per project so templates and settings exist.
See `claude/cms-architecture-spec.md`. The old `cms_service.py`/`placement_email.py`
are gone; the legacy `correspondence` and `acknowledgment_email_*` fields are deprecated.
SMTP acceptance is not delivery or an open; one attempt, no automatic retry.
The post-save status write has a two-second RPC timeout and no retry; an error
is logged by record ID and code only, and registration success is preserved.

### Local verification: no email

From `enjoy_router/`, use the existing project Python:

    venv/bin/python run_cms_tests.py

SMTP is fake in this suite. A harmless sleeping process verifies deadline
enforcement and worker cleanup; another child process uses fake SMTP to verify
the real worker/pipe round trip. No key, network connection or real data is used.
Tests and the emulator keep CMS disabled even if the enable flag is true.

### Later provisioning and deployment (Todd's approval required)

No new dependencies. The existing Firebase SDK supplies SecretParam. After
approval, from `enjoy_router/`, create the secret with the CLI's hidden prompt;
never put its value in a command, chat or environment file:

    firebase functions:secrets:set ICDT_BREVO_SMTP_KEY --project launch-ai-workshop

Set `ICDT_CMS_ENABLED=true` in the git-ignored `.env.launch-ai-workshop`, keeping
the existing settings intact. The SMTP key stays in Secret Manager. Only the
registration function always binds the secret, even when CMS is disabled during
deployment discovery. The runtime enable flag controls sending; the secret is
read only at request time, after saving. Setting the enable flag alone never
enables CMS in the emulator. The application logger explicitly enables INFO
records containing IDs, statuses and sanitized codes, never submitted values.

Sync the deployable schema copy before deploying:

    venv/bin/python sync_schemas.py

Then, only after approval:

    firebase deploy --only functions:enjoy --project launch-ai-workshop

Deploy the server before Todd publishes the updated static schema and guide.
An enabled deployed registration endpoint sends real acknowledgments for new
requests. Do not run live tests or enable/deploy without approval. No live test
is part of the local verification above.

## Run the emulator and test it over HTTP

Terminal 1 (from `enjoy_router/`, with `venv` set up as above):

    ICDT_FIXED_NOW=2026-10-06T17:00:00Z firebase emulators:start --only functions,firestore --project demo-icdt

`ICDT_FIXED_NOW` fixes the endpoint's clock to the tests' `setup.now` (so the date rules do not depend on the day you run them). `main.py` honors it only inside the emulator, never in a deployed function.
Terminal 2:

    source venv/bin/activate
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8180 python3 run_http_tests.py \
      --url http://127.0.0.1:5101/demo-icdt/us-central1/enjoy_registration_request --project demo-icdt

The `demo-` project name keeps the emulator from touching any real project. `run_http_tests.py` refuses to read or write Firestore unless `FIRESTORE_EMULATOR_HOST` is set.

## Deploy and live test (the dedicated enjoy project)

`.firebaserc` has no default project on purpose: always pass `--project <id>`. `firestore.rules` denies every browser read and write; it is for the dedicated project only, never for one another codebase shares (a rules deploy replaces the whole file).

    python3 sync_schemas.py
    firebase deploy --only functions:enjoy,firestore:rules --project <id>

For the live test run, deploy once with the rate limit relaxed (the run sends 30 requests from one address): set `ICDT_RATE_RULES=600:1000,86400:5000` for the function, then run `run_http_tests.py --live` (see its docstring). A warning is logged whenever the override is set. When the test is done, redeploy without it.

## Decisions (Todd, 2026-10-06)

Confirmation number `ICDT-` plus 6 characters from `23456789BCDFGHJKMNPQRSTVWXYZ`; the price the visitor saw is stored and compared later by processing, never checked at submit; a requested date may be today or later (Mountain time); rate limit 5 per 10 minutes and 30 per day per visitor.

## Known limits

- The rate limiter keeps its counts in each running copy of the function, so several copies make the real limit a little looser. App Check and a shared counter come later.
- The visitor address is the last entry of `X-Forwarded-For` (the one Google's front end appends); earlier entries can be forged.
- Class capacity is read, not reserved: a request is not a registration, so no seat is held (by design).

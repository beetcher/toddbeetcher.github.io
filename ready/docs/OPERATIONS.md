# READY — Setup, verification, deployment and rollback

## What is running versus verified

The service, management interface and Firebase adapter/entrypoint are implemented. Offline service/HTTP checks do not prove a deployed function or real Firestore behavior. See BUILD_STATUS.md for exact evidence and blockers. Production is the separate `beetcher-ready` Firebase project, with Firestore Native and Functions in `us-central1`. Owner authorized project creation and linking the existing billing account. Canonical workshop: https://beetcher-ready.web.app/ready/. The key is in Secret Manager; see ACCESS.md for owner connection. No production key is in source.

## Local development, synthetic data only

From repository root, Python 3.11+:

```bash
python3 -m venv ready/.venv
ready/.venv/bin/python -m pip install -r ready/requirements.txt
ready/.venv/bin/python ready/schemas/check.py
ready/.venv/bin/python -m unittest discover -s ready/tests -v
```

Choose a local secret of at least 32 characters. In an interactive Bash terminal, enter it without echo:

```bash
read -rs READY_API_KEY
export READY_API_KEY
ready/.venv/bin/python -m ready.devserver --demo --seed
```

Open `http://127.0.0.1:8765/ready/`. Enter that local key in the connection field. Demo mode is **ephemeral memory**: restarting discards only this synthetic development database. After a successful connection the tab remembers its key in sessionStorage across reloads; Disconnect removes it. The UI identifies MemoryStore prominently; it is not the indefinite production store. Production always selects Firestore explicitly and never falls back to memory.

To run the same development HTTP boundary against a configured Firestore project, install `runtime-requirements.txt`, use Application Default Credentials appropriate to that project and pass `--project PROJECT_ID` instead of `--demo`. This accesses real product data: use the emulator first. Do not use `--seed` for live Firestore; authenticated import preview/commit is the explicit path.

## Browser verification

Install optional `browser-requirements.txt` and use Chromium or Playwright's installed browser. Run:

```bash
ready/.venv/bin/python ready/scripts/browser_check.py
```

This script drives the real HTML/CSS/JS and actual Application through intercepted in-process requests on a synthetic HTTPS origin. It does not need outbound Internet or a local HTTP socket, but Chromium still needs local IPC support. It validates connect, import preview/commit, native library, duplicate pairs, immutable test creation, discrepancy display, result history and mobile overflow; screenshots go to the selected artifacts directory. Socket/IPC denial means **blocked**, not passed. Run the same workflow over actual stdlib HTTP, plus a static Pages-layout preview check, with `python ready/scripts/browser_check.py --transport http`. Both modes have passed on the Mac; CSP remains enforced. Browser screenshots include desktop, results, mobile and the unconnected preview.

## Firebase project prerequisites

The selected new project is **beetcher-ready**, administered by the authorized owner account. Its `(default)` Firestore Native database is in **us-central1**, and billing is enabled. All five composite indexes were verified READY and the active ruleset was inspected to confirm browser reads/writes are denied. These resources are separate from LAUNCH. Do not infer an existing LAUNCH project or silently replace its rules. Cloud Functions/Hosting/Firestore must be enabled and billing/quota prerequisites satisfied by the project owner. Default function region is `us-central1`; choose the Firestore location deliberately before creating its database.

Use an authenticated Firebase CLI on a deployment workstation. No default `.firebaserc` project is included. Set `READY_FIREBASE_PROJECT` to the explicitly selected new project ID; every cloud command below includes it. Do not paste keys into chat or command arguments.

## Prepare a self-contained function

From repository root:

```bash
python3 ready/scripts/prepare_deploy.py
python3 -m venv ready/.firebase-build/venv
ready/.firebase-build/venv/bin/python -m pip install -r ready/.firebase-build/requirements.txt
```

Staging creates `main.py`, runtime requirements and an importable `ready` package. It excludes env files, tests, virtualenvs and unrelated site media. The `venv` directory and `.secret.local` are explicitly excluded by Firebase configuration, and `.firebase/` caches are excluded from staging/version control. Re-running staging replaces that generated directory; keep durable secrets in Secret Manager, not staging. It does not choose a project or deploy. Python 3.12 runtime is declared in firebase.json.

## Real emulator verification

From `ready/`, configure a local `.firebase-build/.secret.local` containing the local emulator READY_API_KEY using a secure editor (ignored, never commit). Then:

```bash
firebase emulators:start --only functions,firestore,hosting --project demo-ready-local
```

The fixed demo project prevents accidental production access. Functions/Firestore ports are 5201/8280; Hosting can use its CLI default. In another terminal from repository root with runtime dependencies installed:

```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8280
export READY_EMULATOR_PROJECT=demo-ready-local
ready/.firebase-build/venv/bin/python ready/scripts/emulator_check.py
```

The script refuses missing emulator settings or non-demo projects. It retains tagged synthetic records; it never deletes product data. Check management through Hosting or the appropriate emulator function URL with its route prefix. Hosting rewrites provide canonical `/ready/` and `/v1/` paths; opening a bare Cloud Functions URL with nested prefixes may not resolve absolute browser asset URLs.

## Cloud deployment

Run offline checks and emulator checks first; explicitly acknowledge any unverified gate before live use. From `ready/`, with READY_FIREBASE_PROJECT set to the new project's actual ID:

```bash
firebase functions:secrets:set READY_API_KEY --project "$READY_FIREBASE_PROJECT"
firebase deploy --only functions:ready,firestore:rules,firestore:indexes,hosting --project "$READY_FIREBASE_PROJECT"
```

The CLI secret prompt hides its value. Initial key is super admin. Functions are capped at three instances. A 30-day Artifact Registry cleanup policy applies only to disposable container build images, not product records. Hosting redirects `/` to `/ready/` and rewrites management/API paths to ready_api in us-central1. This hosting is for the new READY project; no beetcher.com domain change is implied. Firestore rules deny all browser reads/writes; server Admin SDK uses the runtime service account. Review its project IAM permissions. Index definitions include same-collection linked-revision lookups.

## Non-destructive smoke checks

1. Health returns version; unauthorized API reads fail 401. Missing server key fails closed.
2. Key-authenticated capabilities names FirestoreStore, not MemoryStore.
3. Management assets load on canonical Hosting URL; no key exists in served source or browser persistence.
4. Import preview stores nothing. Commit deliberately tagged validation data with a new key.
5. Assemble/retrieve an immutable test, submit a known result with intentionally different returned score, inspect both scores and discrepancy.
6. Retry same submission (one record); submit identified updated report (linked version); inspect original evidence.
7. Archive validation records/tests; verify retained historical access and delayed-result recording. Never run a destructive cleanup script.
8. Verify actual deployed database rules, indexes and key configuration, not only files. Avoid logging submitted data, API keys and person IDs.

## Rollback and failure handling

- Record the source commit and deployment revision. To roll code back, check out the known-good source, restage, reinstall runtime dependencies and redeploy the READY function/Hosting to the same explicit project. Do not roll data back by deletion.
- Schemas are versioned; old record versions remain readable. No automatic migration/purge is implemented. A breaking schema change needs an explicit migration/read-compatibility plan before deploy.
- If import/result response is lost, retry identical body/key. Do not generate a new key until you intend another genuine operation.
- A conflicting reuse returns 409; inspect input/version rather than bypass it. A candidate-pool or document limit returns validation failure rather than sampling/truncating silently.
- Key rotation: add/update Secret Manager value, redeploy the function binding and distribute the new key through an approved secret channel. Initial implementation has one key, no multi-role UI. Old key ceases to authorize calls after rotation.
- In-process rate limiting is best-effort across function instances; CORS is not authentication. Enable stronger edge protection when deployment exposure requires it; do not invent participant sessions.

## Full Hosting boundary and durability checks

`ready/scripts/hosting_check.py` checks the actual HTTP origin, not an intercepted in-process bridge. Supply a private file containing only the key (or emulator `READY_API_KEY=...` line); never put the key in command arguments. The check intentionally creates tagged builder validation data, verifies it, then archives it without deletion. A synthetic seed variant exercises ambiguous grading without changing the shipped educational seed.

```bash
python ready/scripts/hosting_check.py --base-url https://beetcher-ready.web.app --key-file /private/path/to/key --evidence /private/path/to/live-evidence.json --browser
```

It checks auth/FirestoreStore, assets, dry-run/no-write, exact seed counts, replay, shortage preservation, duplicate pairs, frozen content after revisions, distinct variants, full/half/zero scoring, original submitted JSON, retained corrections, independent anonymous results, native browser authoring/revisions, mobile layout, archival and delayed results against archived tests. The evidence manifest contains only synthetic validation record IDs and frozen test content, never the key. Respect the five-collection 1,000-revision cap when repeating checks.

After restarting or redeploying, verify retained evidence with no new writes:

```bash
python ready/scripts/hosting_check.py --base-url https://beetcher-ready.web.app --key-file /private/path/to/key --verify-manifest /private/path/to/live-evidence.json --evidence /private/path/to/durability.json
```

The first deployment required an explicit `firebase functions:artifacts:setpolicy --location us-central1 --days 30 --project beetcher-ready --force` before Hosting could finish. The policy is now configured. Runtime currently uses Firebase's default compute service account in this dedicated project, with Firestore access and an explicit binding to this one secret. The account's project-level Editor role is the Firebase provisioning default; differentiated runtime IAM is not claimed. Exact-origin CORS is empty because the workshop and API share an origin. API auth, server validation, CSP, per-tab sessionStorage with explicit Disconnect clearing and deny-browser Firestore rules remain enforced.

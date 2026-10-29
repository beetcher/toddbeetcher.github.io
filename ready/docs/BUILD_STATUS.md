# READY build status — October 28, 2026 (America/Denver)

## Operational service

Canonical management URL: **https://beetcher-ready.web.app/ready/**. API shares that origin under `/v1/`. Project **beetcher-ready** is new and separate from LAUNCH. Firestore Native `(default)` and Python 3.12 Gen 2 function `ready_api` are in **us-central1**. Owner authorized creation and the existing billing-account link. Runtime uses Secret Manager `READY_API_KEY`, never MemoryStore fallback. See ACCESS.md for the owner's connection steps.

The Pages route **https://beetcher.com/ready/web/** is a styled, unconnected preview. Relative CSS/JS and static seed paths work there; key entry is hidden/disabled, API actions explain the preview boundary, and the page links to the canonical workshop. Firebase's application handles canonical trailing-slash redirects; a Hosting `/ready` redirect was removed because its slash matching caused a loop.

## Verified evidence

- Five collection schemas, eleven request contracts, fifteen output contracts/fixtures valid.
- **57 unit/service/HTTP/adapter tests pass**; JS syntax and Firebase runtime import pass.
- Real Chromium workflow passes with CSP enforced, both intercepted transport and actual local HTTP; mobile overflow, tabs, import/no-write, selection, duplicate pairs, frozen tests, discrepancies and correction history checked. The earlier CI failure was the browser script's string-evaluation wait under CSP; function predicates fixed it without weakening CSP.
- Real Firestore emulator passes native timestamps, import/replay, frozen tests, concurrent correction chains, original submitted JSON readback and retained evidence. Export/restart/import plus HTTP manifest readback passed.
- Self-contained Functions discovery and Hosting rewrites run through the actual emulator. Deployment package shrank from an intercepted 85 MB preparation to approximately **259 KB** after explicitly excluding the local virtual environment and emulator secret. No oversized package was uploaded.
- Cloud Function creation and Hosting release succeeded. Public health returns 200; unauthenticated API reads are rejected; authenticated capabilities names **FirestoreStore**. All five production composite indexes are **READY**. The active Firestore ruleset was fetched and inspected: direct browser reads/writes denied; unauthenticated direct Firestore REST read returns 403.
- Live HTTPS smoke check passed: seed dry-run/no writes, ten questions/38 answers/ten sets, same-key import replay, explicit shortage, two duplicate pairs with unique occurrence IDs, immutable variants and frozen content after revisions, full/half/zero grading, retained original JSON, returned/calculated score discrepancy, same-key result replay, linked identified corrections, independent anonymous submissions, native browser create/revise, tabs, memory-only key handling and mobile layout.
- All **69 live validation records** were retained and archived. A new result against an already archived test was accepted and archived too. No product records were deleted. The synthetic half-credit test uses an isolated validation-seed variant; the shipped educational seed remains unchanged.
- READY CI at checkpoint `784893e485d0f917b68179fab3650cb1e54cee80` passed both browser/contract and real-Firestore jobs. Current branch CI and the final deployment/readback identity are recorded in the local completion evidence. Historical intermediate CI failures are not treated as passing evidence.

The final source checkpoint is redeployed after these documentation/preview-link updates. Exact pushed SHA, function revision, deployment result and retained-record readback belong in the completion evidence, avoiding a self-referential SHA in this document. Evidence is retained in the separate Masthead workspace's `READY-VERIFICATION/` folder, including live desktop/mobile screenshots and JSON manifests without secrets.

## Scope and operating limits

Five domain collections only: questions, answers, question_answer_sets, tests, attempts. The caller administers delivered tests; no participant player, timer, token/session APIs, AI interpretation, written answers or role system was added. Initial key is super admin.

Product versions persist indefinitely; archive changes availability without deleting evidence. Current selection is explicitly bounded at **1,000 stored revisions per collection**, including history, and fails on overflow. It does not silently truncate or finalize shortages. Metadata extensions remain schema-registered. Rate limiting is per process, 180 authenticated requests/minute/address; Functions are capped at three instances. See D002/D003 for exact grading and concurrency defaults. Runtime currently uses Firebase's default compute service account in this dedicated project; finer runtime IAM is not claimed.

Native Safari is not an acceptance-tested browser. Chromium desktop/mobile layout and actual HTTPS/Firestore behavior are tested. This status replaces the original restricted-cloud snapshot's access/blocker claims; the real Mac checkout is on `finish-now`, and no history was replaced or new branch created.

# FIX: candidate pool cap raised from 1,000 to 10,000

## Problem
`MAX_POOL = 1000` in `ready/services.py`. `ReadyService._inventory` reads `MAX_POOL + 1` records of one kind and raises `candidate_pool_too_large` above the cap. `list()`, `select()` and the sets scan in `relationships()` all use it. The live database holds about 1,600 answers and 500 sets, so connecting at /ready/ failed.

## What I found
- `HANDLERS[kind].inventory(store, limit)` calls `record_kit.inventory`, which calls `store.query(collection, limit=limit)`.
- Firestore adapter (`crud/firestore_store.py`): one `order_by("created_at").limit(limit)` stream. The limit is a plain bound, with no paging and no per-record queries. Inside a transaction it also merges pending writes.
- In-memory store: filters, sorts and slices to the limit.
- The cap is only a safety bound. Nothing else depends on 1000. A plain raise is safe, so no pagination was added.
- Cost note: each list, select or connect reads every record of that kind (about 1 Firestore read each). At 1,600 answers that is 1,600 reads per call. At the new cap it is at most 10,001 reads per call. List pages are still sliced in memory.

## Change
- `ready/services.py`: `MAX_POOL = 10000`. Behavior above the cap is unchanged (`candidate_pool_too_large`, `details.max_candidate_scan` now 10000).
- `ready/tests/test_services.py`: added `test_pool_above_1000_answers_lists_and_selects` (1,100 answers in the memory store; list page at cursor 1000 and select work) and `test_pool_above_cap_still_refused` (cap lowered to 5 in the test; error still raised). No existing test asserted the old 1000.

## Not changed (outside the allowed files)
- `ready/application.py:164` still reports `"max_candidate_scan": 1000` in the capabilities response, and `ready/docs/openapi.json` only types the field as integer. The value reported to the page is now out of date. Change it to 10000 (or import `MAX_POOL`) in a follow-up.

## Test results (before and after)
| Check | Before | After |
|---|---|---|
| schemas/check.py | valid | valid |
| test_foundation | 22 OK | 22 OK |
| test_services | 19 OK | 21 OK (2 new) |
| test_http | 15 OK | 15 OK |
| test_firestore_adapter | 2 OK | 2 OK |

Run with `ready/.venv/bin/python -m unittest ready.tests.test_<name>` from the repo root. The Firestore emulator was not run.

## Deploy step (owner must run; nothing was deployed)
From `ready/`, with `READY_FIREBASE_PROJECT` set to the project ID (`beetcher-ready`), after restaging with `python3 ready/scripts/prepare_deploy.py` from the repo root (OPERATIONS.md):

```bash
firebase deploy --only functions:ready --project "$READY_FIREBASE_PROJECT"
```

OPERATIONS.md gives the full command `firebase deploy --only functions:ready,firestore:rules,firestore:indexes,hosting --project "$READY_FIREBASE_PROJECT"`; that also works. No rules, index or hosting change is needed for this fix. Record the source commit and deployment revision.

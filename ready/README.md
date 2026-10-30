# READY

READY is Todd Beetcher's reusable question, answer, test-generation and returned-result service. It is general enough for AI readiness, practical skills and system training. The service delivers identified tests; the caller administers them and returns results. It does not run participant sessions.

## Background and use cases

Bobby Hodgkinson suggested an AI-readiness quiz. Todd developed the idea into independent question/answer inventories, contextual sets, immutable tests and preserved results. External product research informed the design; this is Todd's own product and development demonstration.

Use READY to author introductory or challenging sets from reusable atoms, select by topic/audience/difficulty/objective/tags, deliver a cohort's standardized test, build alternative tests, and retain caller and calculated results with discrepancies. Content labels do not establish psychometric equivalence or a certification. AI-readiness examples are not official NOCTI assessments.

## Current build status

The management workshop and API are deployed at **https://beetcher-ready.web.app/ready/** with durable Firestore persistence in the separate `beetcher-ready` project. The Pages route `/ready/web/` is a styled, explicitly unconnected preview. See [owner access](docs/ACCESS.md), [build status](docs/BUILD_STATUS.md) and [operations](docs/OPERATIONS.md) for verified evidence and exact usage.

## Saved test downloads

In the saved-test inspector, **Download test PDF** sits beside **Download test JSON**. The PDF is a paginated review copy of the saved test, including its questions, contextual answer classifications and feedback. It includes the answer key shown on screen. Exporting it does not change the stored test.

## Get the admin key on this Mac

Run this in Terminal:

```bash
cd /Users/nddev/nd/bd/toddbeetcher.github.io/ready
./getadminkey.sh
```

The executable `getadminkey.sh` is an owner-only local helper. It is Git-ignored and excluded from Firebase deployment packaging, so it stays on this Mac rather than being committed or published. It contains no embedded key. It retrieves the existing `READY_API_KEY` from Google Secret Manager in project `beetcher-ready`, using the authorized account `toddbeetcher17@gmail.com`, and copies it directly to the Mac clipboard. It does not print the key, save it in a file, create a new key or rotate the existing key.

Open **https://beetcher-ready.web.app/ready/**, paste into **Super-admin API key**, and click **Connect**. Expect **FirestoreStore · super admin**. The input clears and the accepted key is remembered in this tab’s `sessionStorage`. Refresh and hard refresh reconnect automatically after checking the key with the API. **Disconnect** clears it immediately; closing the tab normally ends its session. Browser restore/duplicate-tab features can restore or copy a tab session, so use Disconnect when you want explicit removal. It is never placed in `localStorage` or cookies. The initial key has super-admin access; possession of the local helper alone does not grant Google account access.

If the helper reports a sign-in error, run `gcloud auth login toddbeetcher17@gmail.com`, complete the Google sign-in, and run the helper again. It requires `gcloud` and the Mac's `pbcopy`. To clear the clipboard after pasting, run `printf '' | pbcopy`.

This README is public documentation and contains no secret. On another authorized machine without the local helper, the equivalent command is:

```bash
gcloud secrets versions access latest --secret=READY_API_KEY --project=beetcher-ready --account=toddbeetcher17@gmail.com | pbcopy
```

## Source and current hosting

The local Git repository is `/Users/nddev/nd/bd/toddbeetcher.github.io`, branch `finish-now`; READY source lives in its `ready/` directory and is pushed to GitHub. The separate Masthead chat workspace contains planning and verification notes.

The running workshop is currently on **Google Firebase Hosting**, its API runs as a Google Cloud Function, and its durable data is in Firestore, all in the separate Firebase project **beetcher-ready**. Firebase deployment was performed from the Mac with the Firebase CLI; it is separate from the existing GitHub-to-Cloudflare deployment of beetcher.com. The live service runs independently of the Mac.

**beetcher.com/ready is the intended public integration, but that integration is not implemented yet.** The existing `beetcher.com/ready/web/` route is an unconnected preview linking to the functional Firebase-hosted workshop. Do not enter the admin key into that preview.

## Verification and local demo

From repository root:

```bash
python3 ready/schemas/check.py
python3 -m unittest discover -s ready/tests -v
node --check ready/web/main.js
```

Install `ready/requirements.txt` for offline checks, or `ready/runtime-requirements.txt` for Firebase runtime dependencies. Set a local `READY_API_KEY` of at least 32 characters, then run `python3 -m ready.devserver --demo --seed` and open `http://127.0.0.1:8765/ready/`. Demo memory is temporary synthetic data; production explicitly uses Firestore. Follow the operations guide for secure key entry, browser checks, emulator checks and deployment.

## Structure and architecture

Five domain collections: questions, answers, question_answer_sets, tests and attempts. No people collection. Connections and returned item responses are nested schemas, not new collections. A question/answer atom has no universal question-specific correctness. That belongs to a connection inside an authored set. A test freezes an assembly of sets. A submitted run/result is an attempt against the test.

Follow the repository's schema-first method: schema/registry/guide/examples → model-shaped handler → service → endpoint → management surface. JSON Schema is checked by the established shared kit's standard `jsonschema` validator. Cross-record checks belong to services. Browser code never writes Firestore directly.

See `docs/ARCHITECTURE.md`, `docs/API.md`, and `docs/decisions/0001-foundation.md`. The initial API key is super admin; differentiated roles are future work. Person IDs belong only on result submissions. All product versions are retained; decommission/archive never means hard delete.

## Parking lot

Participant test player, live navigation/feedback timing, participant tokens/sessions, AI narrative interpretation, written answers, differentiated roles, test events with place/date/time, premium packaging and calibrated cohort difficulty. These are not required to implement test delivery/result recording.

### Favicon artwork

The workshop uses a single staring blue eye (`web/favicon.svg`). Each page load varies its iris shade, fibers, and pupil size in the browser. The original two-eye artwork is preserved unchanged in `web/favicon-eyes.svg`, available at https://beetcher-ready.web.app/ready/favicon-eyes.svg.

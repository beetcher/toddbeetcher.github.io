# READY

READY is Todd Beetcher's reusable question, answer, test-generation and returned-result service. It is general enough for AI readiness, practical skills and system training. The service delivers identified tests; the caller administers them and returns results. It does not run participant sessions.

## Background and use cases

Bobby Hodgkinson suggested an AI-readiness quiz. Todd developed the idea into independent question/answer inventories, contextual sets, immutable tests and preserved results. External product research informed the design; this is Todd's own product and development demonstration.

Use READY to author introductory or challenging sets from reusable atoms, select by topic/audience/difficulty/objective/tags, deliver a cohort's standardized test, build alternative tests, and retain caller and calculated results with discrepancies. Content labels do not establish psychometric equivalence or a certification. AI-readiness examples are not official NOCTI assessments.

## Current build status

The management workshop and API are deployed at **https://beetcher-ready.web.app/ready/** with durable Firestore persistence in the separate `beetcher-ready` project. The Pages route `/ready/web/` is a styled, explicitly unconnected preview. See [owner access](docs/ACCESS.md), [build status](docs/BUILD_STATUS.md) and [operations](docs/OPERATIONS.md) for verified evidence and exact usage.

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

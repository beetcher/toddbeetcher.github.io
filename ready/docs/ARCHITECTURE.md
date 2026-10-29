# READY architecture and implementation boundaries

Decisions D001 and D002 document the implemented boundaries. This document contains no participant administration design.

## Layers

`management surface / caller → HTTP endpoint → service → collection handler → store → Firestore`

Handlers never join collections or make HTTP/network calls. Services select/reference content, snapshot tests and grade returned results. `crud/schema_kit.py` is the scoped upstream adaptation; `record_kit.py` factors common validation/preservation mechanics without owning field-specific business rules. Each of five collection modules loads its own registered schema and has the five familiar CRUD functions plus explicitly named protected constructors/archive methods.

The root `schemas/` registry belongs to LAUNCH. READY's separate `schemas/registry.json` uses identical naming/conventions in its own codebase. This avoids adding workshop-specific fields/services and makes packaging into a new Firebase project explicit. The production package will include READY's schema folder; no runtime remote schema fetch.

## Content and preserved history

All records have server-generated UUID identity, provenance and schema version. Content/result revisions are linked records: a new ID references `previous_id` and retains `series_id`. `revision_number` tracks chain content; `record_version` guards metadata concurrency. Archival appends an event with actor/time/reason and never erases content. Decommissioning only affects availability. Current-chain selection belongs to services; raw handler lists intentionally include historical nonarchived revisions.

Test content is immutable. A service composes snapshots with per-occurrence `item_id` (different from question/set IDs). Archive metadata is independently mutable with audited history. A new test variant is a new immutable record, not a PATCH to an old test. Test snapshots contain complete authored answer text and connection roles, never an implicit global correctness map.

`questions` and `answers` have independent author/source/notes and metadata. `question_answer_sets` reference a question and contextual answer connections. Each connection has role, explanation, notes and metadata. Services resolve exact revisions and publication/availability before assembly. Sets may intentionally reuse atoms across different contexts.

## Selection and extensions

Metadata uses explicit plural fields: `topics`, `audiences`, `learning_objectives`, `tags`, and singular `difficulty`. Proposed initial difficulty vocabulary is introductory/basic/intermediate/advanced/expert. AND across dimensions; OR among topics/audiences/difficulties/objectives within one dimension; every specified tag required. The selection service enforces these documented semantics, pool bounds and criteria combinations—no arbitrary caller Firestore predicates.

`metadata.attributes` starts closed. To add a typed dimension: edit canonical fragments; document meaning/vocabulary/operator; run fragment sync; extend import/UI/filter mapping/indexes and fixtures. No per-deployment unknown attributes may silently bypass validation. This schema-driven extension is designed to support the owner's evolving criteria while keeping rules in one place.

Canonical definitions live in `schemas/fragments.json`; self-contained copies in documents/contracts must match. Run `python3 ready/scripts/sync_fragments.py` after editing them, then checker/tests. Operation-specific `question_input`/`answer_input` definitions also must remain equivalent to writable document fields.

## Returned result boundary

Tests never receive a person ID. Caller returns a test ID, optional person ID and test time, occurrence-based responses and a returned score. Service grades using the frozen test, store both reports and diagnostics, and create an attempt record. If person ID is supplied, require caller occurrence time; anonymous reports are independent. Corrections append a linked record for the same test/person/time. Transport retry has its own idempotency key and is not a correction.

No live response endpoint, completion/navigation/feedback-release protocol, player token or participant session. Authored explanations and breakdowns returned with recorded results are output data for the caller to use. AI interpretation remains parked.

## Concurrency and runtime checkpoint

MemoryStore provides locked atomic callbacks and rollback. FirestoreStore buffers transactional writes until reads finish, converts native timestamps and uses real Firestore transactions. Cross-record reference checks, atomic imports, idempotency receipts and identified result-chain heads are implemented. A bounded inventory of at most 1,000 stored revisions per collection supports compound selection; exceeding it fails explicitly. This is an initial scale boundary, not an unbounded indexed search claim.

Offline tests cover the service and HTTP application plus adapter serialization/buffering. Real emulator concurrency, actual HTTP browser workflows and Firebase Hosting/Functions/Firestore checks now run successfully on the Mac. See BUILD_STATUS.md for current live verification and CI evidence. Memory tests remain distinct from Firestore evidence.

The operational project is `beetcher-ready`; canonical management URL is https://beetcher-ready.web.app/ready/. The API key is bound from Secret Manager. Pages is an unconnected preview. Initial key super admin; management surface must not embed it in a publicly served page. Differentiated keys/roles, public participant session infrastructure and hard deletion are outside this build.

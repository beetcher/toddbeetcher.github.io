# READY API reference

Version 1.0 · implemented local application contract. Cloud deployment and browser/emulator verification have separate gates; see BUILD_STATUS.md.

READY supplies identified tests and records returned results. The caller administers tests. All current operations use the initial super-admin API key, except health. `Authorization: Bearer <key>`; JSON bodies; prefix `/v1`. Full machine-readable interface: [OpenAPI](openapi.json). Document/request/output contracts live in `../schemas/`, available through authenticated schema discovery.

## Exact data vocabulary

Questions/answers are independent atoms. Sets have question_id and ordered connections with answer_id, contextual role (`strong`, `ambiguous`, `incorrect`), feedback/notes and metadata. No global correctness flag. Rich signal: topics, audiences, difficulty, learning_objectives, tags, description, origin and registered attributes.

Test input: label, metadata, origin, ordered set_ids, allow_duplicates, duplicate_pair_count. A test freezes resolved content and source revisions. Every occurrence has item_id; repeated questions/sets remain separate. Different content creates a new test ID. No person ID allowed here.

Result input: test_id, responses of item_id/answer_ids, returned_score, idempotency_key; optional person_id requires test_taken_at. No test wording/choice text needs to be resent. A genuine report creates an attempt, a retry does not. Matching identified test/person/time reports create a linked version chain; anonymous reports are distinct. All product versions persist, with archive/decommission only.

Result output: returned_score, calculated_score, score_difference, per-item authored explanations/ambiguous diagnostics and topic/objective breakdowns, attempt identity and history references. `submitted_payload` preserves original validated caller evidence. See [grading/runtime decisions](decisions/0002-runtime-and-grading.md) for exact arithmetic, edge-case defaults and limits.

## Operations

| # | Method/path | Input | Output contract |
|---|---|---|---|
| 1 | GET `/health` | `Path/query parameters` | `discovery` |
| 2 | GET `/capabilities` | `Path/query parameters` | `discovery` |
| 3 | GET `/schemas` | `Path/query parameters` | `discovery` |
| 4 | GET `/schemas/{name}` | `Path/query parameters` | `discovery` |
| 5 | POST `/person-ids` | `{}` | `discovery` |
| 6 | POST `/questions` | `question_create` | `question_record` |
| 7 | GET `/questions/{id}` | `Path/query parameters` | `question_record` |
| 8 | GET `/questions` | `Path/query parameters` | `question_page` |
| 9 | PATCH `/questions/{id}` | `question_patch` | `question_record` |
| 10 | DELETE `/questions/{id}` | `archive_request` | `question_record` |
| 11 | POST `/answers` | `answer_create` | `answer_record` |
| 12 | GET `/answers/{id}` | `Path/query parameters` | `answer_record` |
| 13 | GET `/answers` | `Path/query parameters` | `answer_page` |
| 14 | PATCH `/answers/{id}` | `answer_patch` | `answer_record` |
| 15 | DELETE `/answers/{id}` | `archive_request` | `answer_record` |
| 16 | POST `/sets` | `question_answer_set_create` | `question_answer_set_record` |
| 17 | GET `/sets/{id}` | `Path/query parameters` | `set_detail` |
| 18 | GET `/sets` | `Path/query parameters` | `question_answer_set_page` |
| 19 | PATCH `/sets/{id}` | `question_answer_set_patch` | `question_answer_set_record` |
| 20 | DELETE `/sets/{id}` | `archive_request` | `question_answer_set_record` |
| 21 | GET `/questions/{id}/answers` | `Path/query parameters` | `relationship_page` |
| 22 | GET `/answers/{id}/relationships` | `Path/query parameters` | `relationship_page` |
| 23 | POST `/selections` | `selection_request` | `selection_output` |
| 24 | POST `/content/imports` | `bulk_import` | `import_output` |
| 25 | POST `/tests` | `test_create` | `test_record` |
| 26 | GET `/tests/{test_id}` | `Path/query parameters` | `test_record` |
| 27 | GET `/tests` | `Path/query parameters` | `test_page` |
| 28 | POST `/tests/{test_id}/variants` | `test_create` | `test_record` |
| 29 | PUT `/tests/{test_id}/archive` | `archive_request` | `test_record` |
| 30 | POST `/attempts` | `result_submit` | `result_detail` |
| 31 | GET `/attempts/{attempt_id}` | `Path/query parameters` | `result_detail` |
| 32 | GET `/attempts` | `Path/query parameters` | `attempt_page` |
| 33 | GET `/tests/{test_id}/attempts` | `Path/query parameters` | `attempt_page` |

Four additional `PUT /{questions|answers|sets|attempts}/{id}/archive` operations use archive_request and return the retained record. Tests use their dedicated archive route. Library DELETE is a compatibility alias for non-destructive archive and requires reason and expected_record_version; the server supplies is_archived=true. There is no DELETE test/attempt route or hard purge.

## Requests, outputs and errors

Input schemas: registry in `schemas/contracts.json` (eleven contracts). Output schemas: `schemas/outputs.json` (fifteen complete contracts/fixtures). Stored schemas are not accepted as writable request bodies; service-generated fields are protected recursively. HTTP validates domain output schemas too, so a wrong response shape fails closed as a server error.

Success envelope: `{ok:true,data:...,request_id:UUID}`. Error envelope: `{ok:false,error:{code,message,fields:[{field,code}],details:{}},request_id:UUID}`. No raw SDK errors, submitted person IDs/content or secrets in logs. Content create/import/test/result operations return 201; retry returns 200 with Idempotency-Replayed:true. Existing record updates/archive and reads return 200. Invalid caller/schema data is 422; malformed JSON/query is 400; auth is 401; conflicts 409; missing resources 404; oversized requests 413; rate limit 429; unexpected/output errors 500; missing configured key 503.

Creation keys are UUIDs in Idempotency-Key for content/tests/variants. Import and result submissions use idempotency_key in the JSON body (header fallback accepted). Same key/body preserves operation identity and evidence; current archival/chain metadata may evolve. Content PATCH requires If-Match with its quoted integer record version and returns a new linked revision ID. Archive request contains expected_record_version and reason; no content deletion.

## Retrieval and selection

Lists accept limit 1–100/default25, nonnegative offset cursor, include_archived/include_history booleans and JSON criteria. Attempts alone accept exact person_id/test_id. Offset cursors are not stable snapshots under concurrent updates. The internal scan examines at most 1000 stored revisions per collection; over-limit is an explicit error, never a random first-page sample.

Selection criteria combine AND across dimensions; OR within topics/audiences/difficulties/objectives; all specified tags required. Target is questions/answers/sets. `explicit` uses unique IDs; `ordered`/`random` requires count. Existing choices can be excluded for additive searches. Return requested_count, found_count, shortfall_count, items and start_over/add_more/cancel actions on shortage. The caller retains its working list; the service never discards it or silently finalizes a smaller test.

Random choice samples the full bounded eligible pool without replacement. Eligibility is published, current and unarchived; sets also need available referenced atoms. Metadata belongs to the selected record; frozen test output preserves separate atom/set/connection metadata, with set values overlaying question defaults for result grouping. Attributes are schema-registered extensions, not arbitrary caller database predicates.

Duplicate pairs are validated at test creation: one repeated question appears exactly twice; two pairs occupy four positions. Different sets of the same question may be paired. No triplets, duplicate answer choice or repeated occurrence ID. A test must explicitly match its declared pair count; a library selection is not itself a test.

## Scope exclusions

No next-question, per-answer administration, feedback-release, participant token, timer, session start/complete/resume or conversational AI endpoint. AI interpretation, written answers, differentiated roles, test events and premium packaging remain in the parking lot. Management UI submits reports as a caller; it does not administer tests.

## Saved-test PDF export

`GET /v1/tests/{test_id}/pdf` requires the same super-admin Bearer key as JSON retrieval. It accepts no query parameters or content. Success is an `application/pdf` attachment named `ready-test-<UUID>.pdf`, rather than a JSON envelope; errors retain the standard JSON error envelope and status codes. The saved test record is validated against `test_record` before rendering.

**Download test PDF**, beside **Download test JSON** in the inspector, exports a read-only review copy of the frozen test, with title/ID, author, numbered question occurrences, every offered answer, contextual classifications and teaching feedback. It includes the answer key visible on screen; it is not a participant exam sheet. Archived tests remain exportable. PDF generation does not revise a test or create another record. Text is escaped and embedded fonts support the seed's typographic punctuation; letter-sized pages wrap content and include page numbers.

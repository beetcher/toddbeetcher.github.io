# D002/D003 — Implemented service and runtime choices

These are explicit engineering defaults under Todd's authorization to proceed. Owner-confirmed strong/ambiguous scoring, test/result separation, indefinite retention, person-ID placement, duplicate pairs and linked updates remain governing requirements.

## D002 Grading and output

Frozen policy identifier: `strong_soft_fraction_v1`.

- A question with one strong answer earns 1 when selected, regardless of whether an ambiguous choice is also selected/omitted.
- Ambiguous choices alone earn 0.5 when every strong answer was missed.
- Multiple strong answers: earned credit is the fraction of strong answers selected. Ambiguous choices do not change that fraction.
- Selecting a definitely incorrect option earns 0 for that occurrence. Unanswered/empty selection earns 0. A single-choice occurrence cannot have multiple selections.
- The last two generalizations resolve remaining engineering edge cases; they were not represented as verbatim owner decisions. They are testable policy, not AI interpretation or a validated proficiency model.
- One possible point per occurrence; repeated items are independently scored. Aggregate topics/objectives include every occurrence carrying each label; categories can overlap and must not be summed as exclusive totals.
- Credit/point sums round half-up to six decimal places. Percentages and percentage-point differences round half-up to two. Returned raw score is retained; matching denominator does not prove identical grading methodology.
- Return both scores, per-item authored feedback, ambiguous-choice diagnostics, topic/objective breakdowns and explicit discrepancy JSON. Save original validated report in `submitted_payload` before time normalization. No raw SDK errors, identities or payloads are logged.

## D003 Persistence, replay and chains

- Content creates, immutable test creates and imports allocate stable server UUID-form IDs from operation/actor/idempotency key. They are not secrets. Body digest detects conflicting reuse; no sixth receipt collection.
- Imports store a bounded ID mapping on an anchor atom created atomically with the batch. Dry run uses real validation/handlers but rolls its transaction back. Native fixture import is create-only.
- Anonymous genuine result submissions are independent. A caller supplies a unique key per report; the same key/body replays the prior record rather than adding another.
- Identified test/person/time runs have a deterministic root result ID. Subsequent reports append separately identified results with `previous_id` and `series_id`. `chain_head_id` on the root serializes concurrent updates without adding an event/people/head collection.
- A successor link and chain pointer change only administrative metadata with append-only audit; original text, answers, author, returned/calculated scores and created time remain intact. Native Firestore transactions read shared predecessors/root documents, so two writers cannot fork the chain silently.
- Person ID must be nonblank without leading/trailing whitespace rather than silently trimmed. Identified reports require test_taken_at; normalize UTC occurrence time for matching, separate from received_at. No person ID on tests/selections.
- Root metadata can change after replay (archive/head pointer); replay preserves record identity and result evidence, not byte-identical administrative stamps. Current API is super-admin only, not a participant identity/privacy boundary.
- Product records/receipts remain indefinitely. Archive is availability metadata. Temporary uploads/logs may expire; no product purge API.

## Limits and runtime

- Bounded internal inventory scan: at most 1000 revisions per collection; over-limit returns explicit validation failure rather than sampling a first page. This prototype cap includes history and is advertised by capabilities. Scale/indexed query expansion is deliberate future work; records are not evicted to fit.
- Import: at most 200 records, 256 KiB HTTP body. Stored document canonical UTF-8 representation capped at 768 KiB, leaving database overhead margin. Local same-record rules bound nested arrays.
- List cursors are numeric offsets in the authorized bounded inventory, not stable snapshot cursors; concurrent inventory changes can shift pages. All callers currently have super-admin access. Signed participant cursors/tokens are not part of this product.
- Rate limiter is best-effort per warm process, 180 authenticated requests/minute per remote address; distributed abuse protection is deployment work if public usage warrants it.
- Native Firestore timestamps convert recursively at the store boundary; response/API values are UTC strings. Buffered transactional view performs all SDK reads before flushing writes. Memory tests are not claimed as emulator evidence.
- Development server uses stdlib and explicit ephemeral `--demo`; Firestore mode requires explicit project/installed SDK. No automatic memory fallback in production.
- API key is supplied at runtime/Secret Manager; initial role super admin. On October 29 the owner approved remembering an accepted management key in per-tab sessionStorage across refreshes. Startup revalidates it through the existing API; Disconnect and HTTP 401 remove it. Normal tab close ends its session, subject to browser restore/duplication behavior. No localStorage/cookies or server-auth bypass. Served code contains no embedded key. HTTPS is required outside loopback.
- Deployment packages READY only under a self-contained `.firebase-build/ready` package, excluding env files, virtualenvs and unrelated repo/media. No deployment is performed by the staging script.

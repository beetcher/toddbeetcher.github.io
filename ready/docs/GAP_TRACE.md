# Historical gap trace — current scope

All G01–G25 from the design review are retained. This is requirement traceability, not a claim of runtime implementation. Read BUILD_STATUS.md for verification.

| Gap | Current disposition |
|---|---|
| G01 Unoffered correct answers | Retain set/test consistency requirement. If a service grading method requires all correct choices, all must be present in its frozen offered set. Grading method pending. |
| G02 Alternative versus all-correct | Retain explicit set semantics; formats approved, grading semantics still pending question 10. |
| G03 Browser visitor isolation | Live participant-token design moved to web parking lot. Current requirement is protect super-admin key and authorize management/result reads; no initial granular-role system. |
| G04 Atomic idempotency | Retain for creation/import/test delivery/result recording; redesign receipts for five collections without inventing a live session. |
| G05 Concurrency | Retain real transactions for references/snapshots/result creation/replay; live per-answer append/completion races removed. |
| G06 Availability transitions | Retain published-only selection and reference/version guards across atoms and sets; tests retain frozen material. |
| G07 Formal contracts | Retain five document schemas, operation schemas, OpenAPI and complete fixtures; previous artifacts are not already implemented. |
| G08 Timestamp/version | Retain native conversion/version/precondition decisions and scoped shared-kit adaptation. |
| G09 Output projections | Replace timing-based release matrix with content/management versus delivered-test/result projections. Live release modes parked. |
| G10 Replay/authorization | Retain authorize-first atomic replay contract. Archive-only tests are not deleted; recording delayed results must remain possible. No completion-state replay protocol. |
| G11 Response ordering | Retain explicit test occurrence/order and submission receipt ordering. Incremental participant answer revision/acceptance sequences are caller-web concerns, parked. |
| G12 Caller score freshness | Retain report provenance tied to the submitted result version if corrections are supported; no live evolving score is assumed. |
| G13 Score bounds/rounding | Retain as grading/report contract work after question 10; same denominator does not prove same grading method. |
| G14 Document growth | Retain snapshot/result/import byte budgets and bounded writes; live response/completion reserves no longer required. |
| G15 Query/index | Retain supported query/index plan for five collections, criteria and contextual relationships. Do not use old embedded-on-question relationship assumptions. |
| G16 Random/cursors | Retain bounded whole-pool sampling, explicit cost cap and continuation behavior; shortfall keeps found list per owner. |
| G17 Relationship validation | Retain merged set/pairing validation and immutable test references, not one canonical question mapping. |
| G18 Protected input | Retain allowlisted nested import/assembly/result bodies and server-owned metadata. No generic replacement of immutable test snapshots. |
| G19 Provenance/notes | Retain rich level-specific signal and authorship/source distinction; exact mandatory fields/projections to finalize. |
| G20 Retention/linkage | Distributed tests permanent/archive-only, no test DELETE. Attempt retention/linkage correction separate pending decisions; no profiles. |
| G21 Imports | Retain documented JSON schema, dry-run/atomic commit, reference mapping and replay; web upload/manual entry confirmed. |
| G22 Errors/status/catalog | Retain explicit status/error/permission/schema contracts; update inventory to the current non-administration API. |
| G23 Choices | Preserve authored set/connection identity and rich signal. Pair counts/occurrence IDs are required; subset/shuffle rules not silently assumed. |
| G24 Sequencing | Retain staged content → selection/assembly → tests → returned results → management/demo. No participant player prerequisite. |
| G25 Delivery/documentation | Retain runnable build/deploy/test/rollback artifacts and intent-focused code documentation. |

Foundation proof: schemas/checker, closed request fixtures, preserved handler revisions, duplicate-pair and immutable-test checks. Upcoming proof: cross-record services, real indexed selection, grading/result chains, Firestore concurrency, authenticated HTTP contracts and management UI.

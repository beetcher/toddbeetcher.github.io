# D001 — Schema-first READY foundation

Status: owner decisions consolidated; engineering mechanics explicitly identified below.

Repository source inspected: `finish-now` at `9b0c40505dffd72a90574acb366a183fe5cf8c04` on October 28, 2026. No existing `/ready` or AGENTS.md was present in that tree. Read root CLAUDE.md, schema rules, build method, actual schema kit, venue handler, stores and checker. Shell clone failed because its configured proxy was unavailable; a local source snapshot was obtained with the GitHub connector. This checkout is partial, not a full clone; do not push its local root history over the real repository.

## Owner decisions

- Same repository `/ready`, new Firebase project; initial API key is super admin.
- Five collections; reusable atoms, contextual sets, immutable tests, returned attempts/results. No people or participant-session collection.
- Rich metadata at every meaningful level. Selection criteria are extensible: topic, audience, difficulty, learning objective, tags.
- Content draft/published/retired; new tests use published material. Preserve every version and decommission, never destroy.
- Test edits create another test ID. An archive event changes availability metadata, not test content.
- Test duplicates are configurable pairs, exactly two occurrences each. Two pairs occupy four positions with two unique underlying items. Question-level and identical-set repeats are both allowed; no triplets. Test occurrences have separate IDs.
- Preserve found lists when search is short; offer start over/add/cancel, never silently accept a partial test.
- Optional caller person ID only on result submission. Anonymous reports are distinct; identified reports for the same test/person/test-time form a linked update chain. Retry is not a new report.
- Store returned and calculated scores and discrepancies; strong answer gives full credit, ambiguous-only gives half; preserve ambiguous-choice diagnostics.
- Management UI supports typed content and documented JSON import. Seed: ten questions/four choices each, tagged builder-created validation data.
- All product records/versions retained indefinitely; transient operational data may expire. Participant administration and AI result narration remain parked.

## Engineering decisions in this milestone

1. Give immutable content revisions new UUIDs, preserving `series_id`, `previous_id` and `revision_number` (linked_records). `schema_version` describes shape, never content revision. Archive changes append to lifecycle history on that revision, with an integer record version. A service will select current revisions explicitly, not delete old ones.
2. Rich dimensions use one shared metadata contract embedded identically into every document and nested connection/item where meaningful. Difficulty labels: introductory/basic/intermediate/advanced/expert. Extensions use registered typed `attributes`; unknown names/types are rejected by request validation. Adding an attribute changes contract/docs/UI/filter support explicitly rather than permitting arbitrary Firestore queries.
3. Frozen test items include complete public question/answer content, connection classifications/feedback and metadata, original atom/set IDs and revisions. Internal editorial notes are omitted. Same question appears at most twice; pair count counts repeated question identities, including two versions/sets of that question. This is a documented engineering interpretation of the owner's examples.
4. Store item roles `strong`, `ambiguous`, `incorrect` on set connections. Atom correctness is prohibited. Pure schema constraints stay in JSON; identity uniqueness/set membership and score arithmetic are named handler rules. Multiple strong answers and definitely wrong selections require a documented grading policy before grading service implementation. Foundation schemas do not claim that those remaining edge-case defaults were approved.
5. Use a scoped copy/adaptation of the existing schema kit, with source SHA noted in its header. Remove its unrelated email validator dependency, select READY's explicit schema directory and improve root-level/nested error reporting. Keep the upstream Result contract and validation functions; never modify LAUNCH to make READY pass.
6. Integer versions plus transactions will protect store mutations. The initial memory store is a foundation test adapter, not proof of Firestore concurrency. Real Firestore integration/emulator tests are later milestones. No Firebase project is silently selected.
7. Native JSON import includes atoms and sets, local refs and a dry-run contract. Builder draft list can remain caller-owned; no extra draft-list collection. No live response append or completion-release mode exists.

## Contract error convention

Handlers return existing `Result(ok,data,code,problems)`; problems identify field/issue without values. Endpoint maps to documented HTTP envelopes later. Record `readOnly` is not enough: closed operation input schemas and explicit handler checks reject caller-provided server fields recursively.

## Checkpoint

Do not claim a deployed service, Firestore transaction proof, full REST contract or finished management UI from these foundation checks. See BUILD_STATUS.md.

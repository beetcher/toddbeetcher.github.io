# question schema guide

Collection: `questions`. Decision D001. JSON Schema is the executable field definition; this guide explains intent. All versions retained indefinitely; archive/decommission does not erase content.

## Top-level fields

| Field | Purpose / ownership |
|---|---|
| `id` | Server-owned provenance/identity. |
| `series_id` | Server root identity for a linked revision chain. |
| `previous_id` | Server link to preceding immutable revision, omitted on first revision. |
| `revision_number` | Server content/result revision within the linked chain. |
| `record_version` | Server integer for metadata concurrency; not content or structure revision. |
| `schema_version` | Record structure version, not content revision. |
| `created_at` | Server-owned provenance/identity. |
| `created_by` | Server-owned provenance/identity. |
| `updated_at` | Server-owned provenance/identity. |
| `updated_by` | Server-owned provenance/identity. |
| `source` | Server operational channel; not bibliographic content origin. |
| `is_archived` | Server availability metadata; record content/history preserved. |
| `lifecycle_events` | Append-only archival metadata audit; no destructive deletion. |
| `metadata` | Extensible selection and descriptive signal, typed by shared definition. |
| `origin` | Content authorship/source distinct from the database actor. |
| `status` | Authored availability, separate from archived historical visibility. |
| `question_text` | Authored data; constraints are declared in the schema. |
| `question_type` | Authored data; constraints are declared in the schema. |

## Nested/shared fields

These fields are defined once in the shared contract and embedded identically for local validation; unused definitions do not imply additional collections.

`ambiguous_answer_ids`, `answer_id`, `answer_ids`, `answer_ref`, `answer_revision`, `answer_text`, `answers`, `at`, `attributes`, `audiences`, `author`, `authorship_kind`, `by`, `created_at`, `created_by`, `credit`, `description`, `difficulty`, `feedback`, `grading_label`, `id`, `is_archived`, `is_different`, `item_id`, `learning_objectives`, `lifecycle_events`, `metadata`, `notes`, `origin`, `percentage`, `percentage_point_difference`, `points_difference`, `points_earned`, `points_possible`, `policy_version`, `previous_id`, `question_id`, `question_revision`, `question_text`, `question_type`, `reason`, `record_version`, `revision_number`, `role`, `same_denominator`, `schema_version`, `selected_answer_ids`, `series_id`, `set_id`, `set_revision`, `source`, `source_reference`, `status`, `tags`, `topics`, `updated_at`, `updated_by`.

## Rules and layers

Handler rules enforce same-record identity uniqueness, snapshot/selection consistency and arithmetic. Services verify referenced records, availability, chain-tip/concurrency and grading policy. Handler create rejects read-only caller fields; named test/result constructors accept service-generated fields only in process. HTTP request schemas independently reject nested injection. Archive is a named handler operation; ordinary update creates a linked record instead of overwriting evidence.

## Operational metadata

`successor_id` preserves next-revision linkage and prevents concurrent forks. `operation_key` and `request_digest` support exact retry/conflict checks. `import_receipt` retains `mapping` entries with `client_ref`, `type` and `id`; no extra receipt collection. These fields are server-owned and archived with product evidence.

Snapshot signal: `question_metadata`, `set_metadata`, `answer_metadata`, `question_origin`, `set_origin` and `answer_origin` preserve independent authored context. Public origins omit editorial notes. Effective item `metadata` overlays set values on question defaults for diagnostic grouping.

# Activity event: Programming Guide

For anyone who writes code against `schemas/activity_event.schema.json`: the activity store, the read handler and the Console Activity station. Read `SCHEMA_RULES.md` first. Written October 20, 2026 (thread 21, parking lot P-46).

---

## 1. What it is

The provenance trail for every record in the system. Todd's words (2026-10-15): "the entire point of journaling is to provide proof or provenance. Anytime someone edits one of these records, there needs to be a journal entry created. That's not messages." One entry says: this person (or job) created, edited, deleted or restored this record at this moment, and these fields went from this to that.

It sits beside the other two logs and replaces neither: the message log (`communication_logs`) is what we sent to people; the journal (`journal_events`) is the history of a person's place in a class. The activity log is about records.

## 2. Fields

- `action` (required): `created`, `edited`, `deleted` (soft delete) or `restored` (a soft delete taken back).
- `record_type` (required): the registry's name for the kind of record, such as `venue`.
- `collection` (required): its collection, such as `venues`.
- `record_id` (required): the id of the record that changed.
- `record_label`: a short label (the record's name, title or slug) when it has one that is not personal data.
- `changes`: one item per changed field, each with `field` (the name of a top-level field; a change inside a list or object is shown as a change of the whole field), `old_value` and `new_value` (JSON text; each absent when the field did not exist before or was removed), `values_withheld` (true when the field is personal or sensitive) and `truncated` (true when a long value was cut at 1000 characters). At most 150 items.
- `fields_omitted`: how many changed fields did not fit in `changes`.
- `related_ids`: the record's own id plus the ids it points at (a person, a class, a request, a venue, a place), at most 12. This is how the History button finds entries.
- Server fields: `id`, `schema_version`, `created_at` (when it happened), `created_by` (who did it), `updated_at` and `updated_by` (always equal to the two before: an entry is never updated), `source` (always `system`), `sequence_ms` (the moment in milliseconds, so two changes in one second keep their order).

## 3. Rules the schema cannot say

1. **Append-only and server-written.** The activity store writes an entry in the SAME all-or-nothing step as the change it records, so a change cannot happen without its entry and an entry cannot exist for a change that failed. `create`, `update` and `soft_delete` through the endpoints are refused (`op:not_supported`). Only `get` and `list` work, and only a super admin may read (see the policy table).
2. **One entry per document write.** A service that writes three documents in one transaction leaves three entries, all in that transaction.
3. **Nothing personal is ever copied in.** A field marked `x_pii` in its own schema is recorded as changed, with `values_withheld` and no values. Every field of `individual_restricted_details` is treated that way, and so are a few fields that carry personal text without being marked `x_pii` in their schema: `google_uid` on an access person, `display_name` and `birth_country` on an individual, and `notes` and `organization_name` on a registration request (the list is `WITHHOLD_FIELDS` in `crud/activity_log.py`; marking them in their own schemas would shorten it). So there is nothing to scrub when a person is erased. (Todd decides whether he would rather keep the personal values and scrub them on erase; the default here is never to copy them.)
4. **A change that only touches its own stamps writes nothing.** `updated_at`, `updated_by` and `schema_version` are never listed as changes, and a write that changes nothing else writes no entry. Also quiet: a person's `last_sign_in_at`, the old email status fields of a registration request (`acknowledgment_email_status`, `acknowledgment_email_attempted_at`, `acknowledgment_email_error_code`), and anything written with a bounded timeout.
5. **Which collections are covered.** Every collection the registry names, automatically (a new schema is covered the day it is registered), EXCEPT the ones that are logs themselves or that the server writes constantly: `activity_events`, `communication_logs`, `journal_events`, `discovery_runs`, and the `*_history` collections that hold the old copy of an individual. A write to a name the registry does not know is not logged.
6. **Which door is covered.** Everything that writes through the Console's store: the Console door, the Discovery door and engine, the comms service and the sign-in check. The public registration form writes through its own store and is NOT covered yet (its creates are `web:enjoy`; the completion link edits are `web:completion`). The test door is not covered (it writes test_ collections).
7. A write with no actor stamp is recorded as `system:unattributed`.

## 4. Where the entry gets its facts

- `action`: `created` for a create; `deleted` when the write sets `deleted_at`; `restored` when it removes `deleted_at`; otherwise `edited`.
- `created_by`: the write's own stamp (`created_by` on a create, `deleted_by` on a delete, `updated_by` otherwise).
- `changes`: the stored record before the write, compared with the record after it.
- `related_ids`: the record's own id, plus any of `individual_id`, `scheduled_class_id`, `request_id`, `venue_id`, `location_id`, `attendance_id`, `organization_id`, `curriculum_id`, `contact_individual_id`, `backup_contact_individual_id`, `subject_id` and `participant_individual_ids` that the record holds.

## 5. Reading it

`list` takes ONE filter: `related_ids` (one id: every entry that mentions it), `record_type`, `collection`, `action` or `created_by`. Newest first, at most 200 (default 100). `get` returns one entry by id. The History button on a card uses `related_ids` with the card's record id.

## 6. Open items (parking lot)

- The public registration form's creates and the completion link's edits are not logged yet.
- Entries are listed newest first. Paging: send `before` (the `marker` of the last page, which is the last entry's `sequence_ms`) to get the entries older than it; the reply carries `more` (older entries remain) and `marker`. `before` works only newest first, and the Console asks for 50 at a time.
- Whether personal values should be kept and scrubbed on erase instead of withheld (Todd's call).

# Communication log: Programming Guide

For anyone who writes code against `schemas/communication_log.schema.json`: the CMS (the only writer), the Console Activity tab and the views on attendance and request rows. Read `SCHEMA_RULES.md`, `CMS_GUIDE.md` and `JOURNAL_EVENT_GUIDE.md` (same pattern) first. Written October 15, 2026 (thread 14).

---

## 1. What it is

A log line: one attempt to tell one person one thing, and what came of it. The CMS writes exactly one entry per recipient per call, whatever the outcome, including the ones where nothing was sent. It answers "what did Gladys get?" and "what could not be sent and needs a human?".

The log never stores the message text. The kind, the template version and the facts identify what was sent. The message history on an attendance row or a request card is a view of these entries, selected by `attendance_id` or `request_id`.

## 2. Fields

- `kind` (required): the message kind attempted.
- `template_version`: the version of the template used. Absent when no template was found or the attempt stopped earlier.
- `audience`: the audience label the caller gave.
- `individual_id`: the person told, when the recipient was a known individual. Never changed afterwards, not even when people are merged: a merged person's old id still resolves to the survivor. Receipts to a requester who has no individual record yet carry `request_id` and `to` instead.
- `channel` (required): `email`, `text`, or `none` when no channel could be chosen.
- `to`: where it went (the redirect address when a test redirect was on). Personal data.
- `is_redirected`: true when the test redirect replaced the real address.
- `subject`: the subject as sent. Personal data.
- `status` (required): `sent`, `failed`, `unknown`, `not_sent`, `skipped` (section 3).
- `reason` (required): the closed reason code (section 3).
- `error_code`: a short sanitized code from the adapter or provider, for `failed` and `unknown`. Never a reply text.
- `message_ref`: the Message-ID the CMS put on the email, for matching the provider's delivered, bounced and opened reports later.
- `trigger` (required): `automatic` or `manual`.
- `request_id`, `scheduled_class_id`, `attendance_id`: the records the message belongs to. Optional, not checked. They are fields of their own (not a nested map) so lists can filter on them.
- `dedupe_key`: the key that stops one event being sent twice.
- `contract_version` (required): the version of the CMS call contract.
- `handled_at`, `handled_by`, `handled_note`: set when an operator marks a `not_sent` entry as dealt with. Server only.
- `notes`: operators' comments on the entry, oldest first, up to 50, add only. Each note has `at` (when, UTC), `by` (who, an actor string) and `text` (1 to 1000 characters). A note is never edited or removed; a correction is a new note. Server only, through the add-note operation. Personal data, kept with the entry.
- Server fields: `id`, `schema_version`, `created_at` (for a log entry, when the attempt happened), `created_by` (who caused it: the operator, or `system:` for automatic), `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Status and reason (a closed map)

Each reason belongs to exactly one status; the schema enforces it.

| status | meaning | reasons |
|---|---|---|
| `sent` | the provider accepted it | `ok` |
| `failed` | the provider refused it | `adapter_error` |
| `unknown` | no answer in time; we cannot say | `timeout` |
| `not_sent` | the CMS wanted to send and could not; a person may need to act | `unknown_kind`, `invalid_context`, `no_contact`, `channel_unavailable`, `no_template`, `incomplete`, `time_budget`, `internal_error` |
| `skipped` | the CMS decided not to send; nobody needs to act | `cms_off`, `log_only`, `duplicate`, `excluded`, `muted` |

`internal_error` means a bug inside the CMS was caught: the caller was not hurt, and the entry says so.

`channel_unavailable` covers the rule that a person who prefers text gets no email: the entry is `not_sent` and appears in the hand-contact queue until it is marked handled.

## 4. Rules the schema cannot say

1. Entries are written only by the server (the CMS), not through the endpoints. `create`, `update` and `soft_delete` are refused (`op:not_supported`). Only `get`, `list`, the mark-handled operation and the add-note operation work.
2. `list` takes ONE filter at a time: `individual_id`, `request_id`, `scheduled_class_id`, `attendance_id`, `status` or `kind`, newest first by default.
3. Append-only, with these exceptions: `handled_at`, `handled_by` and `handled_note` are set once by the mark-handled operation, `notes` only grows (the add-note operation, any entry, any status), and provider status may be attached later. The facts of the message are never changed.
4. The log is history. Merging two people, erasing a person, or deleting one never changes, hides or removes a log entry (Todd's rule, 2026-10-15). The only changes an entry ever gets are the add-only `notes`, the one-time mark-handled fields, and a provider status later.
5. A log write failure never undoes anything and never raises into the caller.

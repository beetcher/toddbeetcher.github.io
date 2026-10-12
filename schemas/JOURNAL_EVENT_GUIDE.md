# Journal event: Programming Guide

For anyone who writes code against `schemas/journal_event.schema.json`: the attendance and class services, and the Console Journal lists. Read `SCHEMA_RULES.md` and `ATTENDANCE_GUIDE.md` first. Written October 12, 2026 (thread 13).

---

## 1. What it is

A log line: something happened to a person's place in a class, or to a request's placement, with who did it and when. It exists so nothing drifts away unseen: "this request was placed in this class by this operator on this date", and later "the class was cancelled, so the person was cancelled, so the request went back to unassigned".

The journal is provenance, not truth. Whether a request is assigned is read from the attendance records (see `ATTENDANCE_GUIDE.md`, section 9), never from here.

## 2. Fields

- `event_type` (required): `placed`, `status_changed`, `removed`, `class_cancelled`, `class_removed` or `request_unassigned`.
- `request_id`, `scheduled_class_id`, `individual_id`, `attendance_id`: the records the event concerns, whichever apply. Optional and not checked.
- `role`: the person's role in the class at the time. Optional.
- `from_status`, `to_status`: the attendance status before and after. Optional.
- `note`: free text, personal data. Optional. (The server does not write notes yet; the field is there for operators' notes later.)
- Server fields: `id`, `schema_version`, `created_at` (when it happened), `created_by` (who did it), `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema cannot say

1. **Append-only.** Entries are written only by the server, in the same all-or-nothing step as the change they record. `create`, `update` and `soft_delete` through the endpoints are refused (`op:not_supported`). Only `get` and `list` work.
2. `list` takes ONE filter: `request_id`, `scheduled_class_id`, `individual_id` or `attendance_id`, ordered by time (default newest first). `expand` adds the person's name and the class title.
3. Merging two people repoints `individual_id` on their entries. Erasing a person leaves an anonymous tombstone.

## 4. What writes what

- Placing a person in a class (`assign` or `create` on attendance): `placed`.
- Changing an attendance status: `status_changed` (old and new status).
- Removing an attendance record as a mistake: `removed`.
- A class set to `cancelled`: `class_cancelled` for each person whose open attendance became `cancelled`. A class deleted: `class_removed`.
- Any of the above that leaves a request with no active placement: also `request_unassigned`.

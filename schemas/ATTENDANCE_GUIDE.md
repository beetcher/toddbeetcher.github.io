# Attendance: Programming Guide

For anyone who writes code against `schemas/attendance.schema.json`: the attendance handler and service, the Console class and person cards, and the request-assignment code. Read `SCHEMA_RULES.md`, `INSTRUCTOR_ROSTER_GUIDE.md` and `CURRICULUM_GUIDE.md` first. Written October 11, 2026 (thread 13).

---

## 1. What it is

One person in one class, in one role, and where they stand. This is the record that puts someone in a class, and the most important schema in the class workflow (Todd, October 11). Students and instructors are both attendance records. Assigning a person to a class means creating their record, starting at `assigned`; withdrawing, attending, being late and the rest are later statuses on the same record.

Nothing is stored twice. A class's roster (its instructors and students) is read from the records for that class; a person's history is read from the records for that person. A class does not hold a list of instructors or students.

## 2. Fields

### What the sender provides
- `individual_id`: the person. Required. Never changes once set.
- `scheduled_class_id`: the class. Required. Never changes once set.
- `role`: student, primary_instructor or instructor (a secondary instructor). Required.
- `order`: the place among the instructors (1 first). Optional.
- `status`: assigned, waitlisted, confirmed, attended, late, no_show, declined, withdrawn or cancelled (see section 8). Optional; the server uses assigned.
- `request_id`: the registration request this came from, when it did. Optional and not checked.
- `confirmation_number`: read only. When `request_id` names a registration request that exists, the server copies that request's confirmation number here, so the number follows the person from request to class. Changing `request_id` changes it; removing `request_id` removes it.
- `notes`: operator free text. Personal data. Optional.

### What the server sets (readOnly)
- `status_history`: every status the record has had, oldest first, each with the status, when (`at`) and who (`by`). Added to whenever `status` is set or changed.
- `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (dashboard or import), `deleted_at`, `deleted_by`: the standard fields. Soft delete is for a mistake; a person who leaves is `withdrawn`.

## 3. Rules the schema cannot say (the service enforces them)

The ONLY refusals:
1. The individual exists and is not erased (`individual_id:not_found`); a merged person is followed to the survivor.
2. The class exists and is not deleted (`scheduled_class_id:not_found`).
3. One live record per person per class (`individual_id:duplicate`, with `existing_id` on the problem).
4. `individual_id` and `scheduled_class_id` never change (`immutable`).
5. The schema's own types, values and limits.

Capacity never refuses. A full class simply starts a new student at `waitlisted` (see `assign`). The roles and `order` are not checked against each other.

## 4. The assign step

`assign` is how the Console and request processing put a person in a class: one all-or-nothing action. Give `scheduled_class_id`, `role`, and either `individual_id` (an existing person the operator picked) or `person` (a new person: `given_name`, `family_name`, `email`, `phone`). In the same write it:
1. creates the person, if new;
2. adds the person to the student roster (role student) or the instructor roster (either instructor role), if they are not already on it;
3. creates the attendance record, with `status` as given or, when absent, `assigned` (for a student, `waitlisted` when the class already has as many seat-holding students as its `capacity_max`; a seat is held by every status except waitlisted, declined, withdrawn and cancelled).
The code never matches a typed name to an existing person. A person already in the class is refused as `individual_id:duplicate` with `existing_id`.

## 5. Reading

`get` and `list` accept `expand`: each record then carries `person` (name, email, phone) and `class` (title, start time, status). `list` takes ONE of `scheduled_class_id`, `individual_id` or `request_id`, and may add `status`; `status` alone also works ("all records in this state").

## 6. Merge and erase

Merging two people repoints their attendance to the survivor (a class may then hold two records for one person; unmerge restores). Erasing a person scrubs their attendance records.

## 7. Later

Review and result fields (rating, comments, score, certification) attach to this record. Per-person capacity, per-session grouping and the class counters (registered, waiting, attended) are read from these records, not stored.


## 8. States (changed October 12, 2026: schema version 2)

One `status` line, the same for students and instructors:
- `assigned`: the operator placed them (this was called `enrolled` in version 1).
- `waitlisted`: the class was full when a student was placed.
- `confirmed`: the person said they are coming (set by hand until the communication chain exists).
- `attended`, `late`, `no_show`: the outcome, set after the class. For an instructor, `attended` means they taught it.
- `declined` (the person said no), `withdrawn` (the person left), `cancelled` (the class or the booking was cancelled): the three states that no longer hold a place.

Reviews are NOT a status. A review is its own record, linked to the attendance, so "attended" stays searchable after someone reviews. A status that holds a seat is anything except `waitlisted`, `declined`, `withdrawn` and `cancelled`.

## 9. A request's state is read, never stored

A registration request is **assigned** when at least one live attendance record has its `request_id` and that record is not `declined`, `withdrawn` or `cancelled`. Otherwise it is **unassigned** (waiting to be placed). Nothing is written on the request. When a class is cancelled or deleted, the server sets every person's open attendance in that class (`assigned`, `waitlisted`, `confirmed`) to `cancelled` in the same all-or-nothing step as the class change, so the requests go back to unassigned by themselves. People who already have an outcome (`attended`, `late`, `no_show`) or have already left stay as they are.

## 10. The journal

Every placement, status change, removal and class cancellation or deletion writes a `journal_event` (see `JOURNAL_EVENT_GUIDE.md`) in the same step. When a change leaves a request with no active placement, a `request_unassigned` entry is written too. The journal is provenance; it is never used to decide what is true.

## 11. Changes

Version 2 (2026-10-12): `enrolled` became `assigned`, `confirmed` was added, and the list gained a `status` filter. Only test records existed.

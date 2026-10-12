# Instructor Roster: Programming Guide

For anyone who writes code against `schemas/instructor_roster.schema.json`: the roster handler and service, the Console Instructors station, the merge and erase code. Read `SCHEMA_RULES.md` and `INDIVIDUAL_GUIDE.md` first. Written October 11, 2026 (thread 13).

---

## 1. What it is

One person on the LAUNCH instructor roster. The person is an individual (name, email, phone live in the individual record and are read in, never copied here). This record holds what LAUNCH knows about them as an instructor. Todd's rules: a person is on the roster once; the list is expected to grow more fields over time (add them as optional fields); removing someone keeps the history and they can be added again.

A roster is separate from the student roster. One person can be on both, with one entry on each.

## 2. Fields

### What the sender provides
- `individual_id`: the person. Required. Must exist and not be erased. Never changes once set.
- `status`: active or inactive. Optional; the server sets active when absent.
- `bio`: a short paragraph about the instructor. Optional.
- `capabilities`: short tags for what the instructor can teach or do. Optional list.
- `service_area`: where the instructor will travel, in plain words. Optional.
- `availability`: the weekly hours the instructor can teach, same shape as a venue's `availability_hours` (a `day_of_week`, `opens_at` and `closes_at` per entry). Optional.
- `availability_notes`: anything the weekly hours cannot say. Optional.
- `notes`: operator free text. Personal data. Optional.

### What the server sets (readOnly)
- `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (dashboard or import), `deleted_at`, `deleted_by`: the standard fields. `deleted_at` means the person was removed from the roster; the record stays.

## 3. Rules the schema cannot say (the service enforces them)

These are the ONLY refusals. Nothing else blocks a save.

1. The individual exists and is not erased (`individual_id:not_found`). A merged individual is followed to the survivor.
2. One live entry per individual (`individual_id:duplicate`). A removed entry does not count, so a person can be added again.
3. `individual_id` never changes (`individual_id:immutable`).
4. `availability` entries open before they close (`availability:out_of_range`).
5. `status` is active or inactive, and every limit in the schema holds.

`status` defaults to active on create. Inactive instructors stay on the list and are simply not offered when assigning.

## 4. The one-window flows

- `create_with_person`: add an instructor the way a person says it. Give either `individual_id` (an existing person the operator picked) or `person` (a new person: `given_name`, `family_name` and optionally `email`, `phone`). The person (if new) and the roster entry are saved together or not at all. The code NEVER matches a typed name to an existing person on its own; the operator picks. If the person already has a live entry the answer is `individual_id:duplicate`, and the response carries `existing_id` so the Console can open that card.
- `update_with_person`: save roster fields and the person's name and contact together or not at all.
- `get` and `list` with `expand` return each entry with `person` (id, display_name, email, phone, status) read from the individual. Nothing is stored twice.

## 5. Merge and erase

- Merging two people repoints roster entries from the duplicate to the survivor. If both had an entry, both remain; unmerge restores the original pointers.
- Erasing a person removes their roster entries (soft delete, then everything but the standard fields is scrubbed) in the same write.

## 6. Growth

Add a field by adding an optional property, a line here naming it in backticks, an example, and the Console field. Nothing else changes.

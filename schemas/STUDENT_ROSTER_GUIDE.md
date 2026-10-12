# Student Roster: Programming Guide

For anyone who writes code against `schemas/student_roster.schema.json`: the roster handler and service, the Console Students station, the merge and erase code. Read `SCHEMA_RULES.md`, `INDIVIDUAL_GUIDE.md` and `INSTRUCTOR_ROSTER_GUIDE.md` first (same pattern). Written October 11, 2026 (thread 13).

---

## 1. What it is

One person on the LAUNCH student roster. The person lives in the individual record; this record only says they are a student and holds a status and a note. It is deliberately thin: add optional fields as LAUNCH learns what it needs. A person is on the roster once, and one person can be on both rosters.

## 2. Fields

### What the sender provides
- `individual_id`: the person. Required. Must exist and not be erased. Never changes once set.
- `status`: active or inactive. Optional; the server sets active when absent.
- `notes`: operator free text. Personal data. Optional.

### What the server sets (readOnly)
- `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (dashboard or import), `deleted_at`, `deleted_by`: the standard fields. `deleted_at` means the person was removed from the roster; the record stays.

## 3. Rules the schema cannot say (the service enforces them)

The ONLY refusals:

1. The individual exists and is not erased (`individual_id:not_found`). A merged individual is followed to the survivor.
2. One live entry per individual (`individual_id:duplicate`). A removed entry does not count.
3. `individual_id` never changes (`individual_id:immutable`).
4. `status` is active or inactive, and every limit in the schema holds.

## 4. The one-window flows

Same as the instructor roster: `create_with_person` (existing `individual_id` or a new `person`, saved together or not at all, never auto-matched), `update_with_person`, and `get` / `list` with `expand` returning `person`.

## 5. Merge and erase

Merging repoints entries to the survivor (duplicates may remain; unmerge restores). Erasing a person removes their entries in the same write.

## 6. Later

A requester becomes a student through back-end processing after the hand-built roster works. Not built yet.

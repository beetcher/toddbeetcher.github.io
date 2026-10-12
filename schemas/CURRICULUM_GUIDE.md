# Curriculum: Programming Guide

For anyone who writes code against `schemas/curriculum.schema.json`: the curriculum handler, the Console Curriculum station, and the class code that points at it. Read `SCHEMA_RULES.md` first. Written October 11, 2026 (thread 13).

---

## 1. What it is

What is taught. LAUNCH keeps a small portfolio of curricula (for the pilot, one or two), such as "Introduction to AI Use". A class is a place at a time with one curriculum (`curriculum_id` on the class). Who may teach a curriculum is kept on the instructor roster (`curriculum_ids`), not here.

Todd's rule: each session of a multi-session curriculum is its own class. The curriculum only says how many sessions there are and how long each lasts; classes in one series share a `series_id` and carry a `session_number`.

## 2. Fields

### What the sender provides
- `slug`: short unique identifier (lowercase letters, digits, underscores). Required. Never changes once set.
- `title`: what people see. Required.
- `description`: what it covers. Optional.
- `session_count`: how many sessions. Optional; absent means one session.
- `minutes_per_session`: how long each session lasts. Optional.
- `status`: active or inactive. Optional; the server sets active when absent. Inactive curricula are kept but not offered when building a class.
- `notes`: operator free text. Optional.

### What the server sets (readOnly)
- `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (dashboard or import), `deleted_at`, `deleted_by`: the standard fields. A deleted curriculum stays in the database.

## 3. Rules the schema cannot say (the handler enforces them)

The only refusals:
1. `slug` is unique, counting soft-deleted records (`slug:duplicate`).
2. `slug` never changes (`slug:immutable`).
3. The schema's own types and limits.

Deleting is allowed even when classes point at the curriculum (Todd: no extra rules); set it inactive instead to keep it out of pickers. A class whose curriculum is gone shows it as removed.

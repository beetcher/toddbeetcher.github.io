# Access role: Programming Guide

For anyone who writes code against `schemas/access_role.schema.json`: the access store, the shared authorization check and the Console Access station. Read `ACCESS_GUIDE.md` first. Written October 19, 2026 (thread 18).

---

## 1. What it is

A named bundle of capabilities. Todd is the Super admin; a Region head is meant to manage the venues and instructors of one region and nothing else. Roles are data, so a new bundle is a record, not a deploy. The list of capabilities is fixed and lives in the schema (the `capabilities` enum).

## 2. Fields

- `key` (required): short snake_case name, unique among live records, set once.
- `label` (required): plain-words name in the Console.
- `description`: who the role is for and what it is meant to do.
- `capabilities`: the capabilities the role holds, chosen from the table below, no repeats. Omitted for a super admin.
- `is_super_admin` (required): true means everything, now and for any capability added later, including managing access.
- `is_active` (required): the on/off switch.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. The capability table

Each capability is one thing the server can allow. The server maps every operation on every door to exactly one of these (code, step 3).

| capability | what it allows |
|---|---|
| `view_console` | Open the Console and read the stations the person is allowed to see. Every role needs it. |
| `manage_requests` | Registration requests: view, put in a class, delete a request. |
| `manage_classes` | Scheduled classes and attendance: create, edit, cancel, place people. |
| `manage_curriculums` | Create and edit curriculum records. |
| `manage_instructors` | The instructor roster: add, edit, switch off, add an address through the write-only form. |
| `edit_venues` | Edit venue records (name, contact, hours, rooms, open days) and find GPS. |
| `activate_venues` | Switch a venue on or off, and withdraw Discovery candidates. |
| `edit_people` | The People station (full person records). Todd's super-admin station today. |
| `edit_places` | The Places station (locations and links). Todd's super-admin station today. |
| `view_messages` | Read the Messages station (the send log). |
| `manage_messages` | Edit message wording and settings, add notes, mark handled. |
| `run_discovery` | Start, stop and review Discovery runs (spends money). |
| `edit_discovery_settings` | Discovery models, areas, types, prompt and limits. |
| `view_spend` | Read the Spend tab. |
| `manage_access` | Invite people, change roles, switch access on and off. Only a super admin should hold it. |

Todd may rename or split a capability later; a new one is added to the `capabilities` enum and to this table in the same change.

## 4. Rules the schema cannot say

1. `key` is unique among live records (handler rule) and is not changed after creation.
2. A role with `is_super_admin` false needs at least one capability, and a role with `is_super_admin` true must not list any (it holds them all).
3. A role that any live `access_person` still holds cannot be deleted.
4. The last active role with `is_super_admin` true cannot be switched off or deleted.
5. Strings are trimmed before they are stored.

## 5. Service rules

1. Only a super admin (the `manage_access` capability) may create, change or delete a role.
2. Seed (step 2, the seed script): `super_admin` (all) and `region_head` (`view_console`, `edit_venues`, `activate_venues`, `manage_instructors`, `manage_requests`). Todd edits the Region head bundle in the Console.
3. A role switched off refuses everyone who holds it at their next request.

## 6. Open items

- The final capability list and the Region head bundle (Todd decides; the seed is Claude's first guess).

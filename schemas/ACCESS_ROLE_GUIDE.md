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
| `edit_regions` | Create and edit regions (names and ZIP lists) inside the person's own state. Territorial: only a state grant or a regions grant that lists it. |
| `view_messages` | Read the Messages station (the send log). |
| `manage_messages` | Edit message wording and settings, add notes, mark handled. |
| `run_discovery` | Start, stop and review Discovery runs (spends money). |
| `invite_people` | Invite people into the person's own territory and manage the people they invited (decided 2026-10-20, P-68). Territorial. The people they invite get only regions inside this territory, only capabilities this person holds there (never `invite_people` itself), and only a role that is not a super admin and carries no global capability this person lacks. They see and change only people whose whole territory is inside theirs (or who have none yet and were invited by them), never themselves. |
| `edit_discovery_settings` | Discovery models, areas, types, prompt and limits. |
| `view_spend` | Read the Spend tab. |
| `inspect_everything` | LOOK at everything and change nothing (decided 2026-10-21, P-78). Read access to every station and list, including Activity, Access, Spend, Discovery results and Messages, with private data hidden or masked (see section 5, rule 4). A person whose role holds it is VIEW ONLY: the server refuses every write whatever else the role lists, except starting a Discovery run (capped at 25 cents a run). A sales and demo tool. |
| `manage_access` | Invite people, change roles, switch access on and off. Only a super admin should hold it. |

Territorial or global (decided 2026-10-20): `manage_requests`, `manage_classes`, `manage_instructors`, `edit_venues`, `activate_venues`, `edit_people`, `edit_places`, `edit_regions`, `view_messages`, `manage_messages`, `run_discovery` and `invite_people` apply only inside a person's territory and come from the person's grants (a role's list of these is the default offered when a grant is made). `view_console`, `manage_curriculums`, `edit_discovery_settings`, `view_spend`, `inspect_everything` and `manage_access` are global and come from the role.

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
4. **Inspector (decided 2026-10-21, P-78).** Holding `inspect_everything` makes a person VIEW ONLY at all three doors, whatever else the role lists and whatever territory they hold. The Console CRUD door answers only reads (`get`, `list`, `find_by_address`, `get_for_individual`, `suggest`, `queue`); every other op is refused 403, even if a call is typed by hand. Reads reach every collection the Console door serves (no territory filter); `individual_restricted_details` stays blocked at that door, and Discovery runs are read through the Discovery door. Private data is hidden or masked in what comes back: HIDDEN (the field is removed) notes of every kind, street addresses, birth and death details, restricted details, home addresses (places and links that belong to a person), Google account ids; MASKED (the field shows `(hidden)`) email, phone, backup email and phone, ZIP, a referrer's email, an organizer's email and phone, the address a message was sent to. Names show. Access people's emails show in full. A list filtered on a hidden or masked field is refused (so a value cannot be found by guessing). The Discovery door lets an Inspector use `status`, `quote`, `plan`, `step`, `stop`, `get_run`, `list_runs` and `zips`; `step` and `stop` only on a run the Inspector started; `withdraw` is refused; any quote or plan whose spend cap is over 25 cents is refused (`inspector_cap`). The records door (registration requests) answers with the same hiding and masking. The role may be given only by a super admin; it is seeded as `global_inspector` (label Global Inspector).

## 6. Open items

- The final capability list and the Region head bundle (Todd decides; the seed is Claude's first guess).

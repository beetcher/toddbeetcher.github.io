# Access person: Programming Guide

For anyone who writes code against `schemas/access_person.schema.json`: the access store, the shared authorization check, the seed script and the Console Access station. Read `ACCESS_GUIDE.md` first. Written October 19, 2026 (thread 18).

---

## 1. What it is

One invited Google account and what it may do. The super admin (Todd, `toddbeetcher17@gmail.com`) invites a person by typing their email, picking a role and giving them territory (`grants`). The person then opens the Console and chooses Sign in with Google. If their Google email matches an active record, they are in with exactly that role.

## 2. Fields

- `email` (required): the Google account email, lowercased, unique among live records. Personal data.
- `display_name`: the name shown in the Console. Personal data.
- `role_id` (required): the `access_role` they hold.
- `scope_region_id`: RETIRED. Older records keep it; when a person has no `grants` it counts as one grant for that region with the territorial capabilities the role lists. New records use `grants`.
- `grants`: the territory the person works in and what they may do in each part of it (section 2a). No grants means no territory.
- `individual_id`: optional link to a person record (an instructor who is also a region head).
- `is_active` (required): the on/off switch.
- Server fields: `google_uid` (saved at first sign-in), `last_sign_in_at`, `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 2a. Grants (territory)

Decided by Todd on 2026-10-20. A ZIP is never owned on its own: a ZIP belongs to a region and a region belongs to one state. Regions may share ZIPs. A person holds a list of grants. Each grant has a `kind`:

- `all`: the whole US, every territorial capability. No other grant fields.
- `state`: a whole state (`state_code`): every region in it, every ZIP in it including ZIPs no region has claimed yet, every territorial capability, and the right to invite people inside it (a state administrator). No `capabilities` field.
- `regions`: one or more regions (`region_ids`, all in `state_code`) with exactly the `capabilities` listed. For two regions with different capabilities, write two grants. The Access screen copies capabilities from one region to another as a shortcut; the data stores each grant separately.

`group` is a label the Access screen uses to fold grants together (for example "Wisconsin team"); it gives no rights.

A record is in a person's territory when any one grant covers the record's ZIP; the person may do something to it only when that grant lists the capability (state and all grants list every territorial one; every grant allows looking). The territorial capabilities are `manage_requests`, `manage_classes`, `manage_instructors`, `edit_venues`, `activate_venues`, `edit_people`, `edit_places`, `edit_regions`, `view_messages`, `manage_messages` and `run_discovery`. The others (`view_console`, `manage_curriculums`, `edit_discovery_settings`, `view_spend`, `inspect_everything`, `manage_access`) are global and come from the role. The role's territorial capabilities are only the defaults offered when a grant is made. A record with no ZIP, or a ZIP in no region and no granted state, is outside every grant except `all`.

## 3. Rules the schema cannot say

1. `email` is trimmed and lowercased, and unique among live records (handler rule).
2. `role_id` names an existing, active `access_role` (`role_id:not_found`).
3. `individual_id`, when given, names an existing, non-erased person; `scope_region_id`, when given, names an existing region (`<field>:not_found`).
3a. Each grant (`grants:<problem>`): a `state` grant names a state that has a live state record (`not_found`); a `regions` grant names live regions of kind region whose `state_code` equals the grant's (`not_found`, `wrong_state`) and lists only territorial capabilities (`not_territorial`); the same region appears in at most one `regions` grant of the person (`duplicate_region`); `capabilities` and `region_ids` appear only where the kind allows (`not_allowed`). A person cannot change their own grants.
4. `google_uid` is saved at the first successful sign-in; every later sign-in must present the same Google account, otherwise it is refused. Changing the email of a person who has signed in is refused until a rule for it is agreed with Todd.
5. The last active super admin cannot be switched off or deleted (`is_active:last_super_admin`), and a person cannot change their own role or switch themselves off.
6. Strings are trimmed before they are stored.

## 4. Service rules

1. Only a super admin (the `manage_access` capability) may create, change, switch off or delete a record here. Each is refused to anyone else, whatever the Console shows.
2. An invite creates the record with `is_active` true and no `google_uid`; it works from the person's first Google sign-in. No email is sent by this build.
3. A sign-in is accepted only when Google reports the email as verified and the record and its role are both active.
4. A removed person is switched off and soft deleted, never erased.
5. Seed (step 2, the seed script, run once by Todd): the Super admin person for `toddbeetcher17@gmail.com`.
6. The actor string for a signed-in person is `user:<id>` (SCHEMA_RULES section 5). The Console shows the name, never the id.

## 5. Open items

- Whether to email an invite (not built; the person is simply told).
- What a changed email means for a person who has already signed in (see rule 4).

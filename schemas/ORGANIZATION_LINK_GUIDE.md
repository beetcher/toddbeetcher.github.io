# Organization link: Programming Guide

For anyone who writes code against `schemas/organization_link.schema.json`: the organization link handler, its service, the Console. Read `SCHEMA_RULES.md` and `ORGANIZATION_GUIDE.md` first. Written October 14, 2026 (organizations thread), slice 2. Defaults are Claude's **(proposal)** until Todd confirms.

---

## 1. What it is

One record per connection between a thing (the subject) and an organization. It is the one generic way to hang people, venues and other organizations off an organization, the same way `location_link` hangs things off a location. The organization record stays small; everything that "hangs off" it is a link.

- Ozo's: each shop's venue is the subject with `operated_by`, pointing at the Ozo's organization. A class points at its venue for where; a sponsor is an `organization` subject with `sponsored_by` (or, later, a field on the class), never one of the venues.
- BVSD: a school or the Board of Education is an `organization` subject with `part_of` pointing at BVSD. The superintendent is an `individual` subject with `leads` and a `title`, with dates. Leadership is therefore history, never an overwritten field.

A link says nothing about family and nothing about permission. Being linked to an organization gives no access to anything (that waits for sign-in).

## 2. Fields

### What the sender provides
Required: `subject_type`, `subject_id`, `organization_id`, `relationship`.
- `subject_type`: individual, organization or venue.
- `subject_id`: the id of that individual, organization or venue.
- `organization_id`: the organization it connects to.
- `relationship`: one list for every subject type: works_for, member_of, volunteers_for, teaches_for, leads, contact_for, part_of, affiliated_with, sponsored_by, operated_by, succeeded_by, other. Nothing checks which word fits which subject. **(proposal)**
- `title`: the role, such as Superintendent. Up to 100.
- `description`: a few words. Up to 1000. Personal data possible.
- `valid_from`, `valid_to`: YYYY, YYYY-MM or YYYY-MM-DD. Nothing compares them. A link with a past `valid_to` is simply over; no status is stored.

### Set by the server (readOnly)
`id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules

| Rule | Where |
|---|---|
| Types, formats, lengths, enums, no unknown fields | schema |
| Strings trimmed; blank optional fields left out; server fields refused | handler (`organization_links_crud.py`) |
| `subject_type`, `subject_id`, `organization_id` never change after creation (`immutable`) | handler |
| Subject exists in the right collection and is live (`subject_id:not_found`); a merged individual is followed to the survivor; sealed or erased people are `not_found` | service (`organization_links_service.py`) |
| Organization exists and is live (`organization_id:not_found`) | service |
| An organization is not linked to itself (`organization_id:invalid_value`) | service |

Todd's "no": no overlap rule, no loop rule (a `part_of` cycle is not checked), no primary flag, no word-fit rule, no date-order rule, no delete guard. Deleting a link is always allowed.

## 4. Not built
Merge repoint, erase scrub and privacy hiding for individuals (held, in individuals code). Unlocking `organization` on `location_link`. Class sponsor field. Delete guard on organizations with live links. Console station.

## 5. Operations
create, get, list (any of the filters `subject_id`, `organization_id`, `subject_type`, `relationship`; ordered `-created_at` or `valid_from`), update (title, description, relationship, dates; `expected_updated_at` conflict), soft_delete.

## 6. Files
`schemas/organization_link.schema.json`, this guide, `schemas/examples/organization_link.examples.json`, `enjoy_router/crud/organization_links_crud.py`, `enjoy_router/crud/organization_links_service.py`, `enjoy_router/run_organization_link_tests.py`.

# Location Link: Programming Guide

For anyone who writes code against `schemas/location_link.schema.json`: the link handler and service, the Console, the merge and erase code. Read `SCHEMA_RULES.md` and `LOCATION_GUIDE.md` first. Written October 11, 2026 (thread 13).

---

## 1. What it is

One relationship between a thing and a location, with dates. Todd's rule: a location knows nothing about who lives, owns or operates there; that knowledge is only here. Examples: this individual resides at that location from 2019 to 2024. This venue operates at that location from 2005 on. When a school moves buildings, its old link ends and a new one starts; neither location changes.

One generic record serves every kind of subject (Todd chose this on October 11 over one link type per subject). The subject is named by `subject_type` and `subject_id`.

A link says nothing about family. Two people linked to the same location are not thereby related, and the code must never infer it.

## 2. Fields

### What the sender provides
- `subject_type`: individual, venue or organization. Required. The service checks an organization exists in `organizations` and is live.
- `subject_id`: The id of the subject. Required. A merged individual is followed to the survivor.
- `location_id`: The location. Required, active, and never changes once set.
- `relationship`: resides_at, mailing_address_for, billing_address_for, works_at, operates_at, owns, manages, delivers_to or other. Required, and never changes once set.
- `description`: A few words about this relationship, especially for other.
- `is_primary`: True for the subject's main link of this relationship. Making one primary demotes the previous primary in the same write.
- `valid_from`: First day it applies, YYYY, YYYY-MM or YYYY-MM-DD.
- `valid_to`: Last day it applies. Setting it ends the link; removing it reopens it.
- `verification`: none, self_reported or verified.
- `notes`: Operator free text. Personal data when the subject is a person.

### What the server sets (readOnly)
- `status`: active when there is no `valid_to`, ended when there is.
- `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (dashboard or import), `deleted_at`, `deleted_by`: the standard fields. A soft-deleted link means a mistake was corrected; an ended link means a relationship really ended.

## 3. Rules the schema cannot say (the service enforces them)

1. The subject exists in the right collection (individuals, venues) and is live. An erased, deleted or missing subject is refused. A merged individual is followed to the survivor and the link is made for the survivor.
2. The location exists, is not deleted and is active.
3. `resides_at` is only for an individual; `operates_at` only for a venue or an organization (an organization's factory or headquarters). Other pairs are allowed.
4. `valid_from` is not after `valid_to`.
5. No two live links with the same subject, location and relationship overlap in time. A period is the whole of its year or month: 2020 means 2020-01-01 through 2020-12-31. A missing `valid_from` starts at the beginning of time; a missing `valid_to` never ends.
6. At most one active link per subject and relationship has `is_primary`; making a link primary demotes the other and reports which.
7. `subject_type`, `subject_id`, `location_id` and `relationship` never change. To change them, end the link and make a new one.
8. `status` follows `valid_to` on every write.
9. A location is residential while any active `resides_at` link points at it. The service keeps the location's `is_residential` in step in the same transaction.

## 4. Operations

create; get; list (one of `subject_id`, `location_id`, `subject_type`, `relationship`, `status`; newest first); update (dates, `is_primary`, `description`, `verification`, `notes`, with `expected_updated_at`); end (sets `valid_to`, default today); soft_delete. The location service refuses to retire or delete a location while it has a live link.

## 5. Privacy (proposal)

A residence link reveals where a person lives. Until sign-in roles exist the Console keeps residence links of confidential or sealed people out of lists and `get`, and an erased person's links are soft deleted with `description`, `notes`, `verification` and the dates removed.

## 6. Not here, on purpose

Which seat, room or bed. What the place is like (that is the location). Any family relationship (that is a separate subject).

## 7. Merge and erase

Merging two people re-points every link of the duplicate to the survivor (it is recorded in the merge event, and an unmerge puts back only the links still unchanged). If both people had a link to the same place, the survivor ends up with two; the operator ends or deletes one. Erasing a person scrubs their links and any location nobody else is linked to.

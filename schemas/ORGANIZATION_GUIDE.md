# Organization: Programming Guide

For anyone who writes code against `schemas/organization.schema.json`: the organization handler, the services that link to it, the Console. Read `SCHEMA_RULES.md` first. Written October 14, 2026 (organizations thread). Every default is Claude's **(proposal)** until Todd confirms it. The design comes from Todd's architecture paper (a working draft) and his discussion of Ozo's and BVSD.

---

## 1. What it is

An organization is a persistent organized entity with its own identity: a company, a nonprofit, a school district, a school, a board, a club, a training provider. It exists whether or not LAUNCH, or any product, uses it. The organization is a permanent part of the shared foundation next to `individual` and `location`, so later products can reuse it. LAUNCH starts the collection and uses only a small part of it.

What an organization is **not**:
- Not a location. It has no address field. A place is a `location`; the two are connected by a link. A virtual organization has no location link. Ozo's has five (four shops and a factory). A school district has dozens.
- Not a venue. A venue is a destination with rooms and rules. Ozo's East Pearl shop may be a venue. A class happens at the venue. If Ozo's **sponsors** a class, that points at the organization, never at one of the four venues.
- Not its people. Employees, leadership, board members and volunteers are individuals linked to the organization with a role and dates (a later schema, `organization_link`). Leadership is therefore history, never a field that gets overwritten.
- Not its parent. A school is "part of" a district by a link, so the school keeps its identity if the affiliation changes. A Board of Education is its own organization, part of the district.
- Not a LAUNCH concept. Nothing here knows about workshops, registrations or LAUNCH engagement status.
- Not a kind-specific record. A school's grade levels, a nonprofit's tax status, a business's industry code are separate **profile records** pointing at the organization, added only when a product needs them, so this schema never has to change for them. Nothing like that exists yet.

Names are not identity. Two organizations can share a name. One organization can have many names. A rename never makes a new organization.

## 2. Fields

### What the sender provides
Only `name` is required.
- `name`: What people call the organization. Required, 1 to 200 characters.
- `legal_name`: The registered legal name, when different. Optional.
- `short_name`: A short everyday name such as BVSD. Optional, up to 60.
- `aliases`: Other names, former names, trade names, abbreviations. Up to 20. For search and matching only.
- `kinds`: One or more of business, nonprofit, school, school_district, college_university, government, governing_body, association, club, training_provider, community_group, other. Up to 5, no repeats. A list because kinds overlap. **(proposal)** The vocabulary is deliberately small and can grow.
- `description`: What it is and does. Up to 2000 characters.
- `website_url`: The main web page.
- `email`, `phone`: The organization's public contact, not a person's. Personal data when the organization is a sole proprietor.
- `identifiers`: Outside identifiers, each with a `type` (lowercase, such as `ein`), a `value` and an optional `description`. Up to 20. The EIN goes here as type `ein`; it is not its own field because not every organization has one.
- `founded_date`, `closed_date`: YYYY, YYYY-MM or YYYY-MM-DD. Nothing compares them.
- `status`: active (default when omitted), inactive or closed. The organization's own state in the world. Never its state with LAUNCH. `merged` exists in the list but is set only by a future merge handler.
- `notes`: Operator notes. Personal data possible.

### Set by the server (readOnly)
`id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`, and `merged_into_id` (reserved for a future merge handler; no merge exists).

### Inside each identifier
`type` and `value` are required; `description` is optional.

## 3. Rules and where they live (method section 4.1)

| Kind | Rule | Home |
|---|---|---|
| Schema | Types, formats, lengths, the kinds and status lists, `name` required, no unknown fields | the schema |
| Handler rules block | Normalizers only: trim strings, drop blank aliases, lowercase `email`, tidy `phone` | `organizations_crud.py` (next) |
| Handler refusal | A sender may not set `status` to `merged` or send any readOnly field | `organizations_crud.py` (next) |
| Service | None in slice 1 | |

Decided by Todd (2026-10-14), all "no" for now: no rule that `closed_date` is not before `founded_date`; no delete guard for an organization with live links; no duplicate-name check or warning on create.

Not built, listed so they are not lost: `organization_link` (people, other organizations, venues), the location link for organizations (`location_link` already names `organization` and refuses it), merge and de-duplication, kind profiles, a sponsor field on `scheduled_class`, an existence check on `transaction_record` payer or payee `party_id` when `party_type` is organization, who may administer an organization (membership is not permission; permissions wait for sign-in), and the Console station.

## 4. Test cases that drive the design
- **Ozo's.** One organization (`kinds` business). The East Pearl shop is a venue linked to a location. A class points at the venue for where. A sponsor points at the organization.
- **BVSD.** One organization (`kinds` school_district, government). Schools and the Board of Education (`kinds` governing_body) are organizations linked "part of" it. Employees and leadership are individuals linked with a role and dates. Buildings are locations linked to it. A headquarters is a primary location link.

## 5. Policy
- `x_history`: `in_place` **(proposal)**: the document changes and `updated_at` and `updated_by` say who and when.
- `x_retention`: kept until the owner deletes it; a sole proprietor's contact details are removed on request. A written policy only; nothing enforces it yet. While retention is a written policy only, do not store real personal data beyond what the owner enters.

## 6. Files
`schemas/organization.schema.json`, `schemas/examples/organization.examples.json`, this guide. Collection `organizations`, registered in `schemas/registry.json`. Handler, service and tests come after Todd reviews this schema.

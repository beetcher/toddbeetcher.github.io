# Individual: Programming Guide

For anyone who writes code against `schemas/individual.schema.json`: the endpoints, the dashboard, the registration matcher. Read `SCHEMA_RULES.md` first. Design and research: project doc `individual-schema-research.md`. Accessory schemas: `individual-accessory-schemas.md`. Where a decision is Claude's proposal and not Todd's it is marked **(proposal)**; where nothing is decided it is marked **(open)**.

Written October 10, 2026 (thread 13). Todd chose to have it built without review; every default below is Claude's **(proposal)**.

---

## 1. What an individual is

One human being, independent of any role. Robots and animals get their own schemas. An individual is created by the dashboard, by an import, or by the matcher when a registration arrives. It is never a registration, a customer or a participant: those are roles or events that point at an individual with `individual_id`.

Only things that are intrinsic and stable live here. The boundary rule: a fact stays out if it can have more than one value, changes over time, or depends on context. So addresses, contact points, identifiers, relationships, unions, roles, observations (current height, weight, hair, shoe size), consents, guardianship, credentials, payments and registrations are all other schemas that point at the individual. Sensitive items live in `individual_restricted_detail` (its own guide).

## 2. Fields

### Names (core)
- `given_name`: The first or only name the person goes by in records. Required. Not unique, may be one word, and is never used alone to identify anyone. Other names (legal, former, alias, other scripts) are individual_name records, a later schema.
- `middle_names`: Middle or additional names, free text. Optional.
- `family_name`: Family name. Optional: some people have a single name. Never assume it exists.
- `name_prefix`: Honorific before the name (Dr., Mx.). Optional.
- `name_suffix`: Suffix after the name (Jr., III, PhD). Optional.
- `name_to_use`: What the person asks to be called. When present it overrides given_name in display_name. Optional.
- `name_pronunciation`: How to say the name, plain text or phonetic. Optional.
- `pronouns`: Pronouns as the person states them (for example she/her). Person-stated only, never inferred. Optional.
- `display_name`: The name to show on screens: name_to_use if present, otherwise given_name and family_name. Computed by the server. A label only, never an identity key.

### Record state and privacy
- `status`: Record state: active (default when omitted), inactive (kept, not in pickers), merged (this record was found to be the same person as merged_into_id; every read follows it) or erased (personal data removed; only a tombstone remains). A sender may set only active or inactive; merged and erased are set by the server.
- `merged_into_id`: When status is merged: the id of the individual this record was folded into. All reads follow it. Set by the merge handler.
- `erased_at`: When the personal data was erased (UTC). Set by the erase handler. After this only the id, status, erased_at and server fields remain.
- `record_privacy`: normal (default), confidential (hidden from ordinary lists) or sealed (readable only by an administrator). Optional.
- `identity_verification`: How well this person's identity is established: none (a name and nothing else, such as a walk-in), self_reported (the person told us) or document_verified (an issued document was checked). Matching favors document_verified. Optional; absent means none.
- `retention_class`: Which retention rule applies: active_participant, inactive_3y, financial_7y, minor_review_at_18 or deceased_review. The server sets a default from is_minor and life_status; an operator may override. Optional.
- `is_minor`: Whether the person is under 18. Derived by the server from birth_date and the clock; absent when birth_date is unknown. Stored only as a cache and refreshed nightly. Drives the rules for minors.

### Birth
- `birth_date`: Date of birth as YYYY, YYYY-MM or YYYY-MM-DD, so a partial date is allowed (the length is the precision). Personal data. For a minor, store only the year unless a product needs the full date. Optional.
- `birth_date_certainty`: exact, approximate or estimated. Absent means exact. Optional.
- `birth_date_verification`: none, self (the person said) or document (an issued document was checked). Matching favors document over self. Optional.
- `birth_place_city`: City or town of birth. A place, not an address. Optional.
- `birth_place_region`: State or region of birth. Optional.
- `birth_country`: Country of birth, two capital letters, ISO 3166 (for example US). Optional.
- `multiple_birth_count`: How many were born in the same birth (2 for twins). Absent for a single birth. Twins are never auto-matched as the same person. Optional.
- `multiple_birth_order`: Birth order within the multiple birth, starting at 1. Needs multiple_birth_count. Optional.

### Life status
- `life_status`: alive (default when omitted), deceased, presumed_deceased or unknown. deceased and presumed_deceased require death_evidence. Setting one blocks new registrations, messages and charges and starts the retention clock.
- `death_date`: Date of death as YYYY, YYYY-MM or YYYY-MM-DD. Only with life_status deceased or presumed_deceased. Optional.
- `death_date_certainty`: exact, approximate or estimated. Absent means exact. Optional.
- `death_place_city`: City or town of death. Optional.
- `death_place_region`: State or region of death. Optional.
- `death_country`: Country of death, ISO 3166 two capital letters. Optional.
- `death_evidence`: Basis for the death status: family_report, document, public_record or operator_assertion. Required when life_status is deceased or presumed_deceased. Automated actions need document or public_record.

### Stable physical traits
- `eye_color_left`: Natural color of the left eye: black, blue, brown, gray, green, hazel, maroon, pink, dichromatic or unknown. Different left and right values are valid. Optional. A baby's eye color is not recorded before age 3.
- `eye_color_right`: Natural color of the right eye, same values as eye_color_left. Optional.
- `natural_hair_color`: Natural hair color at maturity: bald, black, blond, brown, gray, red, sandy, white or unknown. Hair as it is now (dyed, cut) is a later observation record. Optional.
- `handedness`: right, left, ambidextrous or unknown. Optional.
- `adult_height_cm`: Height in centimeters, measured once as an adult baseline (50 to 272). Ongoing heights and a child's heights are observation records, a later schema. Optional.

### Language and time
- `preferred_language`: The language to use with this person, a BCP 47 tag such as en or es-MX. All languages and proficiency are language_ability records, a later schema. Optional.
- `time_zone`: The person's IANA time zone such as America/Denver. Optional.
- `requires_interpreter`: Whether the person needs an interpreter. Optional.

### Cross-references
- `external_refs`: Pointers to this person in other systems, such as a payment processor customer id. Government ids never go here. Optional, up to 20.
- `same_as_urls`: Public profile pages the person chose to link. Optional, up to 10.

Inside `external_refs`, each entry has `system` (the other system, lowercase with underscores), `ref` (the id there) and `kind` (optional: customer, member, account).

### Other
- `notes`: Operator notes about the person, free text. Personal data. Optional.

### Server fields (readOnly)
- `id`: UUID v4, set by the server; also the Firestore document id. Never sent by a browser.
- `schema_version`: Version of this schema the record was written under (currently 1). Set by the server.
- `created_at`: When the record was created (UTC, ISO 8601). Set by the server.
- `created_by`: Who created the record. Who acted, as an actor string such as user:<uuid>. Set by the server.
- `updated_at`: When the record last changed (UTC). Set by the server. A change must name the updated_at it read.
- `updated_by`: Who last changed the record. Who acted, as an actor string such as user:<uuid>. Set by the server.
- `source`: Where the record came from: web_enjoy, dashboard or import. Set by the server.
- `deleted_at`: Soft-delete time: the record is kept. Never soft-delete a record that others point at; set it inactive or erase it instead. Set by the server.
- `deleted_by`: Actor who soft-deleted the record. Set by the server.


## 3. Required and optional

A sender must provide only `given_name`. Everything else is optional and is omitted when empty; never store null (SCHEMA_RULES section 3). A mononym is valid: `family_name` is absent. `status` defaults to active and `life_status` to alive when omitted, set by the endpoint. Every enumeration includes `unknown` where it makes sense: absent means never asked, `unknown` means asked and not known.

## 4. Rules the schema enforces

- Any death field (`death_date`, `death_date_certainty`, `death_place_city`, `death_place_region`, `death_country`) requires `life_status` of deceased or presumed_deceased, and those statuses require `death_evidence`.
- `multiple_birth_order` needs `multiple_birth_count`. `birth_date_certainty` and `birth_date_verification` need `birth_date`. `death_date_certainty` needs `death_date`.
- A merged record carries `merged_into_id`; an erased record carries `erased_at`.
- Dates are `YYYY`, `YYYY-MM` or `YYYY-MM-DD`. The length is the precision. A partial date is never compared as if it were exact.

## 5. Rules the endpoint enforces (the schema cannot)

- A real calendar date (no February 30); `birth_date` not in the future; `death_date` not before `birth_date`.
- A sender may set `status` only to active or inactive. `merged` and `erased` come only from the merge and erase handlers.
- `display_name` is computed. `is_minor` is derived and cached, refreshed nightly.
- **Minors**: store the birth year only unless a product needs more; no photo, voice or home address without guardian consent; the guardianship schema (later) is required before a minor is registered. Until it exists, a registration for a minor is flagged, not completed **(proposal)**.
- **Dead**: `life_status` deceased blocks new registrations, messages and charges, and keeps history.
- Updates name the `updated_at` they read and are refused if the record changed. Every update writes a history record (values before and after) to `individual_history` in the same transaction (the `x_history` mode is `history_collection`). The history holds personal data and is erased with the individual.
- Logs record ids and codes, never personal data.

## 6. Identity rules (proposal)

1. A registration is evidence about a person, never the person. The request stores `individual_id` once decided (a later change to the request schema).
2. Never match or merge on email or phone alone: couples and households share both. A name plus birth year is only a candidate.
3. The matcher suggests candidates with evidence; an operator confirms. The only automatic link is a verified identifier match from the same issuer, and none exist yet, so nothing links automatically **(proposal)**.
4. A conflict on a verified identifier from the same issuer is a non-match whatever else agrees. Twins (`multiple_birth_count`) are never auto-linked.
5. A merge is a reversible event: both records are snapshotted, the duplicate gets status merged and `merged_into_id`, linked records are re-pointed, and everything is logged with who decided and why. An unmerge restores the snapshot and keeps later legitimate changes.
6. For each field the merge keeps the better value: verified over self-reported, document over self for birth date, recency last. Deceased status needs authoritative evidence.

## 7. Privacy

Personal fields carry `x_pii`. Public pages never read individuals; the dashboard reads them behind sign-in. `record_privacy` sealed hides a record from everyone but an administrator. Sensitive facts are in `individual_restricted_detail`, written only with a purpose and a consent or lawful basis. Nothing sexual is collected.

## 8. Controlled values

Kept in the schema enums: eye colors (black, blue, brown, gray, green, hazel, maroon, pink, dichromatic, unknown), hair colors (bald, black, blond, brown, gray, red, sandy, white, unknown), life status, status, privacy, retention class, certainty and verification. These follow the common driver licence vocabulary; check them against the AAMVA standard before freezing **(open)**.

## 9. Not here, on purpose

Shoe size, clothing sizes, current hair, weight, photo: changing, so observation records. Marital status and marriage dates: unions. Disability: accessibility and health profiles. Veteran flag: `individual_restricted_detail`. Race and ethnicity: not collected **(proposal)**. Payer and payment: transaction records point at the individual.

# Individual Restricted Detail: Programming Guide

For anyone who writes code against `schemas/individual_restricted_detail.schema.json`. Read `INDIVIDUAL_GUIDE.md` and `SCHEMA_RULES.md` first. Written October 10, 2026 (thread 13). Every default is Claude's **(proposal)**.

---

## 1. What it is

The sensitive, optional facts about one individual, held in a separate record so security rules, exports and erasure can treat them apart. Nothing here is collected by default. It is created only from the dashboard or an import, never by a public page.

## 2. Fields

### Basis (required to write anything)
- `individual_id`: The individual this detail belongs to (a UUID). Required. At most one restricted-detail record per individual (endpoint rule).
- `purpose`: Why these details are held: registration, safety, billing, certification, research or health_care. Required. A field may be written only for a purpose it allows (see x_allowed_purposes on each field).
- `consent_ref`: Reference to the consent record that covers this purpose (a UUID once the consent schema exists). Required unless legal_basis is given.
- `legal_basis`: Another lawful basis when there is no consent: vital_interests, legal_obligation or public_interest. Required unless consent_ref is given.

### Sensitive facts
- `blood_type_abo`: ABO blood group: A, B, AB, O or unknown. Health data. Allowed purposes: safety, health_care.
- `blood_type_rh`: Rh factor: positive, negative or unknown. Health data. Allowed purposes: safety, health_care.
- `skin_tone_scale`: Fitzpatrick skin type: type_1 to type_6 or unknown. Not ethnicity. Allowed purposes: safety, health_care.
- `sex_recorded`: Recorded sex on a source document: female, male, other or unknown. The concept is the recorded sex, not gender identity. Allowed purposes: registration, health_care, certification.
- `gender_identity`: Gender identity as the person states it, free text up to 100 characters. Person-stated only. Allowed purposes: registration, research.
- `sex_for_clinical_use`: Sex parameter for clinical use: female, male, specified, unknown. Health products only. Allowed purposes: health_care.
- `veteran_status`: Whether the person is a military veteran: yes, no or unknown. A cached flag; the military_service schema (later) is the source. Allowed purposes: registration, certification.
- `death_cause`: Cause of death in words. Health data; collected only when a lawful basis exists. Allowed purposes: health_care, research.
- `notes`: Operator notes on these details, free text. Allowed purposes: any.

### Server fields (readOnly)
- `id`: UUID v4, set by the server; also the Firestore document id. Never sent by a browser.
- `schema_version`: Version of this schema the record was written under (currently 1). Set by the server.
- `created_at`: When the record was created (UTC, ISO 8601). Set by the server.
- `created_by`: Who created the record. Who acted, as an actor string such as user:<uuid>. Set by the server.
- `updated_at`: When the record last changed (UTC). Set by the server. A change must name the updated_at it read.
- `updated_by`: Who last changed the record. Who acted, as an actor string such as user:<uuid>. Set by the server.
- `source`: Where the record came from: dashboard or import. Restricted details are never taken from a public page. Set by the server.
- `deleted_at`: Soft-delete time: the record is kept. Never soft-delete a record that others point at; set it inactive or erase it instead. Set by the server.
- `deleted_by`: Actor who soft-deleted the record. Set by the server.

Each sensitive field also carries `x_allowed_purposes`, the purposes it may be held for, and `x_restricted`.

## 3. Rules the schema enforces
- `individual_id` and `purpose` are required.
- Either `consent_ref` or `legal_basis` must be present.

## 4. Rules the endpoint enforces
- One record per individual; the individual must exist and not be erased.
- `purpose` must be in the field's allowed purposes, or the write is refused.
- For a minor, consent comes from a guardian (guardianship schema, later). Until it exists, restricted details for a minor are refused **(proposal)**.
- Reads are limited by role and logged by id. A change names the `updated_at` it read. Every update writes a history record to `individual_restricted_detail_history` in the same transaction. A soft delete (consent withdrawn) keeps the record but stops its use; a new record may then be created for the individual.
- When the individual is erased this record is erased too. When consent is withdrawn the fields it covered are removed.
- Disability and health conditions are not here (later accessibility and health profile schemas). Sexual orientation and anything sexual are collected nowhere.

# Registration Request: Programming Guide

For anyone who writes code against `schemas/registration_request.schema.json`: the endpoint, the web surface, the dashboard, the test scripts. Read this first. The schema says WHAT is allowed. This guide says WHY, and what each field is for, in Todd's intent. Where a decision is Claude's proposal and not Todd's, it is marked **(proposal)**. Where nothing is decided, it is marked **(open)**.

Companion files: `schemas/SCHEMA_RULES.md` (naming and data rules for every schema), `schemas/SCHEDULED_CLASS_GUIDE.md` (the class a request points at), `schemas/registry.json` (type to collection map).

Written October 6, 2026, from the registration design conversation (thread 11, I Can Do That /enjoy site).

---

## 1. What a registration request is

- It is a **request**, not a registration. Someone is asking to take part. Being "registered" is a later fact, decided by processing.
- It is **unfiltered**: whatever a visitor submits, once valid, is stored as received. No judgment is applied at creation.
- The job of the web surface is to produce a clean registration request and send it to **our own endpoint**. Everything after that (follow-up email, scheduling, payment, confirmation that a seat is held) is a separate workflow and not part of this schema's creation step.
- On success the visitor gets a **confirmation number**. The message must say a request was received, never "you are registered."
- Todd: "A request has been made. That doesn't mean they're registered."

## 2. How the pieces fit

1. The visitor chooses a type (private, group, class), fills in fields, and the page validates them field by field, for the visitor's benefit.
2. The page sends one JSON document to the **create endpoint**. It never writes to Firestore directly. (Today's older sign-up form does write directly; that is the pattern being replaced.)
3. The endpoint validates against the schema, adds the server fields, stores one document in the `registration_requests` collection, and replies with the confirmation number.
4. A dashboard, built separately, reads and processes requests later.

Principles:
- **The schema is the handshake** between web, endpoint and dashboard. One file, one definition.
- **The server is the only authority.** Browser validation is courtesy. The endpoint re-checks everything.
- **Creates only from the web.** A submit always creates a new record. Updates come later from server handlers, never a public page.
- **One schema, three types.** There is a `registration_type` field (`private`, `group`, `class`). Which other fields apply depends on the type. There are not three schemas. (Todd, after considering separate schemas: it is one schema with fields dependent on the type.)
- **Schema design is separate from interface design.** The schema lists everything that could be collected. The web surface may ask for only some of it. Todd: "don't conflate schema architecture with web surface design."
- Firestore security rules deny all web reads and writes. The deployed rules must be verified, not only the rules file.

## 3. The three types

All three share the requester, contact, consent, attendee count, minors flag, AI background, notes and the server fields. They differ as follows.

**Private.** Todd: a private session can be one person, a couple or a family. It is "a family or a couple." Requires a duration and a location type. Date and time preferences, a venue arrangement and a series count are optional.

**Group.** "An extension of a private with a network of people that may or may not be affiliated, like at the family level." The requester is the group leader. Same fields and rules as private, plus an optional `group_type` (family, friends, colleagues, club or nonprofit, other). Names of the other people are optional because a leader may only know a headcount at first. Individual AI levels are deliberately NOT collected here (see section 5, "Who is attending").

**Class.** A class request picks a scheduled class from a list: a public, enrolling class of type workshop (private and group classes are created later by processing and are never in the list). A scheduled class is a scheduled event. A class request does exactly one of:
- **Picks a scheduled class** (`scheduled_class_id`, a UUID of a class record). Location, date and time come from the class, so the request does not carry duration or location type.
- **Says none fit** (`no_class_fits` = true). This means "I would like to be part of a class; none of yours work; tell me when one is available." Location and timing preferences matter most here, because enough of them can justify building a new class. This is a demand signal.

A class request can bring others: "I've got three more people." Same `participants` and `attendee_count` as other types.

**Class capacity logic (Todd's decisions).** A class has three numbers: a minimum to run, a target ("we'll take it to 10") and an absolute maximum ("we'll go as high as 15"). The range between target and maximum is overflow.
- The check at submit compares `attendee_count` with the class's **maximum capacity**. If the count exceeds it, refuse with `over_capacity`. Registered people are not subtracted: a request is not a registration and no seat is held. A class that is at its maximum still accepts a request.
- Only a class in status `enrolling` accepts requests. Any other status gives `class_closed`.
- At the moment of submit the server **reads the class record itself** (never trusts the list the browser saw, which could be minutes old) and stores a snapshot on the request: `class_capacity_target_at_request`, `class_capacity_max_at_request`, `class_registered_at_request`, and `seats_available_at_request` (maximum minus registered, never below zero). Todd: it will show "we had a fully booked class, we accepted another one," and may be useful later.
- Processing, not this endpoint, later decides whether a request is accepted, accepted into overflow, or waitlisted.
- The class list endpoint returns each public enrolling class with capacity numbers and registered count for display.
- The class schema now exists: `schemas/scheduled_class.schema.json`, with its own guide `SCHEDULED_CLASS_GUIDE.md`.

## 4. Rules the schema enforces itself

- All field names are snake_case. Unknown fields are rejected.
- Required for every request: `registration_type`, `idempotency_key`, `attendee_count` (1 to 50), `first_name`, `last_name`, `email`, `consent_to_contact` (must be true), `presented_cost_cents`, `presented_cost_basis`, `is_requester_attending`, `has_minors_present`.
- Private and group require `duration_minutes_requested` and `location_type`, and forbid `scheduled_class_id` and `no_class_fits`.
- Class requires exactly one of `scheduled_class_id` or `no_class_fits`, and forbids `duration_minutes_requested`, `location_type`, `venue_arrangement`, `sessions_requested` and `group_type`.
- `group_type` is allowed only on group requests.
- If `is_requester_attending` is false, `participants` must be present with at least one person (for example a gift recipient).
- If any participant has `age_band` child or teen, `has_minors_present` must be true.
- `no_class_fits` can only be sent as true. Omit it otherwise.
- Fields marked `readOnly` are set by the server only. A submission containing one is rejected (the endpoint enforces this; JSON Schema itself only annotates it).

## 5. Field intent

Each field below says what it is for. Todd's own words are quoted where they exist.

### Who is asking (the requester)
- `first_name`, `last_name`, `email`, `phone`, `street_address`: the person making the request. "There should be a requester, but there might not be the same person as who's joining." Email is trimmed and lowercased by the server. Street address matters mainly when the session is at their home.
- `requester_age_band`: child, teen or adult, optional.
- `preferred_contact_method`: email or phone.
- `consent_to_contact`: required and always true. The next step is us contacting them.

### Who referred them
- `referrer_first_name`, `referrer_last_name`, `referrer_email`: the person who referred them. Optional. The email belongs to a third party, so treat it as personal data and do not contact that person without their say-so **(proposal)**.

### What they were shown
- `presented_cost_cents` and `presented_cost_basis`: the price shown to them when they engaged, in US cents, and what it covers. `per_session` means the whole session (private and group are a flat session price); `per_person` means each attendee (a class seat). Both required, because with a headcount on every request the number alone cannot be read. Whether the server compares it with its own price list is **(open)**; a browser value can be altered.
- `duration_minutes_requested`: requested length, private and group only. Today's site says about 2 hours.

### Where they are with AI (requester only)
- `has_downloaded_ai_app`, `has_used_ai_online`, `proficiency` (1 to 10), `favorite_ai`, `ai_name` (what they call or would call their AI), `has_paid_ai_account`, `devices` (iphone, android_phone, tablet, windows_laptop, mac_laptop, other).
- Todd wanted this light: "I don't want to make this a super rich thing, maybe some yes or no's." Collected only for the requester. Each participant's level is collected later, after they are invited, through a separate surface linked back to the request. "You're not going to have somebody fill out all this on a web surface about all the different people." That later record is out of scope here. (The scale 1 to 10 differs from the older form's 1 to 5; **open** whether to unify.)

### Who is attending
- `is_requester_attending`: required. False for a gift or when someone is arranging for others.
- `participants`: everyone else being trained, up to 50. Each has a `first_name` or a `last_name` (at least one; Todd: "one or the other is good enough"), optional `email`, optional `age_band`. The requester still gives both names. For a gift, the recipient is a participant. For a couple, the spouse.
- `attendee_count`: the TOTAL number of people wanting seats, including the requester if attending. Required on every type (even a private session can be two or three). Names are optional, so the count can exceed the names. Endpoint rule: names given (plus the requester if attending) must not exceed the count.
- `has_minors_present`: required, true or false. Todd: "you need to know if someone's going to bring a kid on site. It's a vital piece of information for use later."
- `age_band` on requester and participants: in the schema on purpose. The web surface need not ask for it. Todd's policy on whether minors may attend at all is **(open)**; if they do, an adult should be the requester.
- `is_gift`: true when the request is a gift. The recipient is a participant, so no separate recipient fields exist.

### When and where (private and group)
- `requested_date`, `alternate_requested_date`, `requested_time_of_day` (morning, afternoon, evening), `preferred_times` (free text for anything else). Optional, because someone may be flexible. For a "none fit" class request these act as a demand signal.
- `location_type`: `home` or `off_site`. Required for private and group.
- `preferred_location`: where, in their words. Used by private, group and class ("none fit").
- `venue_arrangement`: `we_have_space` or `need_suggestion`. Who arranges the space.
- `sessions_requested`: 1 to 52, for a series. Optional.

### Organization and billing
- `organization_name`: a club, company, church, nonprofit. Optional, any type.
- `group_type`: group only (see section 3).
- `needs_invoice`: organizations often need an invoice or purchase order rather than a card.

### Class selection
- `scheduled_class_id`, `no_class_fits`: see section 3.

### Other
- `what_they_want`: the old form's "what would you love to do with it." Todd's best signal about what a person cares about.
- `how_heard`, `notes`.
- `promotion_code`: an optional code carried in from a promotion link, so promotions can be measured against requests. Matches a promotion record's code.
- `idempotency_key`: a UUID the browser creates once per submission. If the same key arrives twice (double tap, retry), return the original result and create nothing.

### Set by the server only (readOnly)
- Identity and provenance: `id` (UUID v4; also the Firestore document id), `schema_version` (2), `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (web_enjoy, dashboard, import), `program_slug` (which program, such as `launch`; set from where the request came in), `previous_id`, `deleted_at`, `deleted_by`. Actors look like `web:enjoy`, `system:<handler>`, `user:<uuid>`.
- `confirmation_number`: shown to the visitor. Format is **(open)**; make it readable and not guessable.
- Processing: `processing_status` (`not_processed`, `partially_processed`, `processed`; always `not_processed` at creation) and `processed_at`. Todd: "you have to keep track of the status of that processing."
- Payment: none. A request carries no payment fields. `is_paid`, `payment_source` and `payment_id` were removed in schema version 2; payments are transaction records (`TRANSACTION_RECORD_GUIDE.md`) whose ids are held by the registration assignment. **Never store card or other payment details.** Whether payment happens at registration at all is not decided; "I could see somebody providing payment" eventually, through a third party.
- Class snapshot: `class_capacity_target_at_request`, `class_capacity_max_at_request`, `class_registered_at_request`, `seats_available_at_request`: present only when a class was picked, absent otherwise.

## 6. What the endpoint must do

1. **Honeypot first.** Remove the hidden field `website` before anything else. If it held anything, reply as if the request succeeded and store nothing. (It is not in the schema, which rejects unknown fields, so it must be removed before validating.)
2. Reject any submission containing a readOnly field.
3. Normalize the email (trim, lowercase) so validation and matching see the clean value. Do this before validating, or surrounding spaces would fail the email format.
4. Validate against the schema. Reply with the standard envelope (SCHEMA_RULES section 8): `ok`, then `data` or `error` with a `code` and field-level errors. Codes: `validation_failed`, `over_capacity`, `class_not_found`, `class_closed`, `rate_limited`, `not_found`, `server_error`.
5. Honor the idempotency key: the same key twice returns the original success and creates nothing. This is not an error.
6. Dates: `requested_date` and `alternate_requested_date` must not be in the past (Mountain time). Otherwise `validation_failed` with a field error.
7. Names versus count: the names in `participants`, plus the requester if attending, must not exceed `attendee_count`.
8. For a class pick: load the class. Not found, or a class that is not a public workshop, gives `class_not_found`. A status other than `enrolling` gives `class_closed`. A count over `capacity_max` gives `over_capacity`. Otherwise store the four-field seat snapshot. A class at its maximum still accepts the request.
9. **Repeats are flagged, never blocked.** Look for an earlier request with the same normalized email and the same type. If one exists, save the new request as a new record with `previous_id` pointing at the earlier one, and reply with a normal success. Because it is only a flag, a false match (a couple sharing one email) does no harm. Repeats are not errors.
10. Generate `id`, `program_slug` (`launch` for the /enjoy pages), timestamps, `created_by` and `updated_by` (`web:enjoy`), `source` (`web_enjoy`), `schema_version`, `confirmation_number`, `processing_status` = `not_processed`.
11. Check the full record against the schema and confirm every `x_server_required` field is present.
12. Store one document. Reply with `confirmation_number` and `registration_type` and nothing else. The wording shown to the visitor says a request was received, never that they are registered.
13. Protect the public form: rate limit per visitor, Firebase App Check once live. Never put personal data in logs; log ids and codes.
14. **People other than the requester.** Referrer, participant and minor details are stored as given but are not used to contact anyone without the requester's say-so. Collect the minimum. Wording on the web surface should make the requester responsible for having permission to share them.

## 7. Not in this guide's scope

The web surface design (the steering pop-up, wording, which optional fields to ask). The class list endpoint. Processing workflow and follow-up email. Payment processing. The dashboard. The invite surface where participants give their own AI details. Retention.

## 8. Decisions so far

Todd's decisions: one schema with a type field; the request/registration distinction; direct Firestore calls replaced by our own endpoint; creates only from the web, repeats flagged not blocked; snake_case; plural collections; UUID ids; snapshot of class seats at submit; total capacity as the threshold; headcount on all types; `has_minors_present` and `age_band` in the schema; AI level for participants collected later.

Claude's proposals not yet confirmed by Todd: `presented_cost_basis` (per_session or per_person), the honeypot field name `website`, the error code list, the past-date rule, the handling of third-party details, the exact names of the processing statuses, the confirmation-number approach, the idempotency key, the read-only marking, `venue_arrangement`, `sessions_requested`, `needs_invoice`, `how_heard`, `preferred_contact_method`, the 1 to 50 attendee ceiling, the repeat-matching rule (email plus type), and the third-party referrer handling.

## 9. Open items

- Retention period for personal data (`x_retention` is "undecided"; required before launch).
- Whether minors may attend, and any age rule.
- Server price check versus `presented_cost_cents` (the basis is now recorded, but whether the server verifies the amount is not decided).
- Confirmation number format.
- Scale for proficiency (1 to 10 versus the old 1 to 5).
- Boolean naming: the rules say `is_`, the schema also uses `has_` and `consent_to_contact`; amend the rules.
- Where the endpoint lives (the existing project is a test project) and its language.
- The class list endpoint, and the instructor, review, attendance and promotion schemas the class points to (the venue schema is written; see `VENUE_GUIDE.md`).
- Whether the old direct-write sign-up (`enjoy_signups`) is retired when the web surface switches.
- Confirm Firestore rules are deployed, and that `/schemas/` serves as static files on Cloudflare Pages.

## 10. Reuse

Todd: this registration could serve other programs. Roundup (the live in-room event at `/mentor`) has a Join page and a Register Now link but no registration backend. **(proposal)** The pattern carries over: the same envelope (requester, contact, consent, attendee count, minors flag, status, payment, provenance) with a program or type field. A new program adds its own `registration_type` values or a sibling schema that follows `SCHEMA_RULES.md`. Do not fork the endpoint pattern.

## 11. Examples and checks

- `schemas/examples/registration_request.examples.json` holds five valid example requests (private couple, private gift, group with an organization, class with a pick, class where none fit) and ten invalid ones, each named for what is wrong. Use them as the seed for the test-records file and as the first tests for the endpoint.
- `schemas/examples/registration_request.test_records.json` holds 30 ordered test records for the endpoint: happy paths for every type, repeats and idempotent replay, schema rejections, and endpoint rules (capacity, class not found or closed, names over the count, past dates, honeypot, email cleaning). Each says the request to send and the outcome to expect. Its seed list of scheduled classes follows the scheduled-class schema and is checked against it.
- `python3 schemas/check.py` verifies the schema, this guide, the examples and the test records agree: valid schema, snake_case names, every field mentioned here, valid examples pass, invalid examples fail, and the test records behave as labelled. Run it before checkpointing any schema change. It needs `pip install jsonschema`.

## 12. Build order (Todd's workflow)

1. Schema (done, one file) and this guide.
2. A file of test records: good ones for each type, and deliberately broken ones. Use the test-records file (section 11).
3. The endpoint, tested first with the local Firebase emulator, then deployed to a proper project.
4. A script that sends the test records to the endpoint and confirms documents land correctly in the collection (including repeat flagging, idempotency, rejected read-only fields, and a refused direct browser write).
5. The web surface, last.

## 13. Where a request goes next (2026-10-08)

A request is decided by a registration assignment (`REGISTRATION_ASSIGNMENT_GUIDE.md`). For a private or group request, processing creates a scheduled class of that type (with `source_request_id` pointing back) and assigns the party to it. For a class request, processing assigns the party to the workshop they picked, or later offers one if none fit. The request itself does not change except for its processing status.

## 14. Changes in version 2 (2026-10-08)

`is_paid`, `payment_source` and `payment_id` were removed from the request, because payments are now separate transaction records. Removing fields is a breaking change, so `schema_version` moved from 1 to 2. No stored records existed yet.

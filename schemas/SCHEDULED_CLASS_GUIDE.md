# Scheduled Class: Programming Guide

For anyone who writes code against `schemas/scheduled_class.schema.json`: the dashboard, the endpoints, the class list the registration page reads. Read `SCHEMA_RULES.md` first (conventions for every schema) and `REGISTRATION_REQUEST_GUIDE.md` (requests point at classes). Where a decision is Claude's proposal and not Todd's it is marked **(proposal)**; where nothing is decided it is marked **(open)**.

Written October 6, 2026 from the class design conversation (thread 11).

---

## 1. What a scheduled class is

A workshop that people can ask to join. A class is created by the organizer (Todd) from the dashboard, never by a public page. It may exist long before it has a date: a class can begin as an idea built from demand (people who said "none of your classes fit").

The class record stays light. It holds **references** (venue, instructors, promotions) and **summary numbers** (registered, waitlist, attended, reviews). The bigger things are their own collections, each with its own schema: venues (written, see `VENUE_GUIDE.md`) and, not yet written, instructors (identities and contact details live in a person schema), reviews, attendance and promotions.

Registration requests point at a class with `scheduled_class_id`. The class does not store its requests; "all requests for this class" is a lookup.

## 2. Status: the life of a class

`status`, in order: `identified` (an idea, no date), `scheduled` (date and venue set), `enrolling` (taking registration requests), `completed`, and `cancelled` (**proposal**: Todd named the first four).

- Only a class in `enrolling` accepts registration requests. Any other status gives the `class_closed` error. This replaces a separate "open for requests" flag.
- The schema requires `starts_at`, `time_zone`, `duration_minutes`, `venue_id` and `is_venue_confirmed` once a class is `scheduled`, `enrolling` or `completed`. It requires `price_cents` and `price_basis` once `enrolling` or `completed`.
- `cancelled_reason`: optional free text for a cancelled class.

## 3. Fields

### The class itself
- `title`, `slug` (lowercase letters, digits and underscores; unique; never changes), `description`.
- `is_public`: whether the class appears in the public list. A private class can still take requests by direct link **(proposal)**.

### When
- `starts_at` (UTC), `time_zone` (an IANA name such as `America/Denver`), `duration_minutes`. Empty while a class is only an idea.

### Where
- `venue_id`: the UUID of a venue record. The venue record (`schemas/venue.schema.json`, `VENUE_GUIDE.md`) holds the address, the venue contact, the backup contact, its rooms, and standing details such as parking and the physical accessibility facts. Todd: venue contact details and a backup contact exist; they belong with the venue so every class there reuses them **(proposal, confirmed in discussion)**.
- `venue_room_label`: the label of a room in that venue's `rooms` list (Todd: the class points at the venue plus a room label). The room must exist, and `capacity_max` should not be above its `max_occupancy`.
- `is_venue_confirmed`: venue chosen versus venue confirmed.
- `venue_notes`: anything specific to this class at this venue (for example, "use the side entrance"). Not for standing venue details.
- `accessibility_notes`: anything about accessibility specific to this class **(proposal)**. The physical facts live on the venue record. Use the words "accessible" and "accessibility" in field names and visitor wording.

### Who runs it
- `instructor_ids`: a list of UUIDs of instructor identities. Contact details live in the other schema. One class, many instructors (up to 10).
- `organizer_name`, `organizer_email`, `organizer_phone`: the class organizer's contact, "probably me." Later this could point to a person or role record instead.

### Attendance and capacity (Todd's design)
- `capacity_minimum`: how many must be registered for the class to run.
- `capacity_target`: the number planned for ("we'll take it to 10").
- `capacity_max`: the absolute ceiling ("but we'll go as high as 15").
- Overflow is the range from target to maximum. There is no separate overflow flag, because it would only repeat the two numbers and could contradict them **(proposal)**.
- Endpoint rule: `capacity_minimum` <= `capacity_target` <= `capacity_max`. JSON Schema cannot compare fields.
- `is_waitlist_enabled`, `waitlist_max`: whether the class keeps a waiting list and how long it may grow.
- A waitlisted person is still a registration request. Processing decides whether a request is accepted, accepted into overflow, or waitlisted; the class only keeps the counts **(proposal)**.

**How requests use the capacity.** The registration endpoint refuses a request only when its `attendee_count` is over `capacity_max`. A request is not a registration, so no seat is held. At submit the server reads this class record itself and stores a snapshot on the request (target, maximum, registered, and seats available up to the maximum).

### Price
- `price_cents`, `price_basis` (`per_session` or `per_person`): what the class costs and what that covers, so the price shown on a request can be compared with it. USD cents.

### Promotion
- `promotion_ids`: UUIDs of promotion records (channel, link, cost), so success can be measured. The request carries an optional `promotion_code` carried in from the link.

### Set by the server only (readOnly)
- Identity and provenance: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (`dashboard` or `import`), `previous_id` (a rescheduled class can point at the one it replaces), `deleted_at`, `deleted_by`.
- Summary numbers, kept current by processing: `registered_count`, `waitlist_count`, `attended_count` (from the attendance collection), `review_count` and `average_rating` (from the reviews collection, 1 to 5).
- `x_server_required` in the schema lists the readOnly fields every stored class must have. `average_rating` is absent until a first review exists.

## 4. What the endpoints must do

1. Class creation and changes come only from the dashboard, never a public page. Reject any readOnly field sent.
2. Validate against the schema, then check `capacity_minimum` <= `capacity_target` <= `capacity_max`.
3. Set provenance and start the summary numbers at zero.
4. A class list endpoint for the registration page returns only public classes in `enrolling`, with the fields a visitor needs (never organizer phone or email). It is read-only and rate limited.
5. Keep `registered_count` and `waitlist_count` correct as requests are processed, `attended_count` from attendance, and `review_count` and `average_rating` from reviews.

## 5. Open items

- The instructor (person), review, attendance and promotion schemas (the venue schema is written).
- Retention (`x_retention` is "undecided").
- Which fields the public class list may expose.
- Whether a private class (`is_public` false) is reachable by a direct link.
- The attendance app Todd described for checking people in.

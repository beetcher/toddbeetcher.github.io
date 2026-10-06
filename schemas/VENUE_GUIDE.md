# Venue: Programming Guide

For anyone who writes code against `schemas/venue.schema.json`: the dashboard, the endpoints, the class list the registration page reads. Read `SCHEMA_RULES.md` first (conventions for every schema) and `SCHEDULED_CLASS_GUIDE.md` (classes point at venues). Where a decision is Claude's proposal and not Todd's it is marked **(proposal)**; where nothing is decided it is marked **(open)**.

Written October 6, 2026 from the venue design conversation (thread 11).

---

## 1. What a venue is

A place where classes are held. A venue is created from the dashboard, never by a public page. A venue record can begin as an idea (a cafe someone mentioned) and be filled in as it is vetted.

A venue holds where it is, how to get in, who to contact, its rooms, its accessibility, its house rules, when it is available and what it costs. A `scheduled_class` points at a venue with `venue_id` and names the room with `venue_room_label`. The venue does not store its classes; "all classes at this venue" is a lookup.

**Rooms live inside the venue record** (Todd): a room has no life apart from its venue. **Reviews live outside** (Todd): each review is its own record with a pointer back to the thing reviewed. The venue holds only the server-kept `review_count` and `average_rating`.

## 2. Status

`status` is `active` or `inactive` **(proposal)**. Inactive means not usable (an idea, a retired venue) and keeps a venue out of the picker without deleting it.

An `active` venue must have: `street_address`, `city`, `state_region`, `postal_code`, `country`, `time_zone`, `contact_name`, at least one of `contact_email` or `contact_phone`, at least one entry in `rooms`, and answers to `is_accessible`, `allows_minors` and `allows_animals`. An inactive venue needs only `name`, `slug`, `status` and `is_public_venue`.

## 3. Fields

### The venue itself
- `name`, `slug` (lowercase letters, digits and underscores; unique; never changes), `description`.
- `is_public_venue` (Todd): a public venue (library, cafe, hall) versus a private one (a home, an office). Not the same as a class's `is_public`, which is whether the class is listed.

### Where
- `street_address`, `address_line_2`, `city`, `state_region`, `postal_code`, `country` (two capital letters, ISO 3166, for example `US`). `street_address` and `address_line_2` are personal data when the venue is a private home (`x_pii`).
- `time_zone`: an IANA name such as `America/Denver`. A class at this venue takes its `time_zone` from here **(proposal)**.
- `latitude`, `longitude` (Todd): the GPS point of the venue. Each requires the other.

### How to get in (Todd)
- `parking_description`, `parking_latitude`, `parking_longitude`: where to park, in words or GPS or both.
- `entry_description`, `entry_latitude`, `entry_longitude`: the door to use, in words or GPS or both.
- `transit_description`: how to arrive by bus or train **(proposal)**.
- `location_pin_ids`: UUIDs of `location_pin` records. A pin is a precise spot inside a venue (a picture, a verbal description and GPS), a schema still to be written. Todd called these "CAN pins" and said they come later; the venue only keeps the place to point at them.
- Each GPS pair needs both numbers: `parking_latitude` with `parking_longitude`, `entry_latitude` with `entry_longitude`.

### Who to contact
- `contact_name`, `contact_email`, `contact_phone` (Todd): the venue contact.
- `backup_contact_name`, `backup_contact_email`, `backup_contact_phone`: the backup contact. All are personal data (`x_pii`).
- `website_url` **(proposal)**.
- `booking_process`, `booking_lead_days` **(proposal)**: how to book the space and how much notice it needs.

### Rooms (Todd; inside the record)
`rooms` is a list. Each room has:
- `label` (required): the room name, such as "Main room". Unique within the venue. A class names it with `venue_room_label`.
- `max_occupancy` (required) and `preferred_occupancy` (Todd: "preferred occupancy, maximum occupancy"). Preferred is not above maximum.
- `is_accessible`: whether this room is accessible. A venue can be accessible while one room is not **(proposal)**.
- `seating_layout`, `equipment` (a list such as screen, projector, whiteboard, power strips), `notes` **(proposal)**.
- The number of rooms is the length of the list; there is no separate count field.

### Wifi **(proposal)**
- `has_wifi`, `wifi_notes`.

### Accessibility (Todd: "handicap accessible or not")
- `is_accessible`: the venue overall. Use the word "accessible" in labels and visitor wording.
- `has_step_free_entry`, `has_elevator`, `has_accessible_restroom`, `accessibility_notes` **(proposal)**: the specifics a visitor asks about.

### House rules
- `allows_minors`, `allows_animals` (Todd: "minors allowed, animals allowed"). Ties to the registration request: when `has_minors_present` is true on a request for a class at a venue where `allows_minors` is false, processing flags it for the organizer. It is not a refusal at the endpoint, because the venue may change or the request may be for a private session.
- `allows_food`, `allows_alcohol` **(proposal)**. Alcohol matters for a happy-hour format.
- `requires_insurance`, `insurance_notes` **(proposal)**: whether the venue wants proof of insurance.

### Availability (Todd: "hours of availability")
- `availability_hours`: a list of `day_of_week` (`monday` through `sunday`), `opens_at` and `closes_at` (24 hour `HH:MM`, venue local time). `opens_at` is before `closes_at`; a day with no entry is closed.
- `availability_notes`: holidays and exceptions.
- `setup_minutes_before`, `teardown_minutes_after` **(proposal)**: how long before and after a class the space is needed.

### Costs (Todd: "costs")
- `cost_cents` and `cost_basis` (`per_hour`, `per_session` or `per_day`). Each requires the other. Zero cents is a free venue. USD cents, same rule as every other money field.
- `deposit_cents`, `cancellation_terms`, `cost_notes` **(proposal)**.

### Other
- `notes`: anything that fits nowhere else.

### Set by the server only (readOnly)
- Identity and provenance: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (`dashboard` or `import`), `previous_id`, `deleted_at`, `deleted_by`.
- Summary numbers: `review_count` (starts at zero) and `average_rating` (1 to 5; absent until a first review exists), kept current from the reviews collection.
- `x_server_required` in the schema lists the readOnly fields every stored venue must have.

## 4. What the endpoints must do

1. Venue creation and changes come only from the dashboard. Reject any readOnly field sent.
2. Validate against the schema, then check the rules it cannot express: room labels are unique, each room's `preferred_occupancy` is not above its `max_occupancy`, and each day's `opens_at` is before its `closes_at`.
3. Set provenance and start `review_count` at zero.
4. When a class is saved with a `venue_id`: the venue must exist. If `venue_room_label` is present it must name a room in that venue, and the class's `capacity_max` must not be above that room's `max_occupancy` (**proposal**: a warning to the organizer first; make it a refusal only if Todd wants that).
5. Never delete a venue that classes point at; set it `inactive` instead.
6. Public pages and the class list never expose `contact_*`, `backup_contact_*` or a private venue's street address. What the class list may show (venue name, city, accessibility, address after a person has registered) is **(open)**.

## 5. Decisions

Todd's: rooms inside the venue; review aggregates inside, reviews outside with pointers back; address, GPS, parking, entry (words or GPS for each), pins later; contacts; room label, preferred and maximum occupancy; accessible or not; hours; costs; minors and animals allowed; public or private venue.

Claude's proposals (not yet confirmed): the whole list marked **(proposal)** above, including the `allows_` and `requires_` naming for booleans (the rules doc says booleans start with `is_`; the schemas also use `has_`, and this one adds `allows_` and `requires_`), the `active` and `inactive` statuses, and `venue_room_label` on the class.

## 6. Open items

- The `location_pin`, instructor (person), review, attendance and promotion schemas.
- Retention (`x_retention` is "undecided"), and how long a private home's address is kept.
- Which venue fields the public class list may show.
- Whether a class at a venue that disallows minors blocks or only flags.
- Amend `SCHEMA_RULES.md` to list the boolean prefixes in use.

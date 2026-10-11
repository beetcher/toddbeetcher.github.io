# Venue: Programming Guide

For anyone who writes code against `schemas/venue.schema.json`: the dashboard, the endpoints, the class list the registration page reads. Read `SCHEMA_RULES.md` first (conventions for every schema) and `SCHEDULED_CLASS_GUIDE.md` (classes point at venues). Where a decision is Claude's proposal and not Todd's it is marked **(proposal)**; where nothing is decided it is marked **(open)**.

Written October 6, 2026 from the venue design conversation (thread 11).

---

## 1. What a venue is

A place where classes are held. A venue is created from the dashboard, never by a public page. A venue record can begin as an idea (a cafe someone mentioned) and be filled in as it is vetted.

A venue is an entity of its own. It holds its name, its own email and phone, how to get in, pointers to its contact people, its rooms, its accessibility, its house rules, when it is available and what it costs. It does not hold where it is: that is a `location` record, reached through a `location_link` (see section 3, Where). A `scheduled_class` points at a venue with `venue_id` and names the room with `venue_room_label`. The venue does not store its classes; "all classes at this venue" is a lookup.

**Rooms live inside the venue record** (Todd): a room has no life apart from its venue. **Reviews live outside** (Todd): each review is its own record with a pointer back to the thing reviewed. The venue holds only the server-kept `review_count` and `average_rating`.

## 2. Status

`status` is `active` or `inactive` **(proposal)**. Inactive means not usable (an idea, a retired venue) and keeps a venue out of the picker without deleting it.

An `active` venue needs exactly one thing: a place, meaning a live `operates_at` location link to an active location that has an address or a GPS point (an endpoint rule, because it reads another collection). Everything else on the venue is optional, so a city park with no one to call, no rooms and no street address can be active. An inactive venue needs only `name`, `slug`, `status` and `is_public_venue`, so ideas can pile up as drafts with no place.

Because a link needs the venue to exist first, a venue is created inactive, linked to its place, and then activated. (A later single "add venue" operation can do all three steps as one.)

## 3. Fields

### The venue itself
- `name`, `slug` (lowercase letters, digits and underscores; unique; never changes), `description`.
- `is_public_venue` (Todd): a public venue (library, cafe, hall) versus a private one (a home, an office). Not the same as a class's `is_public`, which is whether the class is listed.

### Where
- A venue stores no address, GPS point or time zone. Its place is a `location` record, linked by a `location_link` whose `relationship` is `operates_at` (marked primary, with dates). When a venue moves buildings, only the link changes. Every location detail (address, GPS, time zone) is read from the place when a screen needs it.
- A class stores its own `time_zone`; the time zone of the venue's place is its natural default.
- `availability_hours` are in the venue's local time, meaning the time zone of its place.

### How to get in (Todd)
- `parking_description`, `parking_latitude`, `parking_longitude`: where to park, in words or GPS or both.
- `entry_description`, `entry_latitude`, `entry_longitude`: the door to use, in words or GPS or both.
- `transit_description`: how to arrive by bus or train **(proposal)**.
- `location_pin_ids`: UUIDs of `location_pin` records. A pin is a precise spot inside a venue (a picture, a verbal description and GPS), a schema still to be written. Todd called these "CAN pins" and said they come later; the venue only keeps the place to point at them.
- Each GPS pair needs both numbers: `parking_latitude` with `parking_longitude`, `entry_latitude` with `entry_longitude`.

### Who to contact
- `email`, `phone` (Todd): the venue's own email and phone, the business and not a person. Personal data when the venue is a private home (`x_pii`).
- `contact_individual_id` (Todd): the main contact, a pointer to an `individual` record. The venue stores no name or personal details for that person; they are read from the individual record when a screen needs them. `backup_contact_individual_id` is the optional backup, same rules.
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
6. `contact_individual_id` and `backup_contact_individual_id`, when given, must point at an individual that exists and is not erased (a merged individual is followed to the survivor). Activating a venue requires a live `operates_at` link to a location that has an address or a GPS point; nothing else is required. Public pages and the class list never expose `email`, `phone`, the contact people or a private venue's address. What the class list may show (venue name, city, accessibility, address after a person has registered) is **(open)**.

## 5. Decisions

Todd's: rooms inside the venue; review aggregates inside, reviews outside with pointers back; address, GPS, parking, entry (words or GPS for each), pins later; contacts; room label, preferred and maximum occupancy; accessible or not; hours; costs; minors and animals allowed; public or private venue.

Claude's proposals (not yet confirmed): the whole list marked **(proposal)** above, including the `allows_` and `requires_` naming for booleans (the rules doc says booleans start with `is_`; the schemas also use `has_`, and this one adds `allows_` and `requires_`), the `active` and `inactive` statuses, and `venue_room_label` on the class.

## 6. Open items

- The `location_pin`, instructor (person), review, attendance and promotion schemas.
- Retention (`x_retention` is "undecided"), and how long a private home's address is kept.
- Which venue fields the public class list may show.
- Whether a class at a venue that disallows minors blocks or only flags.
- Amend `SCHEMA_RULES.md` to list the boolean prefixes in use.

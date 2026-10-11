# Location: Programming Guide

For anyone who writes code against `schemas/location.schema.json`: the location handler, the link service, the Console. Read `SCHEMA_RULES.md` first. Written October 11, 2026 (thread 13). Every default is Claude's **(proposal)** unless Todd said it.

---

## 1. What it is

A place on Earth, of any size: a doorway, a street address, a 20-acre property with one street address and several GPS points, a parcel, a route. Todd's rule, in his words: a location holds **no knowledge of who lives there, who owns it, or who operates there**. Those are relationships, and they are `location_link` records (`LOCATION_LINK_GUIDE.md`) that can start and end while the location itself never changes. When a school or library moves buildings, nothing about either building changes; only the venue's link moves from one location to the other.

What a location is **not**:
- Not a structure. A house with three bedrooms and four baths is a separate thing located at a location (a later schema). Nothing about rooms, floors or beds is stored here.
- Not a household or a family. Two people at one location are not thereby related. Never infer a relationship from a shared location.
- Not a neighborhood or a city. Those are a different schema, later.

## 2. Fields

### What the sender provides
A location needs at least one of `name`, `addresses` or `geometries`, so there is always some way to tell which place it is.
- `kind`: point (a doorway or a spot), site (a building, campus or property), parcel (a legal lot) or route (a street or trail). Optional; site when absent.
- `name`: What people call the place. Optional on its own, but see above.
- `aliases`: Other names the place is or was known by. Up to 20.
- `description`: What the place physically is, in words. About the place only. Up to 2000 characters.
- `addresses`: Every street, mailing and former address, each with a `usage`. Up to 20; at most one `is_primary`.
- `geometries`: Every GPS point, line or outline, each with a `role`. Up to 50.
- `time_zone`: An IANA time zone name such as America/Denver.
- `identifiers`: Outside identifiers for the place (county parcel number, utility id). Each has a `type`, a `value` and an optional `description`. Up to 20.
- `characteristics`: Facts about the place itself, never about who is there. Each has a `type`, a `value` and an optional `description`. Up to 20.
- `part_of_location_id`: The larger location this one sits inside. One parent at most.
- `status`: active (default when omitted) or retired.

### Inside each address
- `usage`: civic, mailing, po_box or former. Required. This is Todd's "type" for each entry in the list.
- `description`: A few words about this address.
- `lines`: The address as printed, one string per line, up to 6.
- `street_number`, `street`, `unit`, `locality`, `region`, `postal_code`, `po_box`, `country`: The parts. `country` is two capital letters (US); a civic address needs one. `region` is two capital letters for the US.
- `valid_from`, `valid_to`: YYYY, YYYY-MM or YYYY-MM-DD. Absent `valid_to` means still valid.
- `is_primary`: True on the one address to show first.
- `verification`: none, self_reported or verified.
An address needs `usage` plus at least one of `lines`, `street` or `po_box`.

### Inside each geometry
- `role`: center, entrance, boundary, parcel or other. Required.
- `geometry`: The shape as GeoJSON (RFC 7946), with `type` (Point, MultiPoint, LineString, MultiLineString, Polygon or MultiPolygon) and `coordinates`. Longitude first, then latitude, WGS84, optional altitude. Required.
- `accuracy_m`: How close the shape is to the truth, in meters.
- `source`: gps_device, map_click, geocoder, survey, public_record or other.
- `as_of`: When it was captured, YYYY, YYYY-MM or YYYY-MM-DD.
- `label`: A short label such as "north gate".

### What the server sets (readOnly)
- `is_residential`: True while any live residence link points here. Used to find homes whose residents need privacy. Set by the link service, never by a sender.
- `address_keys`: Normalized strings made from each address, used to find a place that already exists. Set by the server.
- `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (dashboard or import), `deleted_at`, `deleted_by`: the standard fields.

## 3. Rules the schema cannot say (the handler and service enforce them)

1. At least one of `name`, `addresses`, `geometries`.
2. At most one address has `is_primary`.
3. A civic address has a `country`.
4. An address `valid_from` is not after its `valid_to`.
5. GeoJSON: Point is `[lon, lat]` or `[lon, lat, alt]`; MultiPoint and LineString are lists of points (a line has at least 2); a Polygon is a list of rings, each closed (first point equals last) with at least 4 points; Multi types nest one level deeper. Longitude -180 to 180, latitude -90 to 90.
6. `time_zone` must be a real IANA name.
7. `part_of_location_id` exists, is not the location itself, and makes no loop.
8. A location with a live link cannot be retired or deleted: `conflict`, `id:in_use`.
9. Two live locations with the same normalized address are reported to the operator as a match. The server never merges them. Merging duplicate locations is a later feature (`location_merge`).

## 4. Privacy (proposal)

A location holding a residence link is residential: `is_residential` is true. Until sign-in roles exist, a residential location where a **confidential or sealed person** lives is hidden from the Console (get answers not found, lists leave it out, an address search does not return it); the homes of ordinary people are visible to the operator. The check costs one link query per residential location in a list. Names, addresses, descriptions and geometries are personal data when the place is a home (`x_pii`). When the last link of an erased person goes, and nobody else past or present is linked to the location, the server retires the location and removes those fields. Logs carry ids and codes, never an address.

## 5. Lists and lookups

List: no filter, or ONE of `status`, `kind`, `is_residential`; always newest first. Find a place by address: the server looks up `address_keys`. There is no order by name, because a record without a name cannot be ordered by name.

## 6. History

`in_place`: addresses and shapes carry their own `valid_from` and `valid_to` and `as_of`, so a former address is a list entry with usage former, not a lost record. Who linked to the place and when is the link's job.

## 7. Not here, on purpose

Who lives, owns, operates or delivers there; hours, capacity or parking rules of a venue; how many bedrooms; family. Each lives with the thing it is true of.

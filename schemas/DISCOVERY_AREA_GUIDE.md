# Discovery area: Programming Guide

For anyone who writes code against `schemas/discovery_area.schema.json`: the area store, the territory directory and the Console Discovery station (the map and the Settings tab). Read `DISCOVERY_GUIDE.md` first. Written October 17, 2026 (thread 17).

---

## 1. What it is

A place a run may search: a US state, or a named region inside one state. Todd: states are switched on or off one by one, with all their ZIP codes; regions are named lists of ZIP codes, usually metro areas; edge cases err on the aggressive side; "not going to be selectable by zip code, but by state for sure".

A state's ZIP codes come from the shared ZIP table (a data file in the deploy folder, all 50 states and DC), so a state record does not copy them. A region lists its own ZIP codes.

## 2. Fields

- `kind` (required): `state` or `region`.
- `name` (required): the plain-words name on the map and in lists.
- `state_code` (required): two capital letters. For a region, the state it lies in.
- `zip_codes`: five-digit ZIP codes, up to 3,000, no repeats. Required for a region; not allowed on a state.
- `is_active` (required): whether a run may search here.
- `notes`: free text.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema says

A region requires `zip_codes`. A state refuses `zip_codes`. (Both are `if`/`then` rules in the schema.)

## 4. Rules the schema cannot say

1. One live state record per `state_code` (handler rule: same collection).
2. A region's `name` is unique within its `state_code` (handler rule).
3. Strings are trimmed before they are stored.

## 5. Service rules

1. Every ZIP in a region belongs to the region's state (needs the ZIP table).
2. A state or region with `is_active` false cannot be run. A region inside an inactive state cannot be run.
3. A ZIP may belong to more than one region.
4. Seed (step 3): 50 states and DC, only Colorado active; five Colorado regions (Boulder County, Denver metro, Colorado Springs, Fort Collins and Loveland, Longmont) that Todd edits.
5. Turning a state on only makes it selectable. Nothing is searched until a person presses Go.

## 6. Open items

- The source and license of the 50-state ZIP list.
- `geo_rank.py` is Colorado-only today; making it table-driven is a step 3 task.

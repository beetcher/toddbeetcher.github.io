# Discovery type: Programming Guide

For anyone who writes code against `schemas/discovery_type.schema.json`: the type store, the prompt builder and the Console Discovery station (Run tab and Settings tab). Read `DISCOVERY_GUIDE.md` first. Written October 17, 2026 (thread 17).

---

## 1. What it is

One kind of thing a finder looks for. For the venue finder these are Todd's "which type of venues": independent coffee shops and cafes, public libraries, Panera Bread locations, community and senior centers. The operator ticks types on the Run tab, and the prompt is built from the ones ticked. Todd wants the search to find unique, interesting meeting places, not only chains, so each type carries a hint that says what makes one worth listing.

## 2. Fields

- `finder_key` (required): which finder this type belongs to, such as `venue`.
- `key` (required): a short snake_case name, unique within the finder. Set once.
- `label` (required): the plain-words name in the Console.
- `search_hint`: a sentence or two that goes into the prompt for this type.
- `is_chain` (required): true when the type is the locations of one named chain, so the prompt asks for every location.
- `sort_order`: where the type sits in the picker, lowest first.
- `is_active` (required): the on/off switch.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema cannot say

1. `key` is unique within its `finder_key` among live records (handler rule: same collection). It is not changed after creation.
2. Strings are trimmed before they are stored.

## 4. Service rules

1. `finder_key` must name a registered finder.
2. A type with `is_active` false is not offered and cannot be run.
3. A finder with no active type cannot run.
4. Seed (step 3), for the venue finder: `coffee_shops`, `libraries`, `panera_bread` (chain), `community_centers`.

## 5. Open items

- The exact hint wording for each seeded type (Todd edits them in the Console).

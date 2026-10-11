# Merge Event: Programming Guide

For anyone who writes code against `schemas/merge_event.schema.json`: the merge handler, the Console. Read `SCHEMA_RULES.md` and `INDIVIDUAL_GUIDE.md` first. Written October 10, 2026 (thread 13). Every default is Claude's **(proposal)**.

---

## 1. What it is

The record of one decision that two individual records are the same person. It exists so a merge can be reversed and so there is proof of who decided, when and why. It is written only by the merge handler (never by a public page), never edited and never deleted. An unmerge marks it `unmerged`.

## 2. Fields

### What the operator sends (the merge op)
- `survivor_id`: The individual that stays. Required. Must be active or inactive, not merged, erased or deleted.
- `duplicate_id`: The individual found to be the same person, folded into the survivor. Required. Different from survivor_id, and not merged, erased or deleted.
- `reason`: Why the operator decided these are the same person: the evidence in words. Required, up to 500 characters. Personal data.
- `field_choices`: Optional per-field decisions where the two records disagree: the field name mapped to survivor (keep the survivor's value) or duplicate (take the duplicate's). Without a choice the server applies the survivorship rules in the guide. Up to 60 fields.

### What the server records (readOnly)
- `status`: merged (the merge stands) or unmerged (it was reversed). Set by the server.
- `survivor_before`: The survivor's whole record as it was just before the merge. Personal data; scrubbed to an empty object when either person is erased (then the merge can no longer be reversed). Set by the server.
- `duplicate_before`: The duplicate's whole record as it was just before the merge. Personal data; scrubbed like survivor_before. Set by the server.
- `changed_fields`: What the merge changed on the survivor: one entry per field, with its value before and after. An entry without `before` means the field was absent before; without `after`, it was removed. Set by the server.
- `moved_links`: Every other record that pointed at the duplicate and now points at the survivor: its collection, id and field (a dotted path for a nested field), with the value before and after. Unmerge puts back only those whose current value is still the `after` value. Up to 400. Set by the server.
- `unmerged_at`: When the merge was reversed (UTC). Set by the server.
- `unmerged_by`: Who reversed it, as an actor string. Set by the server.
- `unmerge_skipped`: What an unmerge could not put back because it had changed since: field and link entries by name and id, no values. Set by the server.
- `has_erased_snapshots`: True once a person in this merge was erased and the snapshots were scrubbed. Such a merge cannot be reversed. Set by the server.
- `id`: UUID v4, set by the server; also the Firestore document id.
- `schema_version`: Version of this schema the record was written under (currently 1). Set by the server.
- `created_at`: When the merge happened (UTC). Set by the server.
- `created_by`: Who decided the merge, as an actor string. Set by the server.
- `updated_at`: When the record last changed (UTC). Set by the server.
- `updated_by`: Who last changed the record. Set by the server.
- `source`: Where the record came from: dashboard. Merges are never made by a public page. Set by the server.

Inside `changed_fields`, each entry has `field`, `before` and `after`. Inside `moved_links`, each entry has `collection`, `id`, `field`, `before` and `after`.

## 3. Survivorship: how two records become one (proposal)

For each field the server decides, unless `field_choices` says otherwise:
- Identity and server fields never move (`id`, timestamps, `status`, `merged_into_id`, `erased_at`, `display_name`, `is_minor`, `retention_class`, `deleted_at`, `deleted_by`, `schema_version`, `source`, `created_by`, `created_at`, `updated_by`, `updated_at`).
- A field the survivor lacks is filled from the duplicate. A field both have keeps the survivor's value.
- Birth date and its certainty and verification move together as a group. The duplicate's group wins only when its verification is stronger (document over self over none). Recency never decides.
- Death status moves as a group (`life_status` and the `death_*` fields). The duplicate's wins only when it says deceased with `death_evidence` of document or public_record and the survivor is not already deceased.
- `external_refs` and `same_as_urls` are combined without repeats (within their size limits).
- `record_privacy` takes the stricter of the two (sealed over confidential over normal). `identity_verification` takes the stronger.
- `field_choices` set to `duplicate` takes the duplicate's value for that field (group rules above still move groups whole); set to `survivor` keeps the survivor's.

## 4. Rules the endpoint enforces

- Survivor and duplicate must be different, exist, and each be active or inactive (not merged, erased or deleted).
- Both holding restricted details refuses the merge (`duplicate_id:conflict_restricted_detail`); one holding them moves them to the survivor.
- Every record that points at the duplicate is re-pointed to the survivor: restricted details and requests (`individual_id`), assignments and transactions (`participant_individual_ids`), transaction `payer.party_id` and `payee.party_id`. More than 400 links refuses the merge (`duplicate_id:too_many_links`).
- The survivor, the duplicate, every re-pointed record and this event are written in one transaction. The duplicate becomes status merged with `merged_into_id`. Reads of the duplicate follow the redirect.
- **Unmerge** restores the duplicate from its snapshot, restores each survivor field and each link whose current value is still the value the merge wrote, and lists the rest in `unmerge_skipped`, so later legitimate changes are never undone. It is refused when the duplicate is no longer merged into the survivor, when the survivor was merged or erased, or when the snapshots were scrubbed.
- Nothing merges automatically. A match is a suggestion; an operator confirms (INDIVIDUAL_GUIDE section 6).

# Transaction Record: Programming Guide

For anyone who writes code against `schemas/transaction_record.schema.json`: the dashboard, payment handlers, endpoints and reports. Read `SCHEMA_RULES.md` first, then `REGISTRATION_ASSIGNMENT_GUIDE.md`. Where a decision is Claude's proposal and not Todd's it is marked **(proposal)**; where nothing is decided it is marked **(open)**.

Written October 8, 2026, from the schema conversation (thread 12).

---

## 1. What a transaction record is

Todd: payment is a collection of documents, a transaction record: from who to who, how much. It does not replace the actual transaction. It records it, for provenance.

- The real transaction lives somewhere else: a payment processor, a bank, a cash drawer. This record says that it happened (or is expected), between whom, for how much, and points to the outside system.
- **Other records hold only an id.** A registration assignment keeps a list of `transaction_record_ids` and nothing else about payment. Who paid, how much and how live here, once. The transaction record does not point back, so the two cannot drift apart **(proposal)**.
- **Never store card numbers, bank account numbers or any payment credentials**, in this record or anywhere. A card payment is recorded by the processor's own reference in `external_reference`, nothing more.
- Records are never edited to change what happened and never hard deleted (see refunds below).

## 2. Fields

### What kind of transaction
- `transaction_type`: required. `payment` (money in), `refund` (money back out) or `adjustment` (a correction or write-off).
- `status`: required. `pending` (expected or processing), `completed` (money moved), `failed` (did not go through), `voided` (cancelled before completing). A refund is not a status; it is its own record.
- `method`: required. `card_processor` (a third-party processor holds the card), `cash`, `check`, `bank_transfer` or `other`.

### From whom, to whom
- `payer` and `payee`: both required, each an object with:
  - `party_type`: `person`, `organization` or `program`. Required.
  - `name`: required. Personal data (marked `x_pii`).
  - `party_id`: the id of the party's own record, when one exists. None are written yet.
- Names are on the record so it reads on its own. A payer is usually the registration requester; their contact details stay on the request, not here **(proposal)**.

### How much and when
- `amount_cents`: required, a whole number of US cents, never negative. Direction is carried by `transaction_type`, `payer` and `payee`, not by a minus sign.
- `occurred_at`: required. When the money moved, or was expected to. Sent by the dashboard or handler because a transaction may be recorded after it happened.

### The outside system
- `external_source`: which system holds the real transaction (for example a processor's name). Optional.
- `external_reference`: that system's id for it, or a check number. Optional. Never card or account details.

### Refunds
- `refund_of_id`: the payment being refunded. **Required on a refund and not allowed on any other type.** The schema enforces both.
- A refund is a new record with `transaction_type` of `refund`, the payer and payee reversed, and its own amount (full or partial). The payment stays as it was. The endpoint checks that `refund_of_id` names a payment and that refunds together do not exceed it.

### Other
- `note`: anything worth remembering, in the organizer's words. Never card or account details.
- `program_slug`: which program, such as `launch`. Set by the server.

### Identity and provenance (set by the server)
`id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (`dashboard`, `import` or `system`; a payment webhook is `system`), `previous_id`, `deleted_at`, `deleted_by`.

## 3. How a payment is connected to a registration

1. Someone pays (a processor, cash, a check).
2. A handler or the dashboard writes a transaction record and gets its id.
3. The id is added to the assignment's `transaction_record_ids`.
4. Whether a party has paid is answered by reading those records, not by a flag on the request.

The request carries no payment fields. `is_paid`, `payment_source` and `payment_id` were removed from it in schema version 2. The request still carries `presented_cost_cents` and `presented_cost_basis`: what the visitor was shown, which is a different thing.

## 4. Rules the endpoint enforces

- A refund's `refund_of_id` names an existing record of type `payment`.
- Refunds recorded against a payment may not total more than its `amount_cents`.
- Any field marked readOnly is rejected if a sender includes it.
- Logs record ids and codes, never names or amounts tied to a person **(proposal)**.

## 5. Open

- Retention period (`x_retention` is undecided; required before launch).
- Whether an assignment is the only place payments attach, or a class can hold them too (a private session paid in advance) **(open)**. Today only the assignment holds ids.
- Whether `payer` and `payee` should point at person and organization records once those schemas exist (`party_id` is ready for that).
- Currency: US dollars only, per the rules.

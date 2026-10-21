#!/usr/bin/env python3
"""Mutation check for the Global Inspector (P-78): break each rule on purpose (the capability, the refusals, the hiding and masking, the Discovery cap,
the three doors, the seed) and run_inspector_tests.py must fail. Restores every file afterwards. Run from enjoy_router/:  python3 mutate_inspector.py"""
import os, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
AUTH = HERE / "access" / "authorize.py"; INS = HERE / "access" / "inspect.py"; END = HERE / "crud_endpoint.py"; CON = HERE / "console.py"
DIS = HERE / "discovery_door.py"; DOOR = HERE / "access" / "door.py"; SEED = HERE / "seed_access.py"; ROLE = HERE.parent / "schemas" / "access_role.schema.json"
M = [
 # --- who is an inspector
 ("a super admin counts as an inspector", AUTH, "return self.ok and not self.is_super_admin and INSPECT in self.capabilities", "return self.ok and INSPECT in self.capabilities"),
 ("nobody is an inspector", AUTH, "and INSPECT in self.capabilities", "and False"),
 ("me does not say who is an inspector", DOOR, '"inspector": access.inspector,', '"inspector": False,'),
 ("the capability is not in the schema list", ROLE, '          "inspect_everything",\n', ''),
 ("the seeded role holds more than the capability", SEED, 'capabilities=["inspect_everything"],', 'capabilities=["inspect_everything", "edit_venues"],'),
 # --- the Console door: refusals
 ("the door never refuses a write for an inspector", END, "if _inspect.refuses_op(collection, op) or _inspect.refuses_filters(collection, args.get(\"filters\")):", "if False:"),
 ("the door forgets the filter rule", END, "or _inspect.refuses_filters(collection, args.get(\"filters\"))", ""),
 ("the door does not know who an inspector is", END, "inspector = actor is None and access.inspector ", "inspector = False "),
 ("the door still applies a territory to an inspector", END, "and not access.is_super_admin and not inspector else None", "and not access.is_super_admin else None"),
 ("the door shows an inspector the raw result", END, "shown = _inspect.shape(store, collection, op, result.data)", "shown = result.data"),
 ("refuses_op lets writes through", INS, "return op not in policy.READ_OPS or collection in BLOCKED_COLLECTIONS", "return collection in BLOCKED_COLLECTIONS"),
 ("refuses_op lets the blocked collection through", INS, "return op not in policy.READ_OPS or collection in BLOCKED_COLLECTIONS", "return op not in policy.READ_OPS"),
 ("a filter on a hidden field is never refused", INS, "    return any(k in bad for k in filters)", "    return False"),
 ("a blocked collection is shown", INS, "    if collection in BLOCKED_COLLECTIONS:\n        return None\n    if collection == \"location_links\"", "    if False:\n        return None\n    if collection == \"location_links\""),
 # --- hidden
 ("street addresses are shown", INS, 'HIDE_FIELDS = frozenset({"street_address", ', 'HIDE_FIELDS = frozenset({'),
 ("the Google account id is shown", INS, '"google_uid", "preferred_location"', '"preferred_location"'),
 ("notes are shown", INS, "(k == HIDE_NOTES and collection not in NOTES_KEPT)", "False"),
 ("a venue's own note is hidden too", INS, 'NOTES_KEPT = frozenset({"venues", "curriculums"})', 'NOTES_KEPT = frozenset({"curriculums"})'),
 ("birth details are shown", INS, '"birth_place_city", "birth_place_region"', '"birth_place_region"'),
 ("a person's free-text journal note is shown", INS, '"street_address", "handled_note", "note", "birth_date"', '"street_address", "handled_note", "birth_date"'),
 ("a place's address list is kept inside people's records", INS, 'if k in ADDRESS_LISTS and collection not in ("venues", "locations"):', "if False:"),
 ("a person's home place is listed", INS, 'data = _drop(data, lambda r: r.get("id") in mine)', 'data = _drop(data, lambda r: False)'),
 ("a person's address link is listed", INS, 'data = _drop(data, lambda r: r.get("subject_type") == PERSON_SUBJECT)', 'data = _drop(data, lambda r: False)'),
 ("a single private record is returned", INS, "return None if is_private(data) else data", "return data"),
 ("the places that belong to people are looked up wrongly", INS, '[("subject_type", "==", PERSON_SUBJECT)]', '[("subject_type", "==", "venue")]'),
 # --- masked
 ("email is shown", INS, 'MASK_FIELDS = frozenset({"email", "phone",', 'MASK_FIELDS = frozenset({"phone",'),
 ("phone is shown", INS, 'MASK_FIELDS = frozenset({"email", "phone",', 'MASK_FIELDS = frozenset({"email",'),
 ("the ZIP is shown", INS, '"postal_code", "referrer_email"', '"referrer_email"'),
 ("a referrer's email is shown", INS, '"referrer_email", "organizer_email"', '"organizer_email"'),
 ("an organizer's phone is shown", INS, '"organizer_email", "organizer_phone"})', '"organizer_email"})'),
 ("the address a message went to is shown", INS, 'or (k == "to" and mask_to)', ''),
 ("a status change's to is masked", INS, 'mask_to = "channel" in node and "to" in node', 'mask_to = "to" in node'),
 ("an empty value shows as hidden", INS, "out[k] = MASK if v not in (None, \"\", [], {}) else v", "out[k] = MASK"),
 ("the records door shows requests as they are", INS, "return [_scrub(r, \"registration_requests\") for r in records]", "return list(records)"),
 ("a list's records are not shaped one by one", INS, 'return {**data, "records": [_scrub(r, collection) for r in data["records"]]}', 'return {**data}'),
 # --- shown in full
 ("staff emails are masked", INS, '"access_persons": frozenset({"email"}),', '"access_persons": frozenset(),'),
 ("a venue's contact is masked", INS, '"venues": frozenset({"email", "phone"}), "organizations"', '"venues": frozenset(), "organizations"'),
 ("an organization's contact is masked", INS, '"organizations": frozenset({"email", "phone"}),', '"organizations": frozenset(),'),
 ("the place a venue operates at is masked", INS, 'KEEP_SUBTREE = {"venues": frozenset({"place"}),', 'KEEP_SUBTREE = {"venues": frozenset(),'),
 ("a venue place's ZIP is masked", INS, '"locations": frozenset({"addresses"})}', '"locations": frozenset()}'),
 # --- the records door
 ("the records door never shapes", CON, "if access.inspector:                              # view only", "if False:                              # view only"),
 ("the records door still applies a territory to an inspector", CON, "scope = None if access.is_super_admin or access.inspector else", "scope = None if access.is_super_admin else"),
 ("the records door refuses the inspector", CON, "if not access.inspector and not _policy.allowed(access, _policy.RECORDS):", "if not _policy.allowed(access, _policy.RECORDS):"),
 # --- Discovery
 ("withdraw is allowed", INS, '"get_run", "list_runs", "zips"})   # no', '"get_run", "list_runs", "zips", "withdraw"})   # no'),
 ("the cap is 25 dollars", INS, "CAP_CENTS = 25", "CAP_CENTS = 2500"),
 ("exactly 25 cents is refused", INS, "cap > CAP_CENTS", "cap >= CAP_CENTS"),
 ("a quote is not capped", INS, 'if op in ("quote", "plan"):\n        cap', 'if op in ("plan",):\n        cap'),
 ("any run may be stepped or stopped", INS, "if op in OWN_RUN_OPS:", "if False:"),
 ("someone else's run may be stepped", INS, 'or run.get("created_by") != access.actor', 'or False'),
 ("the door never asks the Discovery rules", DIS, "refusal = _inspect.discovery_refusal(store, access, op, args)", "refusal = None"),
 ("the Discovery door refuses the inspector", DIS, "if not access.inspector and not _policy.allowed(access, _policy.discovery_need(op)):", "if not _policy.allowed(access, _policy.discovery_need(op)):"),
 ("the Discovery door still applies a territory to an inspector", DIS, "scope = None if access.is_super_admin or access.inspector else", "scope = None if access.is_super_admin else"),
]
survivors = []
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for label, f, a, b in M:
    src = f.read_text(encoding="utf-8")
    if src.count(a) != 1: print("CANNOT APPLY:", label, src.count(a)); survivors.append(label + " (pattern)"); continue
    f.write_text(src.replace(a, b), encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-B", str(HERE / "run_inspector_tests.py")], capture_output=True, text=True, timeout=240, cwd=HERE, env=env)
        caught = r.returncode != 0
    finally:
        f.write_text(src, encoding="utf-8")
    print(("caught   " if caught else "SURVIVED ") + label, flush=True)
    if not caught: survivors.append(label)
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)

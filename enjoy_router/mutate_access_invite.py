#!/usr/bin/env python3
"""Mutation check for the invitation email (P-64): break each rule on purpose (service, fact builder, wording, kind schema, door wiring) and the
test file must fail. Restores every file afterwards. Run from enjoy_router/:  python3 mutate_access_invite.py"""
import os, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parent
SVC = HERE / "crud" / "access_persons_service.py"; CTX = HERE / "launch_comms" / "invite_context.py"; END = HERE / "crud_endpoint.py"
KIND = ROOT / "schemas" / "message_kinds" / "access_invite.facts.schema.json"; SEED = ROOT / "schemas" / "examples" / "message_template.seed.json"
M = [
 # --- the service: when an email is sent
 ("an email is sent even to a system actor", SVC, 'not (isinstance(actor, str) and actor.startswith("user:")) or not r.data.get("is_active")', 'not r.data.get("is_active")'),
 ("an email is sent to a person invited switched off", SVC, 'or not r.data.get("is_active"):\n        return r', ':\n        return r'),
 ("an email is sent inside a caller's transaction", SVC, 'if not r.ok or tx is not None:', 'if not r.ok:'),
 ("the answer carries no invite_email", SVC, 'return success({**r.data, "invite_email": _send(store, r.data, actor, False)})', 'return r'),
 ("a crash in the CMS escapes", SVC, 'except Exception as exc:                                    # a mail problem is never the caller\'s problem', 'except KeyboardInterrupt as exc:'),
 ("CMS not configured is not skipped", SVC, 'return {"status": "skipped", "reason": "cms_off"}\n        call', 'return {"status": "sent", "reason": "ok"}\n        call'),
 ("an automatic send for create is marked manual", SVC, 'invite_context.call_for(store, person, actor, manual)', 'invite_context.call_for(store, person, actor, True)'),
 ("resend sends as automatic (duplicate protection stops it)", SVC, 'return success({"id": id, **_send(store, cur, actor, True)})', 'return success({"id": id, **_send(store, cur, actor, False)})'),
 ("resend ignores a switched-off person", SVC, 'if not cur.get("is_active"):', 'if False:'),
 ("resend ignores a deleted person", SVC, 'if cur is None or "deleted_at" in cur:', 'if cur is None:'),
 ("resend skips the bad-id check", SVC, 'problems = check_actor(actor) + id_problem(id)', 'problems = check_actor(actor)'),
 ("resend skips the actor check", SVC, 'problems = check_actor(actor) + id_problem(id)', 'problems = id_problem(id)'),
 ("resend works with the CMS not configured", SVC, 'if not comms.is_configured():\n        return bad([{"field": "email", "issue": "not_enabled"}])', 'if False:\n        return bad([])'),
 ("update is not passed through", SVC, 'COLLECTION, get, list, update, soft_delete = H.COLLECTION, H.get, H.list, H.update, H.soft_delete', 'COLLECTION, get, list, update, soft_delete = H.COLLECTION, H.get, H.list, H.get, H.soft_delete'),
 # --- the fact builder
 ("greeting word for a nameless person is not there", CTX, 'else "there"', 'else "friend"'),
 ("the greeting uses the whole name", CTX, 'return words[0] if words else "there"', 'return " ".join(words) if words else "there"'),
 # (left out on purpose: dropping the user:admin guard in inviter_of changes nothing, because no access person can have the id "admin"; the guard is defensive)
 ("the inviter shows the id instead of the name", CTX, 'return (p.get("display_name") or p.get("email") or KEY_INVITER)', 'return actor'),
 ("an inviter with no name shows nothing", CTX, 'p.get("display_name") or p.get("email") or KEY_INVITER', 'p.get("display_name") or KEY_INVITER'),
 ("an unknown role is not noticed", CTX, 'if role is None or "deleted_at" in role:', 'if False:'),
 ("the role description is never given", CTX, 'if role.get("description"):', 'if False:'),
 ("the Console address is wrong", CTX, 'CONSOLE_URL = "https://beetcher.com/console/"', 'CONSOLE_URL = "https://beetcher.com/"'),
 ("the dedupe key is the same for everyone", CTX, 'dedupe_key=f"access_invite:{person[\'id\']}"', 'dedupe_key="access_invite"'),
 ("the recipient is not the invited address", CTX, '"email": person["email"]}\n    return', '"email": "someone@else.example"}\n    return'),
 ("the audience is wrong", CTX, 'audience="invitee"', 'audience="student"'),
 # --- the kind
 ("the email address is no longer a needed fact", KIND, '"required": [\n    "name",\n    "inviter",\n    "role_name",\n    "email",\n    "console_url"\n  ]', '"required": [\n    "name",\n    "inviter",\n    "role_name",\n    "console_url"\n  ]'),
 ("unknown facts are allowed", KIND, '"additionalProperties": false,\n  "propertyNames"', '"additionalProperties": true,\n  "propertyNames"'),
 ("the role description became required", KIND, '"required": [\n    "name",\n    "inviter",\n    "role_name",', '"required": [\n    "name",\n    "inviter",\n    "role_description",\n    "role_name",'),
 # --- the wording
 ("the subject changed", SEED, '"subject": "You\'re invited to the LAUNCH Console"', '"subject": "Welcome"'),
 ("the exact-address warning is gone", SEED, 'It has to be that exact address; a different Google account will be refused. ', ''),
 ("the Google account is not named", SEED, '"label": "Use this Google account",\n              "value": "{email}"', '"label": "Use this Google account",\n              "value": "your Google account"'),
 ("the inviter is not named", SEED, '"text": "{inviter} has invited you to the LAUNCH Console as **{role_name}**."', '"text": "You have been invited to the LAUNCH Console as **{role_name}**."'),
 ("the role description shows even when empty", SEED, '"text": "{role_description}",\n          "show_if": "role_description"', '"text": "{role_description}"'),
 ("the Console button is gone", SEED, '"type": "button",\n          "label": "Open the Console",\n          "link": "{console_url}",\n          "plain_prefix": "Open the Console:",\n          "has_fallback_line": true', '"type": "paragraph",\n          "text": "Open the Console."'),
 ("the sign-out note is gone", SEED, '"text": "For safety, the Console signs you out after a period of inactivity. Just sign in again."', '"text": "Welcome."'),
 ("the template is switched off", SEED, '"subject": "You\'re invited to the LAUNCH Console",\n      "is_active": true', '"subject": "You\'re invited to the LAUNCH Console",\n      "is_active": false'),
 # --- the door
 ("the Console cannot use send_invite", END, ', "add_note", "send_invite"})\nSTATUS', ', "add_note"})\nSTATUS'),
 ("send_invite takes no id", END, '"send_invite": ({"id"}, set()),', '"send_invite": (set(), {"id"}),'),
 ("access_persons skips the service (no email on invite)", END, '"access_persons": access_persons_service,', '"access_persons": access_persons_crud,'),
 ("the door never calls send_invite", END, '            return module.send_invite(store, a["id"], actor, now=now)', '            return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])'),
]
survivors = []
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for label, f, a, b in M:
    src = f.read_text(encoding="utf-8")
    if src.count(a) != 1: print("CANNOT APPLY:", label, src.count(a)); survivors.append(label + " (pattern)"); continue
    f.write_text(src.replace(a, b), encoding="utf-8")
    try:
        if f == END and "access_persons_crud," in b:
            f.write_text(src.replace(a, b).replace("from crud import (access_persons_service,", "from crud import (access_persons_crud,"), encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", str(HERE / "run_access_invite_tests.py")], capture_output=True, text=True, timeout=180, cwd=HERE, env=env)
        caught = r.returncode != 0
    finally:
        f.write_text(src, encoding="utf-8")
    print(("caught   " if caught else "SURVIVED ") + label, flush=True)
    if not caught: survivors.append(label)
print("\n%d of %d caught" % (len(M) - len(survivors), len(M)))
if survivors: print("survivors:", survivors)
sys.exit(1 if survivors else 0)

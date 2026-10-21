"""Seed sign-in access in live Firestore: the two starting roles and the first super admin. Todd runs this; Claude never does.

It writes ONLY to `access_roles` and `access_persons`, through the same handlers the Console uses, so every rule applies. Safe to run
twice: anything already there is left alone. Default is a dry run: it says what it would create and creates nothing.

    venv/bin/python sync_schemas.py
    venv/bin/python seed_access.py                                                         # dry run
    venv/bin/python seed_access.py --seed --confirm-project launch-ai-workshop

What it adds:
  role    Super admin (does everything, including inviting and removing people)
  role    Global Inspector (looks at everything, changes nothing; for demos)
  role    Admin, Manager, Instructor (what a person can do everywhere; WHERE they work is their territory, set in the Console). Edit them there.
  move    the old "Region head" role is a territory word, not a role: if it exists, the people who hold it move to Manager and the old role is
          switched off (never deleted). A fresh setup never creates it.
  person  the first super admin, by Google email (default toddbeetcher17@gmail.com; use --email to change it before the first run)

It stores no key and no password. Signing in is done with Google in the Console.
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROJECT = "launch-ai-workshop"
ACTOR = "system:access_seed"
DEFAULT_EMAIL = "toddbeetcher17@gmail.com"
DEFAULT_NAME = "Todd Beetcher"
TERRITORIAL = ["manage_requests", "manage_classes", "manage_instructors", "edit_venues", "activate_venues", "edit_people", "edit_places",
               "edit_regions", "view_messages", "manage_messages", "run_discovery", "invite_people"]
ROLES = [
    dict(key="super_admin", label="Super admin", is_super_admin=True, is_active=True,
         description="The owner. May do everything, including inviting and removing other people."),
    dict(key="admin", label="Admin", is_super_admin=False, is_active=True,
         capabilities=["view_console", "manage_curriculums", "view_spend"] + TERRITORIAL,
         description="Runs a territory end to end: requests, classes, instructors, venues, people, places, regions, messages and Discovery searches "
                     "there, plus curriculums and spend. No Discovery settings and no access management. Where they work is their territory."),
    dict(key="manager", label="Manager", is_super_admin=False, is_active=True,
         capabilities=["view_console", "view_spend", "manage_requests", "manage_classes", "manage_instructors", "edit_venues",
                       "activate_venues", "edit_people", "edit_places", "view_messages", "run_discovery"],
         description="Manages the day-to-day in a territory: requests, classes, instructors, venues, people and places, reads messages, "
                     "runs Discovery searches. Cannot create regions or send messages. Where they work is their territory."),
    dict(key="instructor", label="Instructor", is_super_admin=False, is_active=True,
         capabilities=["view_console", "manage_classes"],
         description="Sees the classes they teach (and who is in them), once their sign-in is linked to their person record."),
    dict(key="global_inspector", label="Global Inspector", is_super_admin=False, is_active=True, capabilities=["inspect_everything"],
         description="View only. Sees every station and list (Activity, Access, Spend, Discovery and Messages too) and changes nothing. Private details "
                     "are hidden or masked. May start a Discovery run, capped at 25 cents. For demos."),
]
OLD_ROLE = "region_head"
NEW_ROLE = "manager"


def plan(store, email):
    """(roles still to create, True when the first super admin person is missing)."""
    from crud import access_persons_crud as PE
    from crud import access_roles_crud as RO
    have = {r["key"] for r in RO.list(store, None, "key", 200).data["records"]}
    return [r for r in ROLES if r["key"] not in have], PE.find_live_by_email(store, email) is None


def nothing_to_do(todo, need_person, old):
    return not todo and not need_person and old is None


def old_role_work(store):
    """(the old Region head role if it is still switched on, the people who hold it): what the move must do. (None, []) when nothing to do."""
    from crud import access_persons_crud as PE
    from crud import access_roles_crud as RO
    old = RO.list(store, {"key": OLD_ROLE}).data["records"]
    if not old or not old[0].get("is_active"):
        return None, []
    return old[0], PE.list(store, {"role_id": old[0]["id"]}, "email", 200).data["records"]


def apply(store, email, name):
    from crud import access_persons_crud as PE
    from crud import access_roles_crud as RO
    done = []
    todo, need_person = plan(store, email)
    for r in todo:
        res = RO.create(store, r, ACTOR, source="import")
        if not res.ok:
            raise SystemExit(f"role {r['key']} refused: {res.problems}")
        done.append(f"role {r['key']}")
    old, holders = old_role_work(store)
    if old is not None:
        new = RO.list(store, {"key": NEW_ROLE}).data["records"][0]
        for p in holders:
            res = PE.update(store, p["id"], {"role_id": new["id"]}, ACTOR)
            if not res.ok:
                raise SystemExit(f"moving {p['email']} to Manager refused: {res.problems}")
            done.append(f"moved {p['email']} from Region head to Manager")
        res = RO.update(store, old["id"], {"is_active": False}, ACTOR)
        if not res.ok:
            raise SystemExit(f"switching off the Region head role refused: {res.problems}")
        done.append("switched off the old Region head role")
    if need_person:
        sup = RO.list(store, {"key": "super_admin"}).data["records"]
        if not sup:
            raise SystemExit("the super_admin role is missing")
        res = PE.create(store, {"email": email, "display_name": name, "role_id": sup[0]["id"]}, ACTOR, source="import")
        if not res.ok:
            raise SystemExit(f"person {email} refused: {res.problems}")
        done.append(f"person {email} as Super admin")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--email", default=DEFAULT_EMAIL, help="the Google email of the first super admin")
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--seed", action="store_true", help="really write (default is a dry run)")
    ap.add_argument("--confirm-project", default="", help="type the project id to allow --seed")
    args = ap.parse_args()

    from google.cloud import firestore
    from crud.firestore_doc_store import FirestoreDocStore
    store = FirestoreDocStore(firestore.Client(project=args.project), "")
    todo, need_person = plan(store, args.email)
    old, holders = old_role_work(store)
    print(f"Project {args.project}: roles to create: {[r['key'] for r in todo] or 'none (already there)'}; "
          f"first super admin {args.email}: {'MISSING' if need_person else 'present'}; "
          f"old Region head role: {'to move %d people to Manager and switch off' % len(holders) if old is not None else 'nothing to move'}")
    if nothing_to_do(todo, need_person, old):
        print("Nothing to do.")
        return 0
    if not args.seed:
        print("DRY RUN: nothing written. Add --seed --confirm-project %s to write." % args.project)
        return 0
    if args.confirm_project != args.project:
        print("Refusing: --confirm-project must equal the project id.")
        return 2
    for line in apply(store, args.email, args.name):
        print("created", line)
    todo, need_person = plan(store, args.email)
    old, _ = old_role_work(store)
    ok = nothing_to_do(todo, need_person, old)
    print("Verified:", "ok" if ok else "something is still missing")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

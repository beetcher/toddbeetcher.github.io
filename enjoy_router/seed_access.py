"""Seed sign-in access in live Firestore: the two starting roles and the first super admin. Todd runs this; Claude never does.

It writes ONLY to `access_roles` and `access_persons`, through the same handlers the Console uses, so every rule applies. Safe to run
twice: anything already there is left alone. Default is a dry run: it says what it would create and creates nothing.

    venv/bin/python sync_schemas.py
    venv/bin/python seed_access.py                                                         # dry run
    venv/bin/python seed_access.py --seed --confirm-project launch-ai-workshop

What it adds:
  role    Super admin (does everything, including inviting and removing people)
  role    Region head (venues, instructors and requests; no Discovery spending, no settings, no access management). Edit it in the Console.
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
ROLES = [
    dict(key="super_admin", label="Super admin", is_super_admin=True, is_active=True,
         description="The owner. May do everything, including inviting and removing other people."),
    dict(key="region_head", label="Region head", is_super_admin=False, is_active=True,
         capabilities=["view_console", "edit_venues", "activate_venues", "manage_instructors", "manage_requests"],
         description="Runs one region: edits and switches on its venues and manages its instructors and requests. "
                     "No Discovery spending, no settings, no access management."),
]


def plan(store, email):
    """(roles still to create, True when the first super admin person is missing)."""
    from crud import access_persons_crud as PE
    from crud import access_roles_crud as RO
    have = {r["key"] for r in RO.list(store, None, "key", 200).data["records"]}
    return [r for r in ROLES if r["key"] not in have], PE.find_live_by_email(store, email) is None


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
    print(f"Project {args.project}: roles to create: {[r['key'] for r in todo] or 'none (already there)'}; "
          f"first super admin {args.email}: {'MISSING' if need_person else 'present'}")
    if not todo and not need_person:
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
    print("Verified:", "ok" if not todo and not need_person else "something is still missing")
    return 0 if not todo and not need_person else 1


if __name__ == "__main__":
    sys.exit(main())

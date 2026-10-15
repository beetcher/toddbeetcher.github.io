"""Seed the CMS in live Firestore: the settings record and the starting message templates (the receipt, the placement confirmation and the change notices). Todd runs this; Claude never does.

It writes ONLY to `comms_settings` and `message_templates`, through the same handlers the Console uses, so every rule applies.
The first two templates are today's receipt and placement emails, word for word (schemas/examples/message_template.seed.json), published as
version 1. It is safe to run twice: anything already there is left alone.

Default is a dry run: it says what it would create and creates nothing.
To really write: add --seed AND --confirm-project launch-ai-workshop.

    venv/bin/python sync_schemas.py
    venv/bin/python seed_comms.py                                         # dry run
    venv/bin/python seed_comms.py --seed --confirm-project launch-ai-workshop

When the wording of a seed template changes later, publish it as a new version (the old one stays in the history):
    venv/bin/python seed_comms.py --refresh students_added --seed --confirm-project launch-ai-workshop
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROJECT = "launch-ai-workshop"
ACTOR = "system:cms_seed"
SEED = HERE.parent / "schemas" / "examples" / "message_template.seed.json"
FIELDS = ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")


def plan(store):
    """(settings_needed, [templates to create]) given what is already in the store."""
    from crud import comms_settings_crud as SET
    from crud import message_templates_crud as MT
    need_settings = SET.list(store).data["count"] == 0
    todo = []
    for t in json.loads(SEED.read_text())["templates"]:
        if not MT._same_key(store, t):
            todo.append(t)
    return need_settings, todo


def changed(store):
    """Seed templates that exist but whose subject or blocks differ from the seed file: [(standing record, seed template)]."""
    from crud import message_templates_crud as MT
    out = []
    for t in json.loads(SEED.read_text())["templates"]:
        cur = MT.standing(store, t)
        if cur is not None and (cur.get("subject") != t["subject"] or cur.get("blocks") != t["blocks"]):
            out.append((cur, t))
    return out


def refresh(store, kinds):
    """A new published version (the old one stays in the history) for each standing template of the named kinds whose wording changed."""
    from crud import message_templates_crud as MT
    done = []
    for cur, t in changed(store):
        if t["kind"] not in kinds:
            continue
        d = MT.draft_from(store, cur["id"], ACTOR)
        if not d.ok:
            raise SystemExit(f"draft of {t['kind']} refused: {d.problems}")
        u = MT.update(store, d.data["id"], {"subject": t["subject"], "blocks": t["blocks"]}, ACTOR)
        if not u.ok:
            raise SystemExit(f"update of {t['kind']} refused: {u.problems}")
        p = MT.publish(store, d.data["id"], ACTOR)
        if not p.ok:
            raise SystemExit(f"publishing {t['kind']} refused: {p.problems}")
        done.append(f"template {t['kind']} ({t['audience']}) now version {p.data['version']}")
    return done


def apply(store, need_settings, todo):
    from crud import comms_settings_crud as SET
    from crud import message_templates_crud as MT
    done = []
    if need_settings:
        r = SET.create(store, {}, ACTOR, source="import")
        if not r.ok:
            raise SystemExit(f"settings refused: {r.problems}")
        done.append("settings (Launch defaults)")
    for t in todo:
        r = MT.create(store, {k: t[k] for k in FIELDS}, ACTOR, source="import")
        if not r.ok:
            raise SystemExit(f"template {t['kind']} refused: {r.problems}")
        p = MT.publish(store, r.data["id"], ACTOR)
        if not p.ok:
            raise SystemExit(f"publishing {t['kind']} refused: {p.problems}")
        done.append(f"template {t['kind']} (email, {t['audience']}) version {p.data['version']}")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--seed", action="store_true", help="really write (default is a dry run)")
    ap.add_argument("--refresh", default="", help="comma-separated kinds whose wording changed in the seed file: publish a new version of each")
    ap.add_argument("--confirm-project", default="", help="type the project id to allow --seed")
    args = ap.parse_args()

    from google.cloud import firestore
    from crud.firestore_doc_store import FirestoreDocStore
    store = FirestoreDocStore(firestore.Client(project=args.project), "")
    if args.refresh:
        kinds = {k.strip() for k in args.refresh.split(",") if k.strip()}
        will = [t["kind"] for _c, t in changed(store) if t["kind"] in kinds]
        print(f"Project {args.project}: templates whose wording changed: {[t['kind'] for _c, t in changed(store)] or 'none'}; to publish as a new version: {will or 'none'}")
        if not will:
            return 0
        if not args.seed:
            print("DRY RUN: nothing written. Add --seed --confirm-project %s to write." % args.project)
            return 0
        if args.confirm_project != args.project:
            print("Refusing: --confirm-project must equal the project id.")
            return 2
        for line in refresh(store, kinds):
            print("published", line)
        print("Verified:", "ok" if not [1 for _c, t in changed(store) if t["kind"] in kinds] else "something is still different")
        return 0
    need_settings, todo = plan(store)
    print(f"Project {args.project}: settings record {'MISSING' if need_settings else 'present'}; "
          f"templates to create: {[t['kind'] for t in todo] or 'none (already there)'}")
    if not need_settings and not todo:
        print("Nothing to do.")
        return 0
    if not args.seed:
        print("DRY RUN: nothing written. Add --seed --confirm-project %s to write." % args.project)
        return 0
    if args.confirm_project != args.project:
        print("Refusing: --confirm-project must equal the project id.")
        return 2
    for line in apply(store, need_settings, todo):
        print("created", line)
    n_set, n_todo = plan(store)
    print("Verified:", "ok" if not n_set and not n_todo else "something is still missing")
    return 0 if not n_set and not n_todo else 1


if __name__ == "__main__":
    sys.exit(main())

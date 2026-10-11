"""Clear old records from named live Firestore collections. Todd runs this; Claude never does.

You must NAME the collections. Allowed: venues, scheduled_classes, registration_assignments,
registration_requests, idempotency_keys. It refuses anything else (people, places, place links, merge
history and every test_ collection are never touched).

Default is a dry run: it counts and lists what it would delete, and deletes nothing.
To really delete: add --delete AND --confirm-project launch-ai-workshop.

    python3 clear_collections.py scheduled_classes
    python3 clear_collections.py scheduled_classes --delete --confirm-project launch-ai-workshop
"""
import argparse
import sys

PROJECT = "launch-ai-workshop"
ALLOWED = ("venues", "scheduled_classes", "registration_assignments", "registration_requests", "idempotency_keys")
LABEL = ("name", "title", "slug", "confirmation_number")   # never prints emails or other personal details


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("collections", nargs="+", help="one or more of: " + ", ".join(ALLOWED))
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--delete", action="store_true", help="really delete (default is a dry run)")
    ap.add_argument("--confirm-project", default="", help="type the project id to allow --delete")
    args = ap.parse_args()
    bad = [c for c in args.collections if c not in ALLOWED]
    if bad:
        print("Refusing. Not allowed: " + ", ".join(bad) + ". Allowed: " + ", ".join(ALLOWED))
        return 2

    from google.cloud import firestore
    db = firestore.Client(project=args.project)

    found = {}
    for c in args.collections:
        docs = list(db.collection(c).stream())
        found[c] = docs
        print(f"\n{c}: {len(docs)} record(s)")
        for d in docs[:30]:
            x = d.to_dict()
            label = next((str(x[k]) for k in LABEL if x.get(k)), "")
            print(f"  {d.id}  {label}  status={x.get('status', '-')}")
        if len(docs) > 30:
            print(f"  ... and {len(docs) - 30} more")
    total = sum(len(v) for v in found.values())
    if not total:
        print("\nNothing to delete.")
        return 0
    if not args.delete:
        print(f"\nDRY RUN: nothing deleted ({total} record(s) would go). Add --delete --confirm-project {args.project} to delete.")
        return 0
    if args.confirm_project != args.project:
        print("Refusing: --confirm-project must equal the project id.")
        return 2

    for c, docs in found.items():
        batch, n = db.batch(), 0
        for d in docs:
            batch.delete(d.reference)
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = db.batch()
        batch.commit()
        left = len(list(db.collection(c).stream()))
        print(f"{c}: deleted {n}, remaining {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

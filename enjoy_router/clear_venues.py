"""Clear the venue records from live Firestore. Todd runs this; Claude never does.

It touches ONE collection: `venues`. It never touches test_ collections, places,
location_links, people, classes, assignments or registrations. Those are only COUNTED
so you can see what still points at a venue.

Default is a dry run: it lists what it would delete and deletes nothing.
To really delete: add --delete AND --confirm-project launch-ai-workshop.

    python3 clear_venues.py                      # dry run
    python3 clear_venues.py --delete --confirm-project launch-ai-workshop
"""
import argparse
import sys

PROJECT = "launch-ai-workshop"
COLLECTION = "venues"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--delete", action="store_true", help="really delete (default is a dry run)")
    ap.add_argument("--confirm-project", default="", help="type the project id to allow --delete")
    args = ap.parse_args()

    from google.cloud import firestore
    db = firestore.Client(project=args.project)

    docs = list(db.collection(COLLECTION).stream())
    print(f"Project {args.project}, collection '{COLLECTION}': {len(docs)} record(s)")
    for d in docs:
        x = d.to_dict()
        print(f"  {d.id}  {x.get('name', '?')}  status={x.get('status', '?')}")

    # Report only: things that still point at venues.
    links = [l for l in db.collection("location_links").stream()
             if l.to_dict().get("subject_type") == "venue"]
    classes = [c for c in db.collection("scheduled_classes").stream()
               if c.to_dict().get("venue_id")]
    print(f"Left alone: {len(links)} place link(s) for venues, {len(classes)} class(es) with a venue.")

    if not docs:
        print("Nothing to delete.")
        return 0
    if not args.delete:
        print("DRY RUN: nothing deleted. Add --delete --confirm-project %s to delete." % args.project)
        return 0
    if args.confirm_project != args.project:
        print("Refusing: --confirm-project must equal the project id.")
        return 2

    batch = db.batch()
    n = 0
    for d in docs:
        batch.delete(d.reference)
        n += 1
        if n % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    left = len(list(db.collection(COLLECTION).stream()))
    print(f"Deleted {n} venue record(s). Remaining in '{COLLECTION}': {left}")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

# Open READY

Operational workshop: https://beetcher-ready.web.app/ready/

The GitHub Pages page at https://beetcher.com/ready/web/ is an unconnected preview with a link to the operational workshop. It does not accept an API key or connect to a database. Management and API use the same Firebase origin; no cross-origin backend setting is needed.

## Owner connection

The initial key is super admin. It is stored as `READY_API_KEY` in Secret Manager in project `beetcher-ready`; it is not in source or this document. On the authorized Mac, copy it directly to the clipboard without displaying it:

```bash
gcloud secrets versions access latest --secret=READY_API_KEY --project=beetcher-ready | pbcopy
```

Open the operational workshop, paste into **Super-admin API key**, and choose **Connect**. The badge must say **FirestoreStore · super admin**. The input clears after connection; the key is held in page memory only. Reload or Disconnect ends that page's connection. Clear the clipboard after pasting if desired.

## First inventory

Choose **Bulk import → Load builder validation seed → Validate without saving**. Inspect the report, then choose **Commit this import** deliberately. The supplied educational seed contains ten questions, 38 reusable answer atoms and ten four-choice contextual sets. It is tagged builder-created/system-validation and is not an official assessment.

Deployment verification records are retained and archived. Toggle **Include archived** and **Include revisions** to inspect them. A blank active library after verification is intentional; no user inventory was deleted.

The management surface authors content, builds/exports immutable tests and accepts returned results. The caller administers tests; READY has no participant player. See API.md for integration contracts and OPERATIONS.md for deployment and rollback.

# Open READY

Operational workshop: https://beetcher-ready.web.app/ready/

The GitHub Pages page at https://beetcher.com/ready/web/ is an unconnected preview with a link to the operational workshop. It does not accept an API key or connect to a database. Management and API use the same Firebase origin; no cross-origin backend setting is needed.

## Owner connection

The initial key is super admin. It is stored as `READY_API_KEY` in Secret Manager in project `beetcher-ready`; it is not in source or this document. On the authorized Mac, run the local, Git-ignored helper to copy it directly to the clipboard without displaying it:

```bash
cd /Users/nddev/nd/bd/toddbeetcher.github.io/ready
./getadminkey.sh
```

The helper contains no embedded key and is excluded from deployment packaging. See ../README.md for Google sign-in instructions and the equivalent command on an authorized machine without this local helper.

Open the operational workshop, paste into **Super-admin API key**, and choose **Connect**. The badge must say **FirestoreStore · super admin**. The input clears after connection. The accepted key is kept in this tab’s `sessionStorage`; reload and hard refresh automatically reconnect and revalidate it with the API. Disconnect removes it before reloading. Closing a tab normally ends its session; browser restore/duplicate-tab features can restore or copy session storage, so Disconnect is the explicit clear action. A rejected/rotated key is removed on HTTP 401. No `localStorage`, cookies or authentication bypass is used. Clear the clipboard after pasting if desired.

## First inventory

The educational seed was activated on October 29, 2026: ten published questions, 38 answer atoms and ten published sets are available. Five-set selection was verified. To inspect or import additional seed content, choose **Bulk import → Load builder validation seed → Validate without saving**, inspect the report and commit only if you intend a new import; do not duplicate the active seed just to browse it. The supplied educational seed contains ten questions, 38 reusable answer atoms and ten four-choice contextual sets. It is tagged builder-created/system-validation and is not an official assessment.

Deployment verification records are retained and archived. Toggle **Include archived** and **Include revisions** to inspect them. The earlier deployment-validation records remain archived; the separate educational seed is now active. No historical records were deleted.

The management surface authors content, builds/exports immutable tests and accepts returned results. The caller administers tests; READY has no participant player. See API.md for integration contracts and OPERATIONS.md for deployment and rollback.

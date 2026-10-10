#!/bin/bash
# Check the Console's admin endpoint with curl. Writes NOTHING: only reads, and calls that name an id that does not exist.
# Reads the admin key from the git-ignored env file; never prints it.   enjoy_router/admin_curl_check.sh
HERE="$(cd "$(dirname "$0")" && pwd)"
KEY="$(grep '^ICDT_ADMIN_KEY=' "$HERE/.env.launch-ai-workshop" | cut -d= -f2-)"
URL="${ADMIN_URL:-https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_admin}"
call() { echo; echo "--- $1"; curl -s -w '\nHTTP %{http_code}\n' -X POST "$URL" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d "$2"; }

echo "--- no key (expect 401)"; curl -s -w '\nHTTP %{http_code}\n' -X POST "$URL" -d '{}'
echo; echo "--- browser preflight from beetcher.com (expect 2xx and an allow-origin header)"
curl -s -o /dev/null -D - -X OPTIONS "$URL" -H 'Origin: https://beetcher.com' -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type' | grep -i -E '^HTTP|access-control-allow-(origin|headers|methods)'
call "list venues (expect 200, probably count 0)" '{"collection":"venues","op":"list","args":{}}'
call "list venues, status=active (expect 200; needs the real venues index)" '{"collection":"venues","op":"list","args":{"filters":{"status":"active"}}}'
call "update an unknown id (expect 404, writes nothing)" '{"collection":"venues","op":"update","args":{"id":"11111111-1111-4111-8111-111111111111","changes":{"name":"X"}}}'
call "soft_delete an unknown id (expect 404, writes nothing)" '{"collection":"venues","op":"soft_delete","args":{"id":"11111111-1111-4111-8111-111111111111"}}'
call "list scheduled_classes (expect 200)" '{"collection":"scheduled_classes","op":"list","args":{}}'
call "list scheduled_classes, status=scheduled (expect 200; needs the classes index, which takes a few minutes after deploy)" '{"collection":"scheduled_classes","op":"list","args":{"filters":{"status":"scheduled"}}}'
call "list scheduled_classes by venue_id (expect 200; needs the index)" '{"collection":"scheduled_classes","op":"list","args":{"filters":{"venue_id":"11111111-1111-4111-8111-111111111111"}}}'
call "update a class with an unknown id (expect 404, writes nothing)" '{"collection":"scheduled_classes","op":"update","args":{"id":"11111111-1111-4111-8111-111111111111","changes":{"title":"X"}}}'
call "soft_delete a class with an unknown id (expect 404, writes nothing)" '{"collection":"scheduled_classes","op":"soft_delete","args":{"id":"11111111-1111-4111-8111-111111111111"}}'
call "assignments: queue (expect 200 with items and counts; reads requests, assignments and classes)" '{"collection":"registration_assignments","op":"queue","args":{}}'
call "assignments: list newest first (expect 200)" '{"collection":"registration_assignments","op":"list","args":{}}'
call "assignments: list by status (expect 200; needs the assignments index, a few minutes after deploy)" '{"collection":"registration_assignments","op":"list","args":{"filters":{"status":"waitlisted"}}}'
call "assignments: suggest for an unknown request (expect 404, writes nothing)" '{"collection":"registration_assignments","op":"suggest","args":{"request_id":"11111111-1111-4111-8111-111111111111"}}'
call "assignments: create for an unknown request (expect 400 request_id:not_found, writes nothing)" '{"collection":"registration_assignments","op":"create","args":{"data":{"request_id":"11111111-1111-4111-8111-111111111111","scheduled_class_id":"22222222-2222-4222-8222-222222222222"}}}'
call "assignments: delete is refused (expect 400 id:not_allowed, writes nothing)" '{"collection":"registration_assignments","op":"soft_delete","args":{"id":"11111111-1111-4111-8111-111111111111"}}'
call "venues: queue is not for venues (expect 400 op:not_supported)" '{"collection":"venues","op":"queue","args":{}}'
call "set_review_summary is server-only (expect 400 not enabled)" '{"collection":"venues","op":"set_review_summary","args":{"id":"11111111-1111-4111-8111-111111111111","review_count":1,"average_rating":5}}'
echo; echo "Done. Nothing was written."

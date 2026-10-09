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
call "set_review_summary is server-only (expect 400 not enabled)" '{"collection":"venues","op":"set_review_summary","args":{"id":"11111111-1111-4111-8111-111111111111","review_count":1,"average_rating":5}}'
echo; echo "Done. Nothing was written."

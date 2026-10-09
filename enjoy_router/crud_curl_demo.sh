#!/bin/bash
# Exercise the CRUD test endpoint with curl. Reads the admin key from the git-ignored env file; never prints it.
# Works only on test_-prefixed collections. Run from anywhere:  enjoy_router/crud_curl_demo.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
KEY="$(grep '^ICDT_ADMIN_KEY=' "$HERE/.env.launch-ai-workshop" | cut -d= -f2-)"
URL="${CRUD_URL:-https://us-central1-launch-ai-workshop.cloudfunctions.net/enjoy_crud_test}"
call() { echo; echo "--- $1"; curl -s -w '\nHTTP %{http_code}\n' -X POST "$URL" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d "$2"; }

echo "--- no key (expect 401)"; curl -s -w '\nHTTP %{http_code}\n' -X POST "$URL" -d '{}'
SLUG="demo_$(date +%s)"
OUT=$(curl -s -X POST "$URL" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d "{\"collection\":\"venues\",\"op\":\"create\",\"args\":{\"data\":{\"name\":\"  Demo Cafe \",\"slug\":\"$SLUG\",\"status\":\"inactive\",\"is_public_venue\":true}}}")
echo; echo "--- create (expect ok, name trimmed)"; echo "$OUT"
ID=$(echo "$OUT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["id"])')
UPD=$(echo "$OUT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["updated_at"])')
call "create same slug again (expect 400 slug:duplicate)" "{\"collection\":\"venues\",\"op\":\"create\",\"args\":{\"data\":{\"name\":\"B\",\"slug\":\"$SLUG\",\"status\":\"inactive\",\"is_public_venue\":true}}}"
call "get (expect 200)" "{\"collection\":\"venues\",\"op\":\"get\",\"args\":{\"id\":\"$ID\"}}"
call "update name (simple path, expect 200)" "{\"collection\":\"venues\",\"op\":\"update\",\"args\":{\"id\":\"$ID\",\"changes\":{\"name\":\"Demo Cafe Renamed\"}}}"
call "update with stale expected_updated_at (expect 409 conflict)" "{\"collection\":\"venues\",\"op\":\"update\",\"args\":{\"id\":\"$ID\",\"changes\":{\"name\":\"X\"},\"expected_updated_at\":\"2020-01-01T00:00:00Z\"}}"
call "set status active without the required fields (whole-record path, expect 400 with several problems)" "{\"collection\":\"venues\",\"op\":\"update\",\"args\":{\"id\":\"$ID\",\"changes\":{\"status\":\"active\"}}}"
call "list status=inactive (needs the index; expect 200)" '{"collection":"venues","op":"list","args":{"filters":{"status":"inactive"}}}'
call "list newest first (expect 200)" '{"collection":"venues","op":"list","args":{"order":"-created_at","limit":5}}'
call "soft delete (expect 200)" "{\"collection\":\"venues\",\"op\":\"soft_delete\",\"args\":{\"id\":\"$ID\"}}"
call "get after delete (expect 404)" "{\"collection\":\"venues\",\"op\":\"get\",\"args\":{\"id\":\"$ID\"}}"
echo; echo "Done. Records live only in the test_venues collection."

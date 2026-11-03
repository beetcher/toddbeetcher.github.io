#!/usr/bin/env bash
# Import a READY draft library into live Firestore via POST /v1/content/imports.
# Usage: ready/scripts/import_library.sh <slug> [--live]
#   slug: us_geography | us_citizenship | smoking_meat | judgment | (R1 folder name: library)
#   default is a DRY RUN (validates, writes nothing). Add --live to really import.
# Skips *sample* files (they overlap the main batches). Stops at the first failure.
# Key is read from Secret Manager into memory only; never printed or saved.
set -euo pipefail
cd "$(dirname "$0")/../.."
SLUG="${1:?usage: import_library.sh <slug> [--live]}"
MODE="${2:-}"
if [ "$SLUG" = "library" ]; then DIR="ready/seed/library"; else DIR="ready/seed/library_${SLUG}"; fi
[ -d "$DIR" ] || { echo "No folder $DIR"; exit 1; }
URL="https://beetcher-ready.web.app/v1/content/imports"
DRY=true; [ "$MODE" = "--live" ] && DRY=false
echo "Folder: $DIR   Mode: $([ $DRY = true ] && echo DRY RUN || echo LIVE)"
KEY="$(gcloud secrets versions access latest --secret=READY_API_KEY --project=beetcher-ready --account=toddbeetcher17@gmail.com)"
[ -n "$KEY" ] || { echo "Could not read key (try: gcloud auth login toddbeetcher17@gmail.com)"; exit 1; }
for f in $(ls "$DIR"/*.json | grep -v -i sample); do
  BODY="$(python3 - "$f" "$DRY" <<'PY'
import json,sys,uuid
f,dry=sys.argv[1],sys.argv[2]=="true"
d=json.load(open(f))
d["dry_run"]=dry
# deterministic key per file+mode: re-running the same file is a safe replay, not a duplicate
import hashlib
d["idempotency_key"]=str(uuid.UUID(bytes=hashlib.sha256(("ready-library-import:"+f+":"+("dry" if dry else "live")).encode()).digest()[:16],version=4))
print(json.dumps(d))
PY
)"
  OUT="$(mktemp)"
  CODE="$(curl -sS -o "$OUT" -w '%{http_code}' -X POST "$URL" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" --data "$BODY")"
  echo "--- $(basename "$f") -> HTTP $CODE"
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(json.dumps(d.get('data',d.get('error',d)),indent=1)[:1200])" "$OUT" || cat "$OUT"
  rm -f "$OUT"
  case "$CODE" in 200|201) ;; *) echo "STOPPED at $f"; exit 1;; esac
done
echo "Done ($([ $DRY = true ] && echo dry run || echo live))."

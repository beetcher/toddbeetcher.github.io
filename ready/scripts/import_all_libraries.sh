#!/usr/bin/env bash
# Dry-run all four remaining libraries; only if every dry run passes, import them live.
# Usage: ready/scripts/import_all_libraries.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
LIBS="library judgment smoking_meat us_citizenship"
echo "===== PHASE 1: DRY RUN ====="
for s in $LIBS; do
  echo "##### $s (dry)"
  ready/scripts/import_library.sh "$s" || { echo "DRY RUN FAILED on $s. Nothing was imported live."; exit 1; }
done
echo "===== All dry runs passed. PHASE 2: LIVE IMPORT ====="
for s in $LIBS; do
  echo "##### $s (live)"
  ready/scripts/import_library.sh "$s" --live || { echo "LIVE IMPORT FAILED on $s. Earlier libraries are already imported."; exit 1; }
done
echo "===== ALL DONE ====="

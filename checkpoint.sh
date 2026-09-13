#!/usr/bin/env bash
# checkpoint.sh — commit and push whatever's currently changed, as a safe rollback point.
# Usage:
#   ./checkpoint.sh                  -> commits with a timestamped message
#   ./checkpoint.sh "your message"   -> commits with your message

set -e

cd "$(dirname "$0")"

MSG="${1:-Checkpoint $(date '+%Y-%m-%d %H:%M')}"

git add -A

if git diff --cached --quiet; then
  echo "Nothing to commit — working tree already matches last checkpoint."
  exit 0
fi

echo "--- Changes being committed ---"
git status -s
echo "--------------------------------"

git commit -m "$MSG"
git push origin "$(git branch --show-current)"

echo "Checkpoint pushed: $MSG"

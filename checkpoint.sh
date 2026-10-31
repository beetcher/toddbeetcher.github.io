#!/usr/bin/env bash
# checkpoint.sh — commit and push ONLY the files you name, as a safe rollback point.
# Usage:
#   ./checkpoint.sh "your message" path/one path/two ...   -> stages just those files, commits, pushes
#   ./checkpoint.sh --all ["your message"]                 -> old behaviour: stages EVERYTHING changed
# With no file names and no --all it stops, so other work in the folder is never swept in by accident.

set -e

cd "$(dirname "$0")"

ALL=0
if [ "$1" = "--all" ]; then ALL=1; shift; fi

MSG="${1:-Checkpoint $(date '+%Y-%m-%d %H:%M')}"
[ $# -gt 0 ] && shift

if [ "$ALL" = "1" ]; then
  git add -A
elif [ $# -gt 0 ]; then
  git add -- "$@"
else
  echo "No files named. Usage: ./checkpoint.sh \"message\" file1 file2 ...   (or --all to stage everything)"
  echo "Currently changed:"; git status -s
  exit 1
fi

if git diff --cached --quiet; then
  echo "Nothing to commit — the named files already match the last checkpoint."
  exit 0
fi

echo "--- Changes being committed ---"
git diff --cached --name-status
echo "--------------------------------"

git commit -m "$MSG"
git push origin "$(git branch --show-current)"

echo "Checkpoint pushed: $MSG"

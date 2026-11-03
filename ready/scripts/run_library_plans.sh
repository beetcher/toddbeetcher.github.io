#!/usr/bin/env bash
# run_library_plans.sh — run READY library plans one at a time, each in a brand-new Claude Code session.
# Usage (from anywhere):  ready/scripts/run_library_plans.sh            -> R2, R3, R4, R5 in order
#                         ready/scripts/run_library_plans.sh R2 R4      -> just those, in that order
# Each plan gets a fresh headless session (no shared context, no compaction). A failure is logged and the next plan still runs.
# Logs go to ~/ready-library-run-logs/ (outside the repo, never committed).

cd "$(dirname "$0")/../.." || exit 1          # repo root
REPO="$(pwd)"

declare -A PLAN
PLAN[R1]="ready/docs/plans/PLAN-R1-ai-library.md"
PLAN[R2]="ready/docs/plans/PLAN-R2-smoking-meat.md"
PLAN[R3]="ready/docs/plans/PLAN-R3-us-geography.md"
PLAN[R4]="ready/docs/plans/PLAN-R4-us-citizenship.md"
PLAN[R5]="ready/docs/plans/PLAN-R5-judgment-critical-thinking.md"

ORDER=("$@")
[ ${#ORDER[@]} -eq 0 ] && ORDER=(R2 R3 R4 R5)

MODEL="${CLAUDE_MODEL:-sonnet}"
# Unattended runs cannot answer permission prompts. This lets the session use files and the shell in this folder without asking.
# Change it if you want something stricter (then expect some steps to be refused).
PERM_FLAGS=(--permission-mode acceptEdits --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep")

LOGDIR="$HOME/ready-library-run-logs"
mkdir -p "$LOGDIR"
STAMP="$(date '+%Y%m%d-%H%M%S')"

echo "Repo: $REPO   Model: $MODEL   Plans: ${ORDER[*]}"
echo "Logs: $LOGDIR"

for ID in "${ORDER[@]}"; do
  P="${PLAN[$ID]}"
  if [ -z "$P" ] || [ ! -f "$P" ]; then echo "[$ID] plan file not found, skipping"; continue; fi
  LOG="$LOGDIR/$STAMP-$ID.log"
  echo "=== [$ID] starting $(date '+%H:%M:%S')  ($P)"
  PROMPT="Nobody is available to answer questions in this run. Read ready/docs/plans/READY-LIBRARY-COMMON.md first (it applies in full), then $P, and execute that plan step by step, including checkpointing with ./checkpoint.sh and writing its report. If you are blocked, record why in the report and stop; do not ask questions. Other plans run later in separate sessions; do not start them."
  claude -p "$PROMPT" --model "$MODEL" "${PERM_FLAGS[@]}" 2>&1 | tee "$LOG"
  STATUS=${PIPESTATUS[0]}
  echo "=== [$ID] finished $(date '+%H:%M:%S')  exit=$STATUS  log=$LOG"
  git status --short | sed 's/^/    uncommitted: /' | head -20
  osascript -e "display notification \"$ID finished (exit $STATUS)\" with title \"READY library\"" 2>/dev/null
done

echo "All requested plans have been attempted. Reports are in ready/docs/reports/. Logs: $LOGDIR"
osascript -e 'display notification "All plans attempted" with title "READY library"' 2>/dev/null

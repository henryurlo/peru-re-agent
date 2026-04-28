#!/usr/bin/env bash
# Run a single Claude Code priority for PeruRE Agent
# Usage: ./scripts/run_priority.sh <priority_number>

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PRIORITY="${1:-}"

if [ -z "$PRIORITY" ]; then
    echo "Usage: $0 <priority_number>"
    echo ""
    echo "Priorities:"
    echo "  1 — Build FastAPI backend"
    echo "  2 — Wire frontend, .env, Docker, start scripts"
    echo "  3 — Batch processing, rate limiting, admin dashboard"
    echo "  4 — Real Mapbox/WhatsApp/DB integrations"
    echo "  5 — Deployment docs, CI/CD, Makefile, polish"
    exit 1
fi

PROMPT_FILE="$PROJECT_DIR/.claude/prompts/handoff-p${PRIORITY}.txt"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Prompt file not found: $PROMPT_FILE"
    exit 1
fi

LOG_FILE="$PROJECT_DIR/.claude/logs/priority_${PRIORITY}_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "Running Priority $PRIORITY..."
echo "Log: $LOG_FILE"
echo ""

cd "$PROJECT_DIR"
cat "$PROMPT_FILE" | claude -p --dangerously-skip-permissions --name "peru-re-priority-${PRIORITY}" > "$LOG_FILE" 2>&1

echo "Priority $PRIORITY finished."
echo "Log: $LOG_FILE"
echo ""
echo "Last 30 lines:"
tail -n 30 "$LOG_FILE"

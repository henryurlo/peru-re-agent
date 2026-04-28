#!/usr/bin/env bash
# Run a Claude Code priority with automatic OpenRouter fallback on rate limits.
# Usage: ./scripts/run_priority_with_fallback.sh <priority_number>

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PRIORITY="${1:-}"

if [ -z "$PRIORITY" ]; then
    echo "Usage: $0 <priority_number>"
    exit 1
fi

CLAUDE_PROMPT="$PROJECT_DIR/.claude/prompts/handoff-p${PRIORITY}.txt"
OPENROUTER_PROMPT="$PROJECT_DIR/.claude/prompts/handoff-p${PRIORITY}-openrouter.txt"
LOG_DIR="$PROJECT_DIR/.claude/logs"
mkdir -p "$LOG_DIR"

CLAUDE_LOG="$LOG_DIR/priority_${PRIORITY}_claude_$(date +%Y%m%d_%H%M%S).log"
FALLBACK_LOG="$LOG_DIR/priority_${PRIORITY}_fallback_$(date +%Y%m%d_%H%M%S).log"

echo "========================================"
echo "Priority $PRIORITY — Claude Code (Anthropic)"
echo "========================================"

# Try Claude Code first
cd "$PROJECT_DIR"
if [ -f "$CLAUDE_PROMPT" ]; then
    if cat "$CLAUDE_PROMPT" | claude -p --dangerously-skip-permissions --name "peru-re-priority-${PRIORITY}" > "$CLAUDE_LOG" 2>&1; then
        echo "✅ Claude Code succeeded."
        echo "Log: $CLAUDE_LOG"
        tail -n 30 "$CLAUDE_LOG"
        exit 0
    else
        echo "❌ Claude Code failed (exit code $?). Checking for rate limits..."
        
        # Check for rate limit / credit errors
        if grep -qiE "(rate limit|429|too many requests|credits? exhausted|quota|billing)" "$CLAUDE_LOG"; then
            echo "⚠️  Rate limit or credit issue detected."
        else
            echo "⚠️  Other error. Log: $CLAUDE_LOG"
        fi
    fi
else
    echo "Prompt file not found: $CLAUDE_PROMPT"
    exit 1
fi

# Fallback to OpenRouter via Hermes API (if available)
echo ""
echo "========================================"
echo "Priority $PRIORITY — FALLBACK: OpenRouter"
echo "========================================"
echo "Attempting fallback execution..."

# Create a temporary Python script that uses Hermes's API capabilities
# This requires the hermes-agent to be running and accessible
TEMP_SCRIPT="/tmp/fallback_priority_${PRIORITY}_$(date +%s).py"
cat > "$TEMP_SCRIPT" << 'PYEOF'
import sys
import json
import os

prompt_file = sys.argv[1]
log_file = sys.argv[2]

with open(prompt_file) as f:
    prompt = f.read()

# Try to call Hermes API if available
try:
    # This would need to be adapted based on how Hermes exposes its API
    # For now, just log the attempt
    with open(log_file, "w") as f:
        f.write("FALLBACK ATTEMPTED\n")
        f.write(f"Prompt length: {len(prompt)} chars\n")
        f.write("OpenRouter fallback not yet implemented in this script.\n")
        f.write("Please run manually via Hermes with the -openrouter prompt file.\n")
    print("Fallback logged. Manual intervention needed.")
except Exception as e:
    print(f"Fallback failed: {e}")
PYEOF

python3 "$TEMP_SCRIPT" "$OPENROUTER_PROMPT" "$FALLBACK_LOG"
rm -f "$TEMP_SCRIPT"

echo ""
echo "Logs:"
echo "  Claude:  $CLAUDE_LOG"
echo "  Fallback: $FALLBACK_LOG"

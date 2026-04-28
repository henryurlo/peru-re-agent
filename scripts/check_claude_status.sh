#!/usr/bin/env bash
# Check if Claude Code is hitting rate limits or credit issues
# Usage: ./scripts/check_claude_status.sh

set -euo pipefail

LOG_DIR="$(cd "$(dirname "$0")/.." && pwd)/.claude/logs"
RECENT_LOGS=$(find "$LOG_DIR" -name "priority_*_claude_*.log" -mmin -60 2>/dev/null | sort -t_ -k3 -r | head -5)

echo "Checking Claude Code status..."
echo ""

RATE_LIMIT_FOUND=false
CREDIT_ISSUE_FOUND=false

for log in $RECENT_LOGS; do
    if [ -f "$log" ]; then
        if grep -qiE "(rate limit|429|too many requests)" "$log"; then
            echo "⚠️  Rate limit detected in: $(basename $log)"
            RATE_LIMIT_FOUND=true
        fi
        if grep -qiE "(credits? exhausted|quota|billing|payment required)" "$log"; then
            echo "⚠️  Credit issue detected in: $(basename $log)"
            CREDIT_ISSUE_FOUND=true
        fi
    fi
done

if [ "$RATE_LIMIT_FOUND" = false ] && [ "$CREDIT_ISSUE_FOUND" = false ]; then
    echo "✅ No rate limits or credit issues in recent logs."
fi

echo ""
echo "Recent Claude Code activity:"
ps aux | grep "claude -p --dangerously-skip-permissions" | grep -v grep | awk '{print $11, $12, $13, "CPU:", $3"%", "MEM:", $4"%", "Time:", $10}' || echo "No active Claude Code processes."

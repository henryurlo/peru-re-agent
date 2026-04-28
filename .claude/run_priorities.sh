#!/usr/bin/env bash
# PeruRE Agent — Autonomous Priority Runner
# Runs Claude Code through all priorities until completion or rate limits.
# Usage: ./.claude/run_priorities.sh [start_priority]

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_PROMPTS_DIR="$PROJECT_DIR/.claude/prompts"
LOG_DIR="$PROJECT_DIR/.claude/logs"
mkdir -p "$LOG_DIR"

START_PRIORITY="${1:-1}"
CURRENT_PRIORITY="$START_PRIORITY"

# Priority definitions
PRIORITY_1="You are taking over the PeruRE Agent project. Follow these instructions exactly:

1. FIRST, read CLAUDE_HANDOFF.md to understand the full project state and priorities.
2. THEN read README.md and ARCHITECTURE.md for context.
3. THEN list the current directory structure to understand what exists.
4. Priority 1: Build the FastAPI backend (backend/main.py) that:
   - Serves the frontend (static files from frontend/)
   - Mounts the 4 MCP servers (maps, calendar, whatsapp, property_db) as sub-applications or routes them correctly
   - Provides an API endpoint POST /api/v1/coordinate that accepts a JSON payload {\"broker_id\": str, \"instruction\": str, \"context\": dict} and returns the coordinator agent's structured response
   - Provides health check GET /health
   - Uses uvicorn and fastapi
   - Keeps all 25 existing tests in tests/test_coordinator.py passing (run pytest)
5. If backend/ directory doesn't exist, create it.
6. Update requirements.txt if new dependencies are needed.
7. Write a backend/test_main.py with at least 3 FastAPI endpoint tests.
8. Run all tests (pytest tests/ backend/test_main.py -v) and ensure they pass.
9. Do NOT commit anything — just get the code ready.
10. Return a summary of what files you created/modified and any issues encountered.

Work autonomously. You may read, write, edit, and test code. You may run shell commands. Do not ask the user for clarification — make reasonable architectural decisions and document them in comments."

PRIORITY_2="You are taking over the PeruRE Agent project for Priority 2. Read CLAUDE_HANDOFF.md first for full context.

CURRENT STATE:
- backend/main.py exists with /health, /api/v1/coordinate, MCP SSE mounts, static frontend serving
- backend/test_main.py has 15 tests (all passing)
- tests/test_coordinator.py has 25 tests (all passing)
- 40 total tests passing

PRIORITY 2 TASKS (do all of these):

1. Add python-dotenv loading to backend/main.py so it reads ANTHROPIC_API_KEY, MAPBOX_TOKEN, DB_URL from .env file at startup. Fail gracefully with clear error messages if keys are missing.

2. Create scripts/start_server.sh that:
   - Checks for .env file, creates .env.example if missing
   - Sources venv
   - Sets PYTHONPATH to project root
   - Starts uvicorn on port 8000 with sensible defaults
   - Make it executable (chmod +x)

3. Wire the frontend (frontend/index.html) to the real backend API:
   - Replace mock data with fetch() calls to /api/v1/coordinate
   - Add a simple form where broker can type an instruction and see the response
   - Show loading state while waiting for API
   - Display structured response (action_plan, findings, requires_approval)
   - Keep the Mapbox map visualization for route display
   - Add a 'Simulate Cancellation' button that sends the demo scenario

4. Update docker-compose.yml to:
   - Build the backend from the new Dockerfile
   - Pass environment variables from .env
   - Ensure frontend static files are served correctly
   - Add a healthcheck on the backend container

5. Create backend/Dockerfile if it doesn't exist

6. Run all tests (pytest tests/ backend/test_main.py -v) and ensure they still pass.

7. Do NOT commit anything. Return a summary of files created/modified.

Work autonomously. Make reasonable decisions. Document in comments."

PRIORITY_3="You are taking over the PeruRE Agent project for Priority 3. Read CLAUDE_HANDOFF.md first.

CURRENT STATE:
- Backend API working with /health and /api/v1/coordinate
- Frontend wired to backend API
- All 40 tests passing

PRIORITY 3 TASKS:

1. Add a POST /api/v1/batch endpoint that accepts a list of broker instructions and runs them through the coordinator in parallel using asyncio.gather or ThreadPoolExecutor. Return a list of results.

2. Implement rate limiting on /api/v1/coordinate using slowapi or a simple in-memory token bucket (10 req/min per broker_id).

3. Add request/response logging middleware — log to stdout with structured JSON.

4. Create a simple admin dashboard at /admin that shows:
   - Recent requests (last 20)
   - Broker activity
   - MCP server health status

5. Add WebSocket endpoint /ws/broker/{broker_id} for real-time updates (optional but nice).

6. Run all tests and ensure they pass.

7. Do NOT commit. Return summary.

Work autonomously. Document decisions in comments."

PRIORITY_4="You are taking over the PeruRE Agent project for Priority 4. Read CLAUDE_HANDOFF.md first.

CURRENT STATE:
- Full backend with REST API, batch processing, rate limiting
- Frontend wired to API
- Admin dashboard
- All tests passing

PRIORITY 4 TASKS:

1. Implement the real Mapbox integration in mcp_servers/maps/server.py — replace mock data with actual Mapbox API calls using the MAPBOX_TOKEN env var.

2. Add caching layer for Mapbox responses (Redis or simple in-memory TTL cache) to avoid repeated API calls for same routes.

3. Implement the WhatsApp Business API integration in mcp_servers/whatsapp/server.py — use the real WhatsApp Business API or Twilio as fallback.

4. Add PostgreSQL connection pooling in mcp_servers/property_db/server.py with real CRUD operations.

5. Add integration tests that verify MCP servers work end-to-end (mock external APIs).

6. Run all tests.

7. Do NOT commit. Return summary.

Work autonomously. Document decisions."

PRIORITY_5="You are taking over the PeruRE Agent project for Priority 5 (final). Read CLAUDE_HANDOFF.md first.

CURRENT STATE:
- Full backend, frontend, real integrations
- All tests passing

PRIORITY 5 TASKS:

1. Write a comprehensive DEPLOYMENT.md guide covering:
   - Docker deployment
   - Environment variables
   - Database migrations
   - SSL/certbot setup
   - Monitoring (health checks, logs)

2. Add GitHub Actions CI/CD workflow that:
   - Runs tests on every PR
   - Builds Docker image
   - Deploys to staging on merge

3. Create a Makefile with common commands:
   - make test
   - make run
   - make docker-build
   - make docker-up
   - make lint

4. Add pre-commit hooks (black, ruff) configuration.

5. Final test run — all tests must pass.

6. Update README.md with setup instructions, architecture diagram reference, and contributing guide.

7. Do NOT commit. Return summary of all changes.

Work autonomously. Document everything."

# Function to run a single priority
run_priority() {
    local p="$1"
    local log_file="$LOG_DIR/priority_${p}_$(date +%Y%m%d_%H%M%S).log"
    local prompt_var="PRIORITY_${p}"
    local prompt="${!prompt_var:-}"

    if [ -z "$prompt" ]; then
        echo "No priority $p defined. Done."
        return 1
    fi

    echo "========================================"
    echo "STARTING PRIORITY $p"
    echo "Log: $log_file"
    echo "========================================"

    cd "$PROJECT_DIR"

    # Run Claude Code non-interactively
    echo "$prompt" | claude -p --dangerously-skip-permissions --name "peru-re-priority-${p}" > "$log_file" 2>&1
    local exit_code=$?

    echo "Priority $p finished with exit code $exit_code"
    echo "Last 50 lines of log:"
    tail -n 50 "$log_file"

    # Run tests to verify nothing broke
    echo "Running tests..."
    if [ -d "$PROJECT_DIR/venv" ]; then
        source "$PROJECT_DIR/venv/bin/activate"
    fi
    if pytest tests/ backend/test_main.py -v >> "$log_file" 2>&1; then
        echo "✅ All tests passed for Priority $p"
    else
        echo "⚠️  Tests failed for Priority $p — check log: $log_file"
    fi

    return 0
}

# Main loop
echo "PeruRE Agent — Autonomous Priority Runner"
echo "Starting from Priority $START_PRIORITY"
echo "Project: $PROJECT_DIR"
echo "Logs: $LOG_DIR"
echo ""

while true; do
    if ! run_priority "$CURRENT_PRIORITY"; then
        echo "Stopping at Priority $CURRENT_PRIORITY"
        break
    fi

    CURRENT_PRIORITY=$((CURRENT_PRIORITY + 1))

    # Safety: stop after priority 5
    if [ "$CURRENT_PRIORITY" -gt 5 ]; then
        echo "All priorities (1-5) completed!"
        break
    fi

    echo ""
    echo "Moving to Priority $CURRENT_PRIORITY in 5 seconds..."
    sleep 5
done

echo ""
echo "========================================"
echo "AUTONOMOUS RUN COMPLETE"
echo "Check logs in: $LOG_DIR"
echo "========================================"

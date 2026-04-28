#!/usr/bin/env bash
# Start the PeruRE Agent development server

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

cd "$PROJECT_DIR"

# Check for .env; create from .env.example if missing
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  .env file not found."
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
        echo "Created $ENV_FILE from .env.example — please fill in your real API keys before continuing."
        echo ""
        cat "$ENV_FILE"
        exit 1
    else
        echo "ERROR: No .env.example found. Please create $ENV_FILE manually."
        exit 1
    fi
fi

# Export .env variables into the shell environment so uvicorn inherits them.
# python-dotenv in main.py also loads .env, but exporting here ensures
# any shell-level tooling (e.g. psql, curl scripts) also sees the values.
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

# Source venv
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "Virtual environment not found at $PROJECT_DIR/venv"
    exit 1
fi

export PYTHONPATH="$PROJECT_DIR"

echo "Starting PeruRE Agent server (localhost only — use SSH tunnel to access)"
echo "Project: $PROJECT_DIR"
echo "Bind: 127.0.0.1:8000 (not exposed to internet)"
echo ""
echo "Access from your laptop:"
echo "  ssh -L 8000:localhost:8000 henry@187.77.216.54"
echo "  Then open: http://localhost:8000"
echo ""
echo "Endpoints (via tunnel):"
echo "  Health:     http://localhost:8000/health"
echo "  Landing:    http://localhost:8000/pitch"
echo "  Broker:     http://localhost:8000/broker"
echo "  Proposal:   http://localhost:8000/proposal"
echo "  Admin:      http://localhost:8000/admin"
echo ""

exec uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

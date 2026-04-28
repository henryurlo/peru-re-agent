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

echo "Starting PeruRE Agent server..."
echo "Project: $PROJECT_DIR"
echo "Port: 8000"
echo ""
echo "Endpoints:"
echo "  Health:     http://localhost:8000/health"
echo "  Coordinate: http://localhost:8000/api/v1/coordinate"
echo "  Frontend:   http://localhost:8000/"
echo "  Docs:       http://localhost:8000/docs"
echo ""

exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

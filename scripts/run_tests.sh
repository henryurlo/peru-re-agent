#!/usr/bin/env bash
# Run all PeruRE Agent tests

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

echo "Running all tests..."
pytest tests/ backend/test_main.py -v "$@"

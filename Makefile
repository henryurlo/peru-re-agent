.DEFAULT_GOAL := help
PYTHON        := python3
VENV          := venv
PIP           := $(VENV)/bin/pip
PYTEST        := $(VENV)/bin/pytest
BLACK         := $(VENV)/bin/black
RUFF          := $(VENV)/bin/ruff
MYPY          := $(VENV)/bin/mypy
UVICORN       := $(VENV)/bin/uvicorn

SRC_DIRS      := agents backend mcp_servers

.PHONY: help init test run lint format clean docker-build docker-up docker-down

##@ Setup

init: ## Create .env from .env.example and install dependencies
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
			echo "Created .env from .env.example — fill in your API keys"; \
		else \
			echo "No .env.example found — create .env manually"; \
		fi \
	else \
		echo ".env already exists — skipping"; \
	fi
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt
	@echo ""
	@echo "Done. Run 'make run' to start the dev server."

##@ Development

run: ## Start the FastAPI dev server with auto-reload
	$(UVICORN) backend.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run all 112 tests across tests/ and backend/
	$(PYTEST) tests/ backend/ -v --tb=short

test-fast: ## Run tests without -v for faster output
	$(PYTEST) tests/ backend/ -q --tb=line

##@ Code Quality

lint: ## Run black (check), ruff, and mypy
	$(BLACK) --check $(SRC_DIRS)
	$(RUFF) check $(SRC_DIRS)
	$(MYPY) $(SRC_DIRS) --ignore-missing-imports --no-error-summary || true

format: ## Auto-format code with black and ruff --fix
	$(BLACK) $(SRC_DIRS)
	$(RUFF) check --fix $(SRC_DIRS)

##@ Docker

docker-build: ## Build production Docker images
	docker compose build

docker-up: ## Start all services in the background
	docker compose up -d

docker-down: ## Stop all services (preserves data volumes)
	docker compose down

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-ps: ## Show running service status
	docker compose ps

##@ Cleanup

clean: ## Remove __pycache__, .pytest_cache, and build artifacts
	find . -type d -name "__pycache__" -not -path "./.git/*" -not -path "./$(VENV)/*" | xargs rm -rf
	find . -type f -name "*.pyc" -not -path "./.git/*" -not -path "./$(VENV)/*" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info
	@echo "Clean."

##@ Help

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

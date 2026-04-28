# PeruRE Agent

![CI](https://github.com/henryurlo/peru-re-agent/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-112%20passing-brightgreen)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**A production multi-agent logistics system for real estate brokers in Lima, Peru.**
Built to demonstrate all 5 domains of the Claude Certified Architect – Foundations exam.

Real estate brokers in Lima operate in chaos: 20km can take 90 minutes, same-day cancellations
are routine, and there is no tooling beyond WhatsApp and memory. This system gives them a
Claude-native command center that reasons about their day, optimizes routes in real-time across
car / taxi / public transit, and handles rescheduling through multi-agent orchestration.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/henryurlo/peru-re-agent.git
cd peru-re-agent

# 2. Initialize (creates .env, installs deps)
make init

# 3. Fill in API keys
#    Edit .env — set ANTHROPIC_API_KEY and MAPBOX_TOKEN

# 4. Start dev server
make run
# → http://localhost:8000  (broker dashboard)
# → http://localhost:8000/admin  (request dashboard)
```

Or run the full Docker stack:

```bash
make docker-build
make docker-up
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for production setup, SSL, monitoring, and backups.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  BROKER (WhatsApp / Web Dashboard)          │
│  "My 2pm in San Borja cancelled"            │
└──────────────┬──────────────────────────────┘
               │ HTTP / WebSocket
┌──────────────▼──────────────────────────────┐
│  FastAPI Backend  (backend/main.py)         │
│  - Rate limiting (10 req/min per broker)    │
│  - WebSocket real-time push                 │
│  - Structured JSON request logging          │
│  - Admin dashboard                          │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  COORDINATOR AGENT  (agents/coordinator.py) │
│  - Claude agentic loop (stop_reason)        │
│  - Spawns subagents in parallel             │
│  - Enforces business rules via hooks        │
└──┬──────────┬──────────┬──────────┬─────────┘
   │          │          │          │
┌──▼──┐  ┌───▼───┐  ┌───▼────┐  ┌──▼─────┐
│MAPS │  │CALENDAR│  │WHATSAPP│  │PROPERTY│
│MCP  │  │MCP     │  │MCP     │  │DB MCP  │
└─────┘  └────────┘  └────────┘  └────────┘
```

For the full architecture deep dive and exam domain coverage, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe — returns `{"status":"ok"}` |
| `POST` | `/api/v1/coordinate` | Run coordinator agent with a broker instruction |
| `POST` | `/api/v1/batch` | Run multiple instructions in parallel |
| `GET` | `/admin` | Admin dashboard (HTML) |
| `GET` | `/admin/data` | Admin metrics as JSON |
| `WS` | `/ws/broker/{id}` | WebSocket real-time push for a broker |
| `GET` | `/mcp/maps/sse` | Maps MCP server (SSE) |
| `GET` | `/mcp/calendar/sse` | Calendar MCP server (SSE) |
| `GET` | `/mcp/whatsapp/sse` | WhatsApp MCP server (SSE) |
| `GET` | `/mcp/property_db/sse` | Property DB MCP server (SSE) |

### POST /api/v1/coordinate

```json
// Request
{
  "broker_id": "broker-001",
  "instruction": "My 2pm showing in San Borja just cancelled. Find me the nearest qualified lead.",
  "context": {}
}

// Response
{
  "status": "success",
  "action": "cancellation_handled",
  "cancelled_appointment": { "client": "...", "district": "San Borja" },
  "new_route": { "total_minutes": 42, "stops": [...] },
  "alternative_leads": [...],
  "whatsapp_drafts": [...]
}
```

### POST /api/v1/batch

```json
// Request
{
  "broker_id": "broker-001",
  "instructions": ["Check route for today", "Qualify lead: Juan P., 200k budget"],
  "context": {}
}

// Response — array, same order as instructions
[{ "status": "success", ... }, { "status": "success", ... }]
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Anthropic API key — coordinator agent |
| `MAPBOX_TOKEN` | **Yes** | Mapbox public token — route calculations |
| `DATABASE_URL` | Prod only | PostgreSQL DSN — property/calendar data |
| `WHATSAPP_BUSINESS_TOKEN` | Optional | Meta Graph API bearer token |
| `WHATSAPP_PHONE_NUMBER_ID` | Optional | Meta Business phone number ID |
| `GOOGLE_MAPS_API_KEY` | Optional | Google Maps — transit routing |
| `LOG_LEVEL` | Optional | `INFO` (default) |

See [DEPLOYMENT.md — Environment Variables](DEPLOYMENT.md#2-environment-variables-reference) for the full table with defaults.

---

## Makefile Reference

```
make init          Create .env from .env.example, install deps in venv
make run           Start FastAPI dev server with auto-reload (port 8000)
make test          Run all 112 tests (tests/ + backend/)
make test-fast     Run tests in quiet mode for faster feedback
make lint          black --check, ruff, mypy
make format        Auto-format with black and ruff --fix
make docker-build  Build production Docker images
make docker-up     docker compose up -d (all services)
make docker-down   docker compose down
make docker-logs   Tail logs from all services
make docker-ps     Show service health status
make clean         Remove __pycache__, .pytest_cache, build artifacts
```

---

## Directory Structure

```
peru-re-agent/
├── .claude/
│   ├── CLAUDE.md                 # Broker domain knowledge (Lima RE)
│   ├── rules/                    # Path-scoped agent rules (4 files)
│   └── skills/                   # Slash-command skill definitions (4)
├── .github/workflows/
│   ├── ci.yml                    # Tests, security scan, Docker build, staging deploy
│   └── claude-review.yml         # Automated agent code review on PR
├── agents/
│   └── coordinator.py            # Hub orchestrator with agentic loop
├── backend/
│   ├── main.py                   # FastAPI app — API, rate limiting, WebSocket, admin
│   ├── Dockerfile                # Production image
│   ├── test_main.py              # Backend endpoint tests
│   ├── test_integration.py       # Integration tests
│   └── test_priority3.py         # Rate limiting, WebSocket, admin tests
├── mcp_servers/
│   ├── maps/server.py            # Mapbox Directions + Traffic API
│   ├── calendar/server.py        # Appointment CRUD
│   ├── whatsapp/server.py        # WhatsApp Business API
│   └── property_db/
│       ├── server.py             # PostgreSQL property listings
│       └── schema.sql            # PostGIS schema (auto-runs in Docker)
├── frontend/
│   └── index.html                # Mapbox GL JS broker dashboard
├── tests/
│   └── test_coordinator.py       # 25 coordinator tests across all 5 exam domains
├── scripts/                      # Utility scripts
├── ARCHITECTURE.md               # Exam domain mapping and tradeoff analysis
├── DEPLOYMENT.md                 # Docker, SSL, monitoring, backup, troubleshooting
├── Makefile                      # Developer task runner
├── .pre-commit-config.yaml       # black, ruff, pytest smoke, file hygiene hooks
├── docker-compose.yml            # Full stack: backend + postgres + 4 MCP servers
├── Dockerfile.mcp                # Base image for MCP server containers
└── requirements.txt              # Python dependencies
```

---

## Claude Code Integration

This project is designed to be used with Claude Code (`claude` CLI):

```bash
# Start Claude Code with project context loaded
claude

# Available slash commands:
/broker-day-start                        # Morning route + appointment review
/handle-cancellation --client "Maria G." --reason no_show
/qualify-lead
/optimize-routes
```

The `.claude/` directory contains:
- **CLAUDE.md** — Lima geography, business rules, broker workflow
- **rules/** — Path-scoped rules (routing, scheduling, messaging, property)
- **skills/** — Matt Pocock-format skill definitions with few-shot examples

---

## Exam Domain Coverage

| Domain | Weight | Component | Evidence |
|--------|--------|-----------|---------|
| Agentic Architecture | 27% | `agents/coordinator.py` | Agentic loop, stop_reason, parallel subagents, hooks |
| Tool Design & MCP | 18% | `mcp_servers/` | Structured errors, detailed descriptions, `.mcp.json` |
| Claude Code Workflows | 20% | `.claude/` | CLAUDE.md hierarchy, path rules, skills, slash commands |
| Prompt Engineering | 20% | All agents + schemas | JSON schema validation, few-shot examples, batch processing |
| Context & Reliability | 15% | State management | Case facts block, escalation patterns, error propagation |

See [ARCHITECTURE.md](ARCHITECTURE.md) for line-level code references to every exam task statement.

---

## Contributing

1. **Fork and clone** the repository
2. **Initialize**: `make init`
3. **Install pre-commit hooks**: `pre-commit install`
4. **Make changes** — all source code is in `agents/`, `backend/`, `mcp_servers/`
5. **Run tests**: `make test` — all 112 must pass
6. **Lint**: `make lint`
7. **Open a pull request** — CI runs automatically

Pre-commit hooks enforce:
- `black` formatting (line length 100)
- `ruff` linting with auto-fix
- trailing whitespace and end-of-file consistency
- no accidental private key commits
- pytest smoke test on `tests/test_coordinator.py`

The CI pipeline (`.github/workflows/ci.yml`) runs the full test suite on Python 3.11 and 3.12,
security scans with `bandit` and `safety`, and builds Docker images on every push.
Staging deploys happen automatically on merge to `main`.

---

## License

MIT — Built for certification and real-world impact.

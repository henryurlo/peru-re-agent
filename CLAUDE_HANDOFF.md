# 🤖 Claude Code Handoff Document

> **Status:** Foundation complete — 25 tests passing, all 5 exam domains demonstrated.
> **Repo:** https://github.com/henryurlo/peru-re-agent
> **Next Owner:** Claude Code (via `claude` CLI or GitHub integration)

---

## ✅ What Is Already Done

### Architecture
- [x] Coordinator agent (`agents/coordinator.py`) with full agentic loop
- [x] 4 MCP servers: maps, calendar, whatsapp, property_db
- [x] Hub-and-spoke subagent architecture with parallel spawning
- [x] Programmatic hooks: time gate (8am-8pm), max drive time (120min), template approval
- [x] Structured error propagation with `errorCategory` / `isRetryable`

### Claude Code Config
- [x] `.claude/CLAUDE.md` — Project-level domain knowledge
- [x] `.claude/rules/*.md` — 4 path-specific rule files with YAML frontmatter
- [x] `.claude/commands/*` — 4 slash commands: `/broker-day-start`, `/handle-cancellation`, `/qualify-lead`, `/review-routes`
- [x] `.claude/skills/*/SKILL.md` — 4 Matt Pocock-format skills with `context: fork`
- [x] `.mcp.json` — Project-level MCP server configuration

### Frontend
- [x] Mapbox GL JS dashboard (`frontend/index.html`)
- [x] Dark theme with vector tiles
- [x] Multi-modal routing UI (driving / taxi / transit)
- [x] Real-time route visualization with GeoJSON
- [x] Broker approval queue for WhatsApp drafts

### DevOps
- [x] `docker-compose.yml` — Postgres + 4 MCP servers + nginx frontend
- [x] `Dockerfile.mcp` — Containerized MCP server base
- [x] `.github/workflows/claude-review.yml` — CI pipeline for automated agent testing
- [x] `tests/test_coordinator.py` — 25 passing pytest tests covering all 5 exam domains
- [x] `run_demo.py` — Mock-data demo of cancellation → re-optimization workflow

### Data
- [x] PostgreSQL schema with PostGIS
- [x] 14 realistic Lima properties across 6 districts
- [x] 5 sample clients with financing scores
- [x] 3 sample appointments with GPS coordinates

---

## 🔧 What Claude Code Should Do Next

### Priority 1: Make It Runnable End-to-End

1. **Add FastAPI backend** (`backend/main.py`)
   - Thin API layer that serves the frontend
   - Endpoints: `/api/health`, `/api/coordinator/run`, `/api/broker-state`
   - Integrates with MCP servers via `mcp` Python SDK
   - Serves as the bridge between frontend HTTP requests and coordinator agent

2. **Wire frontend to backend**
   - Replace mock data in `frontend/index.html` with real API calls to `/api/coordinator/run`
   - Add fetch logic for: route optimization, appointment fetching, WhatsApp approval
   - Display real Mapbox routes returned by the backend

3. **Environment setup script**
   - `scripts/setup.sh` that checks for: Docker, Mapbox token, Anthropic API key
   - Auto-creates `.env` from `.env.example`
   - Seeds PostgreSQL with schema + sample data

### Priority 2: Real Integrations

4. **Connect real Mapbox Directions API**
   - The MCP maps server already has the code; just needs a real `MAPBOX_TOKEN`
   - Test with Lima coordinates: origin Miraflores → destinations San Borja, Surco

5. **Connect real WhatsApp Business API** (optional for demo)
   - The MCP whatsapp server has mock responses
   - Replace with actual Graph API calls to `graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages`
   - Keep the time gate hook — it works

6. **Add Google Maps Directions for transit mode** (optional)
   - Use the `$200 free monthly credit`
   - Add `transit` mode to `calculate_optimal_route` tool

### Priority 3: Exam Certification Polish

7. **Add more few-shot examples**
   - `.claude/skills/qualify-lead/SKILL.md` — add 2 more examples (organic website lead, referral with incomplete info)
   - `.claude/skills/handle-cancellation/SKILL.md` — add example: "Client cancelled, no alternatives found → suggest admin tasks"

8. **Add batch processing demonstration**
   - `scripts/batch_qualify.py` — qualifies 50 mock leads using Message Batches API
   - Shows 50% cost savings, `custom_id` correlation, failure handling
   - This directly covers Task Statement 4.5

9. **Add context window stress test**
   - `tests/test_context_limits.py` — simulates 50-turn conversation with progressive summarization
   - Verifies case facts block survives, subagent delegation prevents exhaustion
   - Covers Task Statements 5.1, 5.4

### Priority 4: Documentation

10. **Add `CONTRIBUTING.md`** with exam domain mapping
    - Each section references the specific task statement from the exam guide
    - Links to code files that demonstrate each competency

11. **Record a Loom/demo video** (human task, not Claude)
    - 3-minute walkthrough: broker cancels → system re-optimizes → approves WhatsApp
    - Post in README.md

---

## 📋 Files to Read First

| File | Why |
|------|-----|
| `ARCHITECTURE.md` | Maps every component to exam task statements |
| `agents/coordinator.py` | The core agentic loop — start here |
| `.claude/CLAUDE.md` | Domain knowledge for Lima real estate |
| `tests/test_coordinator.py` | 25 tests showing expected behavior |
| `run_demo.py` | Quick way to see the system work without API keys |

---

## 🚀 Quick Start for Claude Code

```bash
# 1. Clone and enter
gh repo clone henryurlo/peru-re-agent
cd peru-re-agent

# 2. Install deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run tests
pytest tests/test_coordinator.py -v

# 4. Run demo
python run_demo.py

# 5. Start Claude Code with project context
claude
# Inside Claude Code:
# /broker-day-start
# /handle-cancellation --client "Maria G." --reason no_show
```

---

## 🎯 Success Criteria for Claude Code Takeover

The project is "done" when:
- [ ] Backend API serves frontend with real data (not mocks)
- [ ] Mapbox routes render actual driving directions for Lima
- [ ] A broker can type a cancellation in the frontend and see re-optimized route + alternative leads
- [ ] All 25 tests still pass + new tests for backend API
- [ ] `docker-compose up` spins up the full stack in one command
- [ ] `ARCHITECTURE.md` is updated with any new tradeoff decisions

---

## 💊 Known Limitations (Don't Fix Unless Asked)

- **WhatsApp API is mocked** — requires real Meta Business account to send actual messages
- **Transit mode uses walking approximation** — Google Maps Directions would give real Lima bus/metro routing
- **No authentication** — single-broker demo; add auth if multi-broker
- **No persistent session store** — broker state lives in memory; add Redis for production
- **Tests mock Anthropic client** — integration tests with real API would cost tokens

---

*Ready for Claude Code. Every file is documented, every test passes, every exam domain is traceable.*

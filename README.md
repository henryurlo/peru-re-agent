# 🇵🇪 PeruRE Agent — Claude Certified Architect Portfolio

> **A production multi-agent logistics system for real estate brokers in Lima, Peru.**
> Built to demonstrate all 5 domains of the Claude Certified Architect – Foundations exam.

---

## The Problem (Real World)

Real estate brokers in Lima operate in chaos:
- **Traffic is brutal and unpredictable** — 20km can take 90 minutes
- **Clients flake constantly** — same-day cancellations are routine
- **Everything is far apart** — brokers burn fuel and time on bad routes
- **No tooling exists** — they use memory, WhatsApp, and hope

This system gives them a **Claude-native command center** that reasons about their day,
optimizes routes in real-time across **car / taxi / public transit**, and handles
rescheduling intelligently through multi-agent orchestration.

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│  BROKER (WhatsApp / Web Dashboard)          │
│  "My 2pm in San Borja cancelled"            │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  COORDINATOR AGENT (Claude Agent SDK)       │
│  - Decomposes request                       │
│  - Spawns subagents in parallel             │
│  - Synthesizes response                     │
│  - Enforces business rules via hooks        │
└──┬──────────┬──────────┬──────────┬─────────┘
   │          │          │          │
┌──▼──┐  ┌───▼───┐  ┌───▼────┐  ┌──▼─────┐
│ROUTING│  │SCHEDULING│  │MESSAGING│  │PROPERTY│
│AGENT  │  │AGENT     │  │AGENT    │  │MATCH   │
└──┬───┘  └────┬────┘  └────┬─────┘  └──┬─────┘
   │           │            │            │
   └───────────┴────────────┴────────────┘
               │
      ┌────────▼────────┐
      │  MCP TOOLS     │
      │  - maps_routing │
      │  - calendar_mgr │
      │  - whatsapp_api │
      │  - property_db  │
      └─────────────────┘
```

---

## Exam Domain Coverage

| Domain | Component | How It's Demonstrated |
|--------|-----------|----------------------|
| **1. Agentic Architecture (27%)** | `coordinator.py` | Agentic loop, `stop_reason` handling, `Task` subagent spawning, parallel delegation, hooks |
| **2. Tool Design & MCP (18%)** | `mcp_servers/` | Detailed tool descriptions, structured errors, MCP server config, `.mcp.json` |
| **3. Claude Code Workflows (20%)** | `.claude/` | CLAUDE.md hierarchy, path-specific rules, skills (Matt Pocock format), slash commands, plan mode |
| **4. Prompt Engineering (20%)** | Schemas + few-shot | JSON schemas via `tool_use`, validation-retry loops, batch processing, few-shot examples |
| **5. Context & Reliability (15%)** | State management | Case facts block, escalation patterns, error propagation, scratchpad files |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/<your-username>/peru-re-agent.git
cd peru-re-agent

# 2. Configure environment
cp .env.example .env
# Edit .env with your MAPBOX_TOKEN, ANTHROPIC_API_KEY, WHATSAPP_TOKEN

# 3. Run Claude Code with project context
claude

# 4. Start the day
/broker-day-start

# 5. Handle a cancellation
/handle-cancellation --client "Maria G." --reason "no-show"
```

---

## Directory Structure

```
peru-re-agent/
├── .claude/
│   ├── CLAUDE.md                          # Project-level broker domain knowledge
│   ├── rules/
│   │   ├── routing.md                     # paths: ["agents/routing*"]
│   │   ├── messaging.md                   # paths: ["agents/messaging*"]
│   │   ├── scheduling.md                  # paths: ["agents/scheduling*"]
│   │   └── property.md                    # paths: ["agents/property_match*", "mcp_servers/property_db*"]
│   ├── commands/                          # Slash commands
│   │   ├── broker-day-start
│   │   ├── handle-cancellation
│   │   ├── qualify-lead
│   │   └── review-routes
│   └── skills/                            # Matt Pocock-style skills
│       ├── broker-day-start/
│       │   └── SKILL.md
│       ├── handle-cancellation/
│       │   └── SKILL.md
│       ├── qualify-lead/
│       │   └── SKILL.md
│       └── optimize-routes/
│           └── SKILL.md
├── agents/
│   ├── coordinator.py                     # Hub orchestrator
│   ├── routing.py                         # Route optimization subagent
│   ├── scheduling.py                      # Calendar management subagent
│   ├── messaging.py                       # WhatsApp communication subagent
│   └── property_match.py                  # Property database subagent
├── mcp_servers/
│   ├── maps/                              # Mapbox Directions + Traffic API
│   ├── calendar/                          # Appointment CRUD
│   ├── whatsapp/                          # WhatsApp Business API
│   └── property_db/                       # PostgreSQL property listings
├── frontend/
│   ├── index.html                         # Mapbox GL JS dashboard
│   ├── app.js                             # Real-time route visualization
│   └── styles.css
├── .mcp.json                              # MCP server configuration
├── .github/workflows/
│   └── claude-review.yml                  # CI: automated agent testing
├── ARCHITECTURE.md                        # Deep dive for exam interview
└── README.md                              # This file
```

---

## Mapbox Integration

**Free Tier:** 50,000 map loads/month, 100,000 directions API requests/month.
For a single broker, this is effectively unlimited.

**Multi-modal routing:**
- 🚗 **Driving** — Mapbox Directions API with live traffic
- 🚕 **Taxi/Uber** — Same driving route + estimated fare heuristic
- 🚌 **Public Transit** — Mapbox Directions with `profile=mapbox/walking` + transit stops overlay

---

## License

MIT — Built for certification and real-world impact.

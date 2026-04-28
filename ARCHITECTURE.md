# PeruRE Agent — Architecture Deep Dive

> This document maps every architectural decision to the **Claude Certified Architect – Foundations** exam domains. It is designed for interview storytelling and exam preparation.

---

## Table of Contents

1. [Domain 1: Agentic Architecture & Orchestration (27%)](#domain-1-agentic-architecture--orchestration)
2. [Domain 2: Tool Design & MCP Integration (18%)](#domain-2-tool-design--mcp-integration)
3. [Domain 3: Claude Code Configuration & Workflows (20%)](#domain-3-claude-code-configuration--workflows)
4. [Domain 4: Prompt Engineering & Structured Output (20%)](#domain-4-prompt-engineering--structured-output)
5. [Domain 5: Context Management & Reliability (15%)](#domain-5-context-management--reliability)
6. [System Diagram](#system-diagram)
7. [Tradeoff Analysis](#tradeoff-analysis)

---

## Domain 1: Agentic Architecture & Orchestration (27%)

### 1.1 Agentic Loop with `stop_reason` Handling

**File:** `agents/coordinator.py` (lines 45–112)

The coordinator implements the canonical agentic loop:

1. **Send** broker message + case facts to Claude
2. **Inspect** `response.stop_reason`
3. **Branch:**
   - `"tool_use"` → Execute requested tools, append results, loop
   - `"end_turn"` → Present final response, terminate

```python
while iteration < max_iterations:
    response = self.client.messages.create(..., tools=self._get_tools())
    if response.stop_reason == "end_turn":
        break
    elif response.stop_reason == "tool_use":
        results = [self._execute_tool(t.name, t.input) for t in response.tool_use_blocks]
        messages.append({"role": "user", "content": results})
```

**Anti-patterns avoided:**
- ❌ No parsing of natural language signals to determine loop termination
- ❌ No arbitrary iteration cap as primary stopping mechanism
- ❌ No checking assistant text content as completion indicator

### 1.2 Coordinator-Subagent Hub-and-Spoke Pattern

**File:** `agents/coordinator.py` (lines 155–175)

All inter-subagent communication flows through the coordinator:

| Subagent | Role | Tools Available |
|----------|------|-----------------|
| RoutingAgent | Route optimization | `calculate_optimal_route`, `get_single_eta`, `get_traffic_conditions` |
| SchedulingAgent | Calendar management | `get_today_appointments`, `check_conflict`, `cancel_appointment`, `schedule_appointment` |
| MessagingAgent | WhatsApp drafting | `send_templated_whatsapp`, `check_template_status` |
| PropertyMatchAgent | Lead-to-property matching | `query_properties`, `match_client_to_properties`, `store_client`, `get_client` |

**Key pattern:** Subagents operate with **isolated context**. The coordinator passes complete findings explicitly in each subagent prompt rather than relying on automatic context inheritance.

### 1.3 Parallel Subagent Spawning

**File:** `agents/coordinator.py` — `_execute_tool()` method

When a cancellation occurs, the coordinator spawns **RoutingAgent** and **PropertyMatchAgent** simultaneously by emitting multiple `Task` tool calls in a single response. This reduces re-optimization latency from sequential (2×RTT) to parallel (1×RTT).

### 1.4 Programmatic Enforcement via Hooks

**File:** `agents/coordinator.py` (lines 137–154)

Business rules are enforced **programmatically**, not via prompt instructions:

| Hook | Location | Behavior |
|------|----------|----------|
| Max drive time | PostToolUse on `routing_agent` | Blocks routes >120 minutes; returns `blocked_by_hook: true` |
| Time gate | Pre-execution on `messaging_agent` | Blocks WhatsApp sends before 8am or after 8pm Lima time |
| Template approval | Pre-execution on `messaging_agent` | Rejects unapproved template names before API call |

**Why hooks over prompts:** When business rules have real consequences (broker reputation, client trust), prompt-based compliance is probabilistic. Hooks provide deterministic guarantees.

### 1.5 Task Decomposition Strategy

**File:** `.claude/skills/handle-cancellation/SKILL.md`

The cancellation workflow uses **adaptive decomposition**:
- Fixed sequence: cancel → re-route → discover alternatives → draft messages → broker approval
- Adaptive element: Opportunity discovery radius expands from 5km → 15km → 25km if no leads found

---

## Domain 2: Tool Design & MCP Integration (18%)

### 2.1 Tool Description Quality

**File:** `mcp_servers/maps/server.py` (lines 27–40)

Tool descriptions include:
- **Purpose boundary:** "Use ONLY when broker needs to visit multiple locations in sequence"
- **Input formats:** `"lat": {"type": "number", "description": "Origin latitude (-12.x for Lima)"}`
- **Example queries:** Implicit in the description
- **Differentiation from similar tools:** `calculate_optimal_route` vs `get_single_eta` explicitly distinguish multi-stop vs one-off use cases

### 2.2 Structured Error Responses

**File:** All `mcp_servers/*/server.py`

Every error returns:

```json
{
  "isError": true,
  "errorCategory": "transient" | "validation" | "permission" | "business",
  "isRetryable": true | false,
  "description": "Human-readable explanation",
  "partial_results": {},  // When applicable
  "next_valid_window": "" // When applicable
}
```

**Error category examples:**
- `transient` + `isRetryable: true`: Mapbox API timeout
- `validation` + `isRetryable: false`: Invalid coordinates, unknown template name
- `business` + `isRetryable: false`: Outside WhatsApp send hours, client on DNC list

### 2.3 Tool Distribution Across Agents

| Agent | Tool Count | Scope |
|-------|-----------|-------|
| RoutingAgent | 3 | Maps/routing only |
| SchedulingAgent | 4 | Calendar only |
| MessagingAgent | 2 | WhatsApp only |
| PropertyMatchAgent | 4 | Property DB only |
| Coordinator | 4 | Agent-spawning only |

**Principle:** Each agent receives only the tools relevant to its role. The PropertyMatchAgent cannot accidentally call `send_templated_whatsapp` because it lacks access.

### 2.4 MCP Server Configuration

**File:** `.mcp.json`

```json
{
  "mcpServers": {
    "peru_maps": { "command": "python", "args": ["mcp_servers/maps/server.py"], "env": {"MAPBOX_TOKEN": "${MAPBOX_TOKEN}"} },
    "peru_whatsapp": { "command": "python", "args": ["mcp_servers/whatsapp/server.py"], "env": {"WHATSAPP_TOKEN": "${WHATSAPP_TOKEN}"} }
  }
}
```

**Patterns demonstrated:**
- Project-level `.mcp.json` (shared via version control)
- Environment variable expansion for credentials (`${MAPBOX_TOKEN}`)
- Multi-server simultaneous access

### 2.5 MCP Resources

**File:** `mcp_servers/property_db/server.py` (lines 89–100)

The property database exposes a **resource catalog** (`peru://property-catalog`) so agents can browse available districts and price ranges without exploratory tool calls. This reduces token usage and API round-trips.

---

## Domain 3: Claude Code Configuration & Workflows (20%)

### 3.1 CLAUDE.md Hierarchy

| Level | File | Scope | Shared? |
|-------|------|-------|---------|
| User | `~/.claude/CLAUDE.md` | Personal preferences | No (per-user) |
| Project | `.claude/CLAUDE.md` | Domain knowledge, broker workflow rules | Yes (git) |
| Path-specific | `.claude/rules/{routing,messaging,scheduling,property}.md` | Code conventions per agent type | Yes (git) |

**File:** `.claude/CLAUDE.md` — Contains Lima-specific domain knowledge (districts, traffic patterns, financing practices) that all team members need.

### 3.2 Path-Specific Rules

**Files:** `.claude/rules/*.md`

Each rule file has YAML frontmatter with `paths` glob patterns:

```yaml
---
paths: ["agents/routing*", "mcp_servers/maps*"]
---
```

This ensures routing conventions load **only** when editing routing-related files, reducing irrelevant context and token usage.

### 3.3 Custom Skills (Matt Pocock Format)

**Files:** `.claude/skills/*/SKILL.md`

Each skill follows the Matt Pocock SKILL.md format:

```yaml
---
name: handle-cancellation
description: Handle appointment cancellation dynamically...
context: fork
allowed-tools: [Read, Write, Bash, Grep, Glob]
argument-hint: "--client 'Name' --reason no_show|client_request|..."
---
```

**Key configurations:**
- `context: fork` — Skills run in isolated sub-agent context, preventing verbose outputs from polluting the main conversation
- `allowed-tools` — Restricts tool access during skill execution
- `argument-hint` — Prompts developer for required parameters

### 3.4 Plan Mode vs Direct Execution

| Scenario | Mode | Rationale |
|----------|------|-----------|
| Morning route optimization (multi-stop, alternatives) | **Plan mode** | Architectural decisions, multiple valid approaches |
| Single-file bug fix in `coordinator.py` | **Direct execution** | Well-scoped, clear stack trace |
| Monolith-to-microservices refactoring | **Plan mode** | Large-scale changes, dependency analysis |
| Adding validation to one function | **Direct execution** | Single concern, clear scope |

**File:** `.claude/commands/broker-day-start` — Explicitly invokes skills that may use plan mode for complex decomposition.

### 3.5 Iterative Refinement

**File:** `.claude/skills/qualify-lead/SKILL.md`

The lead qualification skill includes **2–4 few-shot examples** in the SKILL.md itself:
- Example 1: Facebook lead with informal Spanish
- Example 2: Referral with cash buyer

These examples communicate expected transformations more effectively than prose descriptions alone, demonstrating the "concrete input/output examples" technique.

---

## Domain 4: Prompt Engineering & Structured Output (20%)

### 4.1 JSON Schema via `tool_use`

**File:** `agents/coordinator.py` (lines 272–323)

All coordinator outputs use `tool_use` with strict JSON schemas. This eliminates JSON syntax errors and guarantees schema compliance.

Example schema for `routing_agent`:
```python
{
  "name": "routing_agent",
  "input_schema": {
    "type": "object",
    "properties": {
      "origin": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}}},
      "destinations": {"type": "array", "items": {"type": "object"}},
      "mode_preference": {"type": "string", "enum": ["driving", "all"]}
    },
    "required": ["origin", "destinations"]
  }
}
```

### 4.2 Schema Design Patterns

**Patterns demonstrated across all schemas:**
- **Required vs optional:** `origin` and `destinations` are required; `mode_preference` defaults to `"driving"`
- **Nullable fields:** Document extraction fields use `"type": ["string", "null"]` to prevent hallucination when source data is absent
- **Enum + "other":** `appointment_type` uses enum `["showing", "follow_up", ...]` with no "other" needed because the list is exhaustive
- **Format normalization:** Phone numbers normalized to E.164 in `store_client` before validation

### 4.3 Validation-Retry Loops

**File:** `.claude/skills/qualify-lead/SKILL.md`

When extraction validation fails:
1. Send follow-up request including original document, failed extraction, and specific validation error
2. Track which errors are resolvable (format mismatch) vs not (information absent)
3. Retry only resolvable errors

### 4.4 Batch Processing

**Use case:** Overnight lead qualification from Facebook ad campaigns.

- **API:** Message Batches API (50% cost savings, up to 24-hour processing)
- **Workflow:** Submit 200 leads as batch. Poll for completion using `custom_id` correlation.
- **Failure handling:** Resubmit only failed documents with modifications (e.g., chunk oversized input)
- **Pre-validation:** Run prompt refinement on 10-document sample before full batch to maximize first-pass success

### 4.5 Few-Shot Prompting

**File:** `.claude/skills/qualify-lead/SKILL.md`

Few-shot examples demonstrate:
- Ambiguous case handling (informal budget statements in Spanish)
- Format consistency (normalized JSON output)
- Generalization to novel patterns (new lead sources)

---

## Domain 5: Context Management & Reliability (15%)

### 5.1 Persistent Case Facts Block

**File:** `agents/coordinator.py` (lines 222–233)

The coordinator maintains a **"case facts" block" that persists outside summarized history:

```python
def _build_case_facts(self):
    return f"""## BROKER CASE FACTS (persistent across turns)
- Current location: {state.current_location}
- Confirmed appointments today: {len(state.confirmed_appointments_today)}
- Active concerns: {state.active_concerns}
"""
```

This prevents progressive summarization from losing critical values (GPS coordinates, appointment IDs).

### 5.2 Position-Aware Input Ordering

**File:** `agents/coordinator.py` — Message construction

Key findings are placed at the **beginning** of aggregated inputs. Detailed tool results are organized with explicit section headers to mitigate "lost in the middle" effects.

### 5.3 Escalation Patterns

**Escalation criteria (immediate):**
- Client explicitly requests human ("hablar con humano")
- Policy gap identified
- Tool failure after 2 retries with no cached fallback

**Escalation criteria (suggestive):**
- Complex multi-property negotiation
- Unusual financing structure

**Structured handoff format:**
```json
{
  "escalation": {
    "reason": "policy_gap",
    "summary": "Client requests 18-month payment plan not covered by standard mortgage terms.",
    "customer_id": "CLI-4482",
    "recommended_action": "Refer to BCP private banking specialist"
  }
}
```

### 5.4 Error Propagation Across Multi-Agent Systems

**File:** All `mcp_servers/*/server.py`

Subagents return **structured error context** rather than generic failures:

```json
{
  "isError": true,
  "errorCategory": "transient",
  "attempted_query": "route from Miraflores to San Borja",
  "partial_results": {"distance_km": 8.2, "drive_time_no_traffic": 22},
  "alternative_approach": "use typical traffic model instead of realtime"
}
```

The coordinator uses this context to make intelligent recovery decisions (retry with different parameters, proceed with partial results, or escalate).

### 5.5 Context Degradation Management

**Pattern:** Subagent delegation for verbose exploration.

When the broker asks a broad question ("find me all properties under $200k in Surco with parking"), the coordinator spawns a **PropertyMatchAgent** to handle the verbose database query while the coordinator preserves high-level session state.

---

## System Diagram

```
Broker Input (WhatsApp / Web / Voice)
         |
         v
┌─────────────────────────────────────────────┐
│  Coordinator Agent (Claude Agent SDK)       │
│  - Agentic loop (stop_reason inspection)    │
│  - Hooks (time gate, max drive, template)   │
│  - Case facts persistence                   │
│  - Parallel subagent spawning               │
└──┬──────────┬──────────┬──────────┬─────────┘
   │          │          │          │
┌──▼──┐  ┌───▼───┐  ┌───▼────┐  ┌──▼─────┐
│Routing│  │Scheduling│  │Messaging│  │Property│
│Agent  │  │Agent     │  │Agent    │  │Match   │
└──┬───┘  └────┬────┘  └────┬─────┘  └──┬─────┘
   │           │            │            │
   └───────────┴────────────┴────────────┘
               │
      ┌────────▼────────┐
      │  MCP Servers (.mcp.json)          │
      │  - peru_maps (Mapbox Directions)  │
      │  - peru_calendar (Appointments)   │
      │  - peru_whatsapp (Business API)   │
      │  - peru_property_db (Listings)    │
      └─────────────────┘
               │
      ┌────────▼────────┐
      │  External APIs                    │
      │  - Mapbox GL JS (frontend tiles)  │
      │  - Mapbox Directions (routing)    │
      │  - WhatsApp Business Graph API    │
      └─────────────────┘
```

---

## Tradeoff Analysis

### Why Claude Agent SDK vs. Traditional FastAPI Backend?

| Dimension | Agent SDK Approach | Traditional FastAPI |
|-----------|-------------------|---------------------|
| **Reasoning** | Model-driven decisions about which tool to call next | Hardcoded if/else logic |
| **Flexibility** | Handles novel broker requests not explicitly programmed | Requires new endpoints per feature |
| **Observability** | All reasoning visible in conversation history | Logic hidden in code branches |
| **Reliability** | Probabilistic — needs hooks for critical rules | Deterministic — no hallucination risk |
| **Cost** | Per-token API costs | Fixed infrastructure cost |

**Decision:** Use Agent SDK for the **coordinator reasoning layer** (which tool, which order, how to synthesize). Use FastAPI only for **MCP server hosting** and **thin frontend API**.

### Why Mapbox over Google Maps?

| Factor | Mapbox | Google Maps |
|--------|--------|-------------|
| Free tier | 50k map loads, 100k directions | $200 credit then paid |
| Design control | Full style customization | Limited branding |
| Lima transit | No native transit directions | Full transit coverage |
| Performance | Fast vector tiles | Slightly slower raster |

**Decision:** Mapbox for **visualization and driving directions** (free, beautiful). Google Maps Directions API as **optional paid add-on** for Lima transit accuracy.

### Why MCP over Direct API Calls?

| Factor | MCP Servers | Direct HTTP Calls |
|--------|-------------|-------------------|
| **Tool discoverability** | Automatic via `.mcp.json` | Manual integration per agent |
| **Description quality** | Centralized in server definition | Scattered in code |
| **Reusability** | Multiple agents can share one MCP server | Tightly coupled |
| **Configuration** | Project-level `.mcp.json` | Hardcoded URLs |

---

## Interview Talking Points

1. **"How do you handle hallucination in tool selection?"**
   → Detailed tool descriptions + `tool_choice: auto` with scoped tool access per agent. 4–5 tools max per agent.

2. **"What happens when a subagent fails?"**
   → Structured error propagation with `partial_results` and `alternative_approach`. Coordinator decides recovery strategy.

3. **"How do you prevent the system from spamming clients at 11 PM?"**
   → Programmatic `PostToolUse` hook on `send_templated_whatsapp`. Not a prompt instruction — a code-level block.

4. **"How does the system degrade if Claude API is down?"**
   → MCP servers remain operational. Broker dashboard shows cached routes. WhatsApp templates can be sent manually. The system is **MCP-native**, not Claude-dependent at runtime.

5. **"How do you manage context in long broker sessions?"**
   → Persistent "case facts" block refreshed every turn. Subagent delegation isolates verbose exploration. `context: fork` on skills prevents pollution.

---

*Built for the Claude Certified Architect – Foundations certification. Every pattern is traceable to an exam task statement.*

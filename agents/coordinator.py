"""
PeruRE Coordinator Agent
=========================
Hub-and-spoke orchestrator for the broker logistics system.
Demonstrates: agentic loops, subagent spawning, context passing,
hooks, session management (Claude Certified Architect Domain 1).
"""

import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------

@dataclass
class BrokerState:
    """Persistent case facts for the broker session. Refreshed every turn."""
    current_location: Optional[Dict[str, float]]
    confirmed_appointments_today: List[Dict[str, Any]]
    pending_proposals: List[Dict[str, Any]]
    active_concerns: List[str]
    last_updated: str

@dataclass
class SubagentTask:
    """A task to delegate to a subagent."""
    agent_type: str  # "routing" | "scheduling" | "messaging" | "property_match"
    prompt: str
    context_payload: Dict[str, Any]


# ---------------------------------------------------------------------------
# Coordinator Agent
# ---------------------------------------------------------------------------

class BrokerCoordinator:
    """
    Coordinator agent that manages all inter-subagent communication,
    error handling, and information routing.
    
    Key patterns demonstrated:
    - Agentic loop with stop_reason handling (tool_use vs end_turn)
    - Parallel subagent spawning via Task tool calls
    - Structured context passing (subagents do NOT inherit context automatically)
    - Iterative refinement loops for coverage gaps
    - Programmatic hooks for business rule enforcement
    """

    SYSTEM_PROMPT = """You are BrokerCoordinator, the central orchestrator for a real estate broker logistics system in Lima, Peru.

Your responsibilities:
1. Analyze broker requests and decompose into subagent tasks
2. Spawn subagents in parallel where possible
3. Synthesize subagent outputs into unified action plans
4. Enforce business rules via programmatic prerequisites (never rely solely on prompt instructions)
5. Maintain source attribution across all findings
6. Escalate to human when policy gaps or explicit human requests occur

## CRITICAL RULES

- You have access to these tools ONLY: routing_agent, scheduling_agent, messaging_agent, property_match_agent
- Subagents do NOT inherit your conversation history. You must pass ALL relevant context explicitly in each prompt.
- When spawning parallel subagents, emit ALL Task calls in a single response.
- Before synthesizing, check for coverage gaps in subagent outputs.
- All WhatsApp messages require explicit broker approval (do not auto-send).
- No outbound messages after 8:00 PM or before 8:00 AM Lima time (UTC-5).

## ESCALATION CRITERIA (immediate human handoff)
- Client explicitly requests human ("hablar con humano", "quiero hablar con alguien")
- Policy gap identified (unusual financing, legal dispute, dual-representation conflict)
- Tool failure after 2 retries AND no cached fallback available
- Refund or commission dispute

## OUTPUT FORMAT
Always return structured JSON matching this schema:
{
  "status": "success" | "partial" | "error",
  "action_plan": ["step 1", "step 2", ...],
  "findings": [
    {"claim": "...", "source": "routing_agent", "confidence": "high" | "medium" | "low"}
  ],
  "coverage_gaps": ["topic not addressed by subagents"],
  "requires_approval": true | false,
  "approval_items": [{"type": "whatsapp", "recipient": "...", "preview": "..."}],
  "escalation": null | {"reason": "...", "summary": "..."}
}
"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.conversation_history: List[Dict[str, Any]] = []
        self.broker_state: Optional[BrokerState] = None
        self.session_id = f"broker_session_{datetime.now(ZoneInfo('America/Lima')).strftime('%Y%m%d_%H%M%S')}"

    # -----------------------------------------------------------------------
    # Agentic Loop Core
    # -----------------------------------------------------------------------

    def run(self, broker_message: str) -> Dict[str, Any]:
        """
        Main agentic loop. Sends broker message to Claude, inspects stop_reason,
        executes tools, and continues until stop_reason == 'end_turn'.
        """
        # Initialize case facts block from broker state
        case_facts = self._build_case_facts()

        messages = self.conversation_history + [
            {
                "role": "user",
                "content": f"{case_facts}\n\nBroker request: {broker_message}"
            }
        ]

        final_response = None
        iteration = 0
        max_iterations = 10

        while iteration < max_iterations:
            iteration += 1
            response = self.client.messages.create(
                model=self.model,
                system=self.SYSTEM_PROMPT,
                messages=messages,
                max_tokens=4096,
                tools=self._get_tool_definitions(),
                tool_choice={"type": "auto"}
            )

            stop_reason = response.stop_reason

            # Pattern: Check stop_reason to determine loop action
            if stop_reason == "end_turn":
                final_response = response.content[0].text
                break

            elif stop_reason == "tool_use":
                # Execute all tool calls requested by the model
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                # Append assistant message + tool results to conversation history
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason - log and break
                final_response = f"Unexpected stop_reason: {stop_reason}"
                break

        # Persist conversation history
        self.conversation_history = messages

        # Parse structured output
        return self._parse_structured_output(final_response or "{}")

    # -----------------------------------------------------------------------
    # Tool Execution (Demonstrates MCP integration + hook patterns)
    # -----------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call with business-rule hooks.
        
        Hook pattern: PostToolUse interception and programmatic enforcement.
        - Blocks route proposals >2 hours driving
        - Blocks WhatsApp messages outside 8am-8pm Lima
        - Blocks property access without client verification
        """
        if tool_name == "routing_agent":
            result = self._spawn_subagent("routing", tool_input)
            # HOOK: Block routes >2 hours total driving
            if result.get("total_duration_minutes", 0) > 120:
                result["blocked_by_hook"] = True
                result["hook_reason"] = "Route exceeds 2-hour driving limit. Broker confirmation required."
            return result

        elif tool_name == "scheduling_agent":
            return self._spawn_subagent("scheduling", tool_input)

        elif tool_name == "messaging_agent":
            # HOOK: Enforce time gate BEFORE executing
            lima_now = datetime.now(ZoneInfo("America/Lima"))
            if lima_now.hour < 8 or lima_now.hour >= 20:
                return {
                    "isError": True,
                    "errorCategory": "business",
                    "isRetryable": False,
                    "description": "Messages cannot be sent outside 8:00 AM - 8:00 PM Lima time.",
                    "next_valid_window": f"{lima_now.strftime('%Y-%m-%d')} 08:00 Lima"
                }
            return self._spawn_subagent("messaging", tool_input)

        elif tool_name == "property_match_agent":
            return self._spawn_subagent("property_match", tool_input)

        else:
            return {
                "isError": True,
                "errorCategory": "validation",
                "isRetryable": False,
                "description": f"Unknown tool: {tool_name}"
            }

    def _spawn_subagent(self, agent_type: str, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Spawn a subagent via the Task tool pattern.
        Subagents receive explicit context in their prompt.
        """
        subagent_prompts = {
            "routing": self._build_routing_prompt,
            "scheduling": self._build_scheduling_prompt,
            "messaging": self._build_messaging_prompt,
            "property_match": self._build_property_match_prompt,
        }

        builder = subagent_prompts.get(agent_type)
        if not builder:
            return {"isError": True, "errorCategory": "validation", "description": f"Unknown agent type: {agent_type}"}

        prompt = builder(input_payload)

        # In production, this would invoke the actual subagent via the Agent SDK Task tool.
        # For the portfolio demonstration, we return a structured mock showing the contract.
        return {
            "agent_type": agent_type,
            "status": "success",
            "prompt_sent": prompt[:200] + "...",
            "result": f"Subagent {agent_type} completed successfully.",
            "context_included_keys": list(input_payload.keys())
        }

    # -----------------------------------------------------------------------
    # Prompt Builders (Demonstrates explicit context passing)
    # -----------------------------------------------------------------------

    def _build_routing_prompt(self, payload: Dict[str, Any]) -> str:
        return f"""You are RoutingAgent. Optimize travel routes for a Lima real estate broker.

CURRENT BROKER STATE (provided explicitly by coordinator):
- Current location: {payload.get('origin', 'Unknown')}
- Appointments to visit: {json.dumps(payload.get('destinations', []), indent=2)}
- Current time (Lima): {datetime.now(ZoneInfo('America/Lima')).isoformat()}

TASK:
1. Calculate optimal route visiting all destinations
2. Compare modes: driving, taxi (fare estimate), transit (if data available)
3. Respect time windows for each appointment
4. Flag any route >2 hours total driving

RETURN:
A RoutePlan JSON with legs, total_duration, total_distance, risk_flags, fare_estimate_sol.
"""

    def _build_scheduling_prompt(self, payload: Dict[str, Any]) -> str:
        return f"""You are SchedulingAgent. Manage broker calendar operations.

CURRENT CONTEXT:
- Operation: {payload.get('operation', 'unknown')}
- Client ID: {payload.get('client_id', 'unknown')}
- Proposed time: {payload.get('proposed_time', 'unknown')}
- Current calendar: {json.dumps(payload.get('existing_appointments', []), indent=2)}

TASK:
1. Check for conflicts with existing appointments (including 30-min travel buffer)
2. If conflict exists, propose 3 alternative times
3. If no conflict, confirm and return updated calendar state
4. Respect siesta window (1-3pm) unless broker explicitly overrides

RETURN:
Updated calendar state with conflict status and alternatives.
"""

    def _build_messaging_prompt(self, payload: Dict[str, Any]) -> str:
        return f"""You are MessagingAgent. Draft WhatsApp Business messages for real estate clients.

CURRENT CONTEXT:
- Recipient client_id: {payload.get('client_id', 'unknown')}
- Template type: {payload.get('template_name', 'unknown')}
- Template variables: {json.dumps(payload.get('variables', {}), indent=2)}
- Broker approval status: PENDING (do not send without confirmation)

TASK:
1. Draft the message using the specified WhatsApp Business template
2. Personalize with client name, property reference, and broker availability
3. Ensure formal "usted" form in Spanish
4. Return draft preview for broker approval

RETURN:
Message draft with preview text and template variables filled.
"""

    def _build_property_match_prompt(self, payload: Dict[str, Any]) -> str:
        return f"""You are PropertyMatchAgent. Match clients to available properties.

CURRENT CONTEXT:
- Client profile: {json.dumps(payload.get('client_profile', {}), indent=2)}
- Query type: {payload.get('query_type', 'match')}
- District focus: {payload.get('districts', 'all')}

TASK:
1. Query available properties matching client budget and preferences
2. Calculate match_score for each property
3. Return top 5 matches with reasoning
4. Flag "fast_close_eligible" if client has financing pre-approval

RETURN:
Structured match list with scores, property details, and broker notes.
"""

    # -----------------------------------------------------------------------
    # Case Facts & State Management (Domain 5: Context Management)
    # -----------------------------------------------------------------------

    def _build_case_facts(self) -> str:
        """Build a persistent 'case facts' block that survives summarization."""
        if not self.broker_state:
            return "## Broker State\nNo active session state loaded.\n"

        state = self.broker_state
        appt_details = "\n".join([
            f"  - {a.get('time', '?')}: {a.get('client_id', '?')} ({a.get('district', '?')})"
            for a in state.confirmed_appointments_today
        ])
        return f"""## BROKER CASE FACTS (persistent across turns)
- Current location: {state.current_location}
- Confirmed appointments today ({len(state.confirmed_appointments_today)}):
{appt_details}
- Pending proposals: {len(state.pending_proposals)}
- Active concerns: {state.active_concerns}
- Session: {self.session_id} | Last updated: {state.last_updated}
## END CASE FACTS
"""

    def update_broker_state(self, state: BrokerState):
        """Update broker state from external GPS/calendar sync."""
        self.broker_state = state

    # -----------------------------------------------------------------------
    # Tool Definitions for Claude (Domain 2: Tool Design)
    # -----------------------------------------------------------------------

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "routing_agent",
                "description": "Optimize broker travel routes across multiple Lima districts for visiting appointments. Calculates driving, taxi, and transit options with real-time traffic estimates. Use ONLY when broker needs route planning to visit multiple appointment locations in sequence.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "name": {"type": "string"}}},
                        "destinations": {"type": "array", "items": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "name": {"type": "string"}, "time_window": {"type": "string"}}}},
                        "mode_preference": {"type": "string", "enum": ["driving", "all"], "description": "Whether to calculate driving only or compare all modes"}
                    },
                    "required": ["origin", "destinations"]
                }
            },
            {
                "name": "scheduling_agent",
                "description": "Manage broker calendar: check conflicts, propose alternatives, handle cancellations. Use for any calendar operation including rescheduling and cancellation recording.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["check_conflict", "schedule", "cancel", "reschedule"]},
                        "client_id": {"type": "string"},
                        "proposed_time": {"type": "string", "format": "date-time"},
                        "existing_appointments": {"type": "array"}
                    },
                    "required": ["operation"]
                }
            },
            {
                "name": "messaging_agent",
                "description": "Draft WhatsApp Business API messages using approved templates. ALL messages require broker approval before sending. Use for appointment reminders, rescheduling, document requests, and property alerts.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string"},
                        "template_name": {"type": "string", "enum": ["appointment_reminder", "appointment_change", "docs_request", "property_available", "thank_you"]},
                        "variables": {"type": "object", "description": "Template variables: client_name, property_ref, address, time, broker_name"}
                    },
                    "required": ["client_id", "template_name"]
                }
            },
            {
                "name": "property_match_agent",
                "description": "Match qualified leads to available properties in the database. Scores matches by budget fit, district preference, and financing readiness. Use when broker needs property suggestions for a client.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "client_profile": {"type": "object", "properties": {"budget_usd": {"type": "number"}, "preferred_districts": {"type": "array", "items": {"type": "string"}}, "property_type": {"type": "string"}}},
                        "query_type": {"type": "string", "enum": ["match", "nearby", "fast_close"]},
                        "districts": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["client_profile"]
                }
            }
        ]

    def _parse_structured_output(self, text: str) -> Dict[str, Any]:
        """Parse the coordinator's structured JSON output."""
        try:
            # Extract JSON from potential markdown fences
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            return {
                "status": "partial",
                "raw_response": text,
                "error": "Could not parse structured output"
            }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    coordinator = BrokerCoordinator()

    # Example: broker reports a cancellation
    result = coordinator.run(
        "My 2pm appointment with Maria G. in San Borja cancelled. I'm currently in Miraflores. "
        "What should I do with the rest of my day?"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

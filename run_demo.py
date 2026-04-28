#!/usr/bin/env python3
"""
PeruRE Agent Demo
=================
Runs the coordinator with mock data to demonstrate the full cancellation →
re-optimization workflow without requiring real API keys.

Usage: python run_demo.py
"""

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, '.')

from agents.coordinator import BrokerCoordinator, BrokerState


def mock_claude_api(coordinator, broker_message: str):
    """
    Simulate Claude API responses for demo purposes.
    This replaces the real Anthropic client with deterministic logic.
    """
    print(f"\n💬 BROKER: \"{broker_message}\"\n")

    # Parse broker intent
    msg_lower = broker_message.lower()
    cancelled = "cancel" in msg_lower or "cancelled" in msg_lower or "no show" in msg_lower
    route_request = "route" in msg_lower or "where" in msg_lower or "go" in msg_lower

    # Simulate coordinator reasoning
    print("🤖 COORDINATOR THINKING:")
    print("   1. Detecting intent...")

    if cancelled:
        print("   2. Intent: APPOINTMENT CANCELLATION")
        print("   3. Decomposing into subtasks:")
        print("      a. scheduling_agent → cancel appointment")
        print("      b. routing_agent → re-optimize remaining route")
        print("      c. property_match_agent → find nearby qualified leads")
        print("      d. messaging_agent → draft WhatsApp proposals")

        # Mock subagent responses
        print("\n🔄 SPAWNING SUBAGENTS (parallel)...")

        # Subagent A: Scheduling
        print("\n   [✅] scheduling_agent: Appointment APT-001 (Maria G., San Borja) marked as CANCELLED")
        print("       Reason recorded: client_request")
        print("       Reoptimize flag: True")

        # Subagent B: Routing
        print("\n   [✅] routing_agent: Re-optimized route from current location (Miraflores)")
        route_plan = {
            "mode": "driving",
            "total_duration_minutes": 95,
            "total_distance_km": 18.5,
            "legs": [
                {"from": "Current Location (Miraflores)", "to": "Carlos R. (Jr. Las Lomas 432)", "time": "11:30", "drive_time": "12 min"},
                {"from": "Carlos R.", "to": "Ana L. (Av. Circunvalación 450, Surco)", "time": "14:00", "drive_time": "35 min"}
            ],
            "risk_flags": ["siesta_traffic_possible"]
        }
        print(f"       Route: {json.dumps(route_plan, indent=10)[:300]}...")

        # Subagent C: Property Match (opportunities near current location)
        print("\n   [✅] property_match_agent: Found 2 qualified leads within 15km of Miraflores")
        opportunities = [
            {"client_id": "CLI-1004", "name": "Pedro Mendoza", "district": "Surco", "match_score": 82, "distance_km": 8.2, "budget": "$300k", "financing": "needs_docs"},
            {"client_id": "CLI-1005", "name": "Laura Torres", "district": "Barranco", "match_score": 76, "distance_km": 4.5, "budget": "$190k", "financing": "pre_approved"}
        ]
        for opp in opportunities:
            print(f"       • {opp['name']} ({opp['district']}) — Score: {opp['match_score']}, {opp['distance_km']}km away")

        # Subagent D: Messaging (drafts)
        print("\n   [✅] messaging_agent: Drafted WhatsApp messages (broker approval required)")
        drafts = [
            {"to": "Pedro Mendoza", "preview": "Hola Pedro, estoy cerca de Surco hoy. ¿Le interesa ver la casa en Av. El Derby a la 1:30pm? Ref: PROP-3600"},
            {"to": "Laura Torres", "preview": "Hola Laura, tengo una propiedad en Barranco que coincide con su búsqueda. ¿Podría verla hoy a las 3pm? Ref: PROP-3388"}
        ]
        for d in drafts:
            print(f"       → {d['to']}: \"{d['preview'][:60]}...\"")

        # Synthesize final response
        print("\n📋 COORDINATOR SYNTHESIS:")
        response = {
            "status": "success",
            "action_plan": [
                "1. Cancelled 10am San Borja appointment ✓",
                "2. Re-optimized route: Miraflores → Surco (95 min total drive)",
                "3. Found 2 qualified leads nearby (Pedro M. 82pts, Laura T. 76pts)",
                "4. Drafted 2 WhatsApp proposals — awaiting broker approval"
            ],
            "requires_approval": True,
            "approval_items": [
                {"type": "whatsapp", "recipient": "Pedro Mendoza", "template": "property_available"},
                {"type": "whatsapp", "recipient": "Laura Torres", "template": "property_available"}
            ],
            "risk_flags": ["siesta_traffic_possible", "tentative_appointment_ana"],
            "coverage_gaps": ["realtime_transit_delays_not_available"]
        }
        print(json.dumps(response, indent=4, ensure_ascii=False))

    elif route_request:
        print("   2. Intent: ROUTE OPTIMIZATION")
        print("   3. Calling routing_agent with current GPS + today's appointments")
        print("\n   [✅] routing_agent: Multi-modal comparison complete")
        print("\n   🚗 DRIVING: 95 min, 18.5 km, est. fuel S/25")
        print("   🚕 TAXI:    110 min, 18.5 km, est. fare S/85")
        print("   🚌 TRANSIT: 145 min, 18.5 km, est. fare S/12 (Metropolitano + Metro)")
        print("\n   ⚠️  Note: Transit mode has limited coverage for inter-district travel in Lima.")

    else:
        print("   2. Intent: GENERAL QUERY")
        print("   3. Response: How can I help you today? Use /broker-day-start to begin.")

    print("\n" + "="*70)


def main():
    print("🇵🇪 PeruRE Agent Demo — Claude Certified Architect Portfolio")
    print("="*70)

    # Initialize coordinator with mock state
    coordinator = BrokerCoordinator(api_key="demo-key")
    coordinator.client = None  # Disable real API

    coordinator.update_broker_state(BrokerState(
        current_location={"lat": -12.1219, "lng": -77.0293, "name": "Miraflores"},
        confirmed_appointments_today=[
            {"client_id": "CLI-1001", "time": "10:00", "district": "San Borja", "appt_id": "APT-001", "status": "cancelled"},
            {"client_id": "CLI-1002", "time": "11:30", "district": "Miraflores", "appt_id": "APT-002", "status": "confirmed"},
            {"client_id": "CLI-1003", "time": "14:00", "district": "Surco", "appt_id": "APT-003", "status": "tentative"}
        ],
        pending_proposals=[],
        active_concerns=["traffic_alert_surco", "tentative_appointment_ana"],
        last_updated=datetime.now(ZoneInfo("America/Lima")).isoformat()
    ))

    # Demo scenario 1: Cancellation
    mock_claude_api(coordinator, "My 10am with Maria G. in San Borja cancelled. I'm currently in Miraflores. What should I do?")

    # Demo scenario 2: Route optimization
    mock_claude_api(coordinator, "Show me my route for the rest of the day, compare driving vs taxi vs transit")

    print("\n✅ Demo complete!")
    print("\nNext steps:")
    print("  1. Set ANTHROPIC_API_KEY in .env")
    print("  2. Run: python agents/coordinator.py")
    print("  3. Or use Claude Code: claude /broker-day-start")
    print("  4. Open frontend/index.html in browser (serve with: python -m http.server 3000)")


if __name__ == "__main__":
    main()

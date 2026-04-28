"""
FastAPI backend endpoint tests
==============================
Tests /health, /api/v1/coordinate, and static file serving.
BrokerCoordinator.run() is mocked so no Anthropic API key is needed.

Run: pytest backend/test_main.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_payload_structure(self):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data

    def test_health_content_type_json(self):
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# /api/v1/coordinate endpoint
# ---------------------------------------------------------------------------

_MOCK_COORDINATOR_RESULT = {
    "status": "success",
    "action_plan": ["Route optimized", "2 alternatives found"],
    "findings": [{"claim": "Cancellation processed", "source": "scheduling_agent", "confidence": "high"}],
    "coverage_gaps": [],
    "requires_approval": False,
    "approval_items": [],
    "escalation": None,
}


class TestCoordinateEndpoint:

    def test_coordinate_requires_broker_id(self):
        """broker_id is required; missing it returns 422."""
        response = client.post("/api/v1/coordinate", json={
            "instruction": "Test",
            "context": {}
        })
        assert response.status_code == 422

    def test_coordinate_requires_instruction(self):
        """instruction is required; missing it returns 422."""
        response = client.post("/api/v1/coordinate", json={
            "broker_id": "broker-001",
            "context": {}
        })
        assert response.status_code == 422

    def test_coordinate_success(self):
        """Valid request returns coordinator result with 200."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            instance = MockCoord.return_value
            instance.run.return_value = _MOCK_COORDINATOR_RESULT

            response = client.post("/api/v1/coordinate", json={
                "broker_id": "broker-001",
                "instruction": "My 2pm in San Borja cancelled. Re-optimize my day.",
                "context": {}
            })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["action_plan"]) > 0
        instance.run.assert_called_once_with(
            "My 2pm in San Borja cancelled. Re-optimize my day."
        )

    def test_coordinate_passes_broker_state(self):
        """Broker state in context.broker_state is loaded into coordinator."""
        broker_state_payload = {
            "current_location": {"lat": -12.12, "lng": -77.03},
            "confirmed_appointments_today": [
                {"client_id": "CLI-1001", "time": "10:00", "district": "San Borja"}
            ],
            "pending_proposals": [],
            "active_concerns": ["traffic_surco"],
            "last_updated": "2026-04-28T08:00:00-05:00"
        }

        with patch("backend.main.BrokerCoordinator") as MockCoord:
            instance = MockCoord.return_value
            instance.run.return_value = _MOCK_COORDINATOR_RESULT

            response = client.post("/api/v1/coordinate", json={
                "broker_id": "broker-001",
                "instruction": "How many appointments today?",
                "context": {"broker_state": broker_state_payload}
            })

        assert response.status_code == 200
        # update_broker_state should have been called with a BrokerState
        instance.update_broker_state.assert_called_once()
        call_arg = instance.update_broker_state.call_args[0][0]
        from agents.coordinator import BrokerState
        assert isinstance(call_arg, BrokerState)
        assert call_arg.current_location == {"lat": -12.12, "lng": -77.03}

    def test_coordinate_default_context_is_empty_dict(self):
        """context field defaults to {} — omitting it is valid."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            instance = MockCoord.return_value
            instance.run.return_value = _MOCK_COORDINATOR_RESULT

            response = client.post("/api/v1/coordinate", json={
                "broker_id": "broker-001",
                "instruction": "Start my day",
            })

        assert response.status_code == 200

    def test_coordinate_500_on_coordinator_exception(self):
        """If coordinator.run() raises, endpoint returns 500."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            instance = MockCoord.return_value
            instance.run.side_effect = RuntimeError("Anthropic API unavailable")

            response = client.post("/api/v1/coordinate", json={
                "broker_id": "broker-001",
                "instruction": "Test",
                "context": {}
            })

        assert response.status_code == 500
        assert "Anthropic API unavailable" in response.json()["detail"]

    def test_coordinate_partial_response_passthrough(self):
        """coordinator.run() returning status=partial is passed through unchanged."""
        partial_result = {
            "status": "partial",
            "raw_response": "Could not parse structured output",
            "error": "JSON parse failure"
        }
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            instance = MockCoord.return_value
            instance.run.return_value = partial_result

            response = client.post("/api/v1/coordinate", json={
                "broker_id": "broker-001",
                "instruction": "test",
            })

        assert response.status_code == 200
        assert response.json()["status"] == "partial"


# ---------------------------------------------------------------------------
# Frontend static serving
# ---------------------------------------------------------------------------

class TestStaticFrontend:

    def test_index_html_served(self):
        """GET / returns the Mapbox dashboard HTML."""
        response = client.get("/")
        assert response.status_code == 200
        # Verify it's actually the frontend, not an API response
        assert "text/html" in response.headers["content-type"]
        assert "PeruRE" in response.text


# ---------------------------------------------------------------------------
# MCP endpoint presence
# ---------------------------------------------------------------------------

class TestMcpEndpoints:

    def test_mcp_maps_sse_endpoint_routed(self):
        """MCP maps SSE endpoint is routed (check app.routes, don't open SSE stream)."""
        route_paths = [str(r.path) for r in app.routes]
        assert any("/mcp/maps" in p for p in route_paths)

    def test_mcp_calendar_sse_endpoint_routed(self):
        route_paths = [str(r.path) for r in app.routes]
        assert any("/mcp/calendar" in p for p in route_paths)

    def test_mcp_whatsapp_sse_endpoint_routed(self):
        route_paths = [str(r.path) for r in app.routes]
        assert any("/mcp/whatsapp" in p for p in route_paths)

    def test_mcp_property_db_sse_endpoint_routed(self):
        route_paths = [str(r.path) for r in app.routes]
        assert any("/mcp/property_db" in p for p in route_paths)

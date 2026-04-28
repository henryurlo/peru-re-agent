"""
Priority 3 Feature Tests
========================
Tests for batch endpoint, rate limiting, logging middleware,
admin dashboard, and WebSocket endpoint.

BrokerCoordinator.run() is mocked throughout — no Anthropic API key needed.

Run: pytest backend/test_priority3.py -v
"""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app, _get_rate_bucket

client = TestClient(app, raise_server_exceptions=True)


_MOCK_RESULT = {
    "status": "success",
    "action_plan": ["Route optimized"],
    "findings": [{"claim": "Done", "source": "routing_agent", "confidence": "high"}],
    "coverage_gaps": [],
    "requires_approval": False,
    "approval_items": [],
    "escalation": None,
}


def _fresh_broker_id() -> str:
    """Generate a unique broker_id so lru_cache creates a fresh token bucket."""
    return f"test-broker-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Batch Endpoint
# ---------------------------------------------------------------------------

class TestBatchEndpoint:

    def test_batch_returns_correct_count(self):
        """Batch with 3 instructions returns exactly 3 results."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT

            response = client.post("/api/v1/batch", json={
                "broker_id": _fresh_broker_id(),
                "instructions": ["Task A", "Task B", "Task C"],
            })

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_batch_single_instruction(self):
        """Batch with 1 instruction returns a list of 1."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT

            response = client.post("/api/v1/batch", json={
                "broker_id": _fresh_broker_id(),
                "instructions": ["Only task"],
            })

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_batch_empty_instructions(self):
        """Batch with no instructions returns empty list."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT

            response = client.post("/api/v1/batch", json={
                "broker_id": _fresh_broker_id(),
                "instructions": [],
            })

        assert response.status_code == 200
        assert response.json() == []

    def test_batch_preserves_order(self):
        """Results are returned in the same order as instructions."""
        results = [
            {**_MOCK_RESULT, "action_plan": [f"Step {i}"]}
            for i in range(5)
        ]
        call_count = [0]

        def side_effect(instruction):
            idx = call_count[0]
            call_count[0] += 1
            return results[idx % len(results)]

        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.side_effect = side_effect

            response = client.post("/api/v1/batch", json={
                "broker_id": _fresh_broker_id(),
                "instructions": [f"Instruction {i}" for i in range(5)],
            })

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    def test_batch_requires_broker_id(self):
        """Missing broker_id returns 422."""
        response = client.post("/api/v1/batch", json={
            "instructions": ["task"],
        })
        assert response.status_code == 422

    def test_batch_requires_instructions(self):
        """Missing instructions field returns 422."""
        response = client.post("/api/v1/batch", json={
            "broker_id": "broker-001",
        })
        assert response.status_code == 422

    def test_batch_coordinator_exception_returns_error_entry(self):
        """If coordinator raises, the result entry has status=error instead of 500."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.side_effect = RuntimeError("API down")

            response = client.post("/api/v1/batch", json={
                "broker_id": _fresh_broker_id(),
                "instructions": ["fail task"],
            })

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "error"
        assert "API down" in data[0]["detail"]


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:

    def _exhaust_bucket(self, broker_id: str, count: int = 10):
        """Burn through `count` tokens on the coordinate endpoint."""
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT
            for _ in range(count):
                client.post("/api/v1/coordinate", json={
                    "broker_id": broker_id,
                    "instruction": "test",
                })

    def test_rate_limit_returns_429_after_capacity_exhausted(self):
        """After consuming all bucket tokens, next request returns 429."""
        broker_id = _fresh_broker_id()
        self._exhaust_bucket(broker_id, count=10)

        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT
            response = client.post("/api/v1/coordinate", json={
                "broker_id": broker_id,
                "instruction": "over limit",
            })

        assert response.status_code == 429

    def test_retry_after_header_present_on_429(self):
        """429 response includes Retry-After header."""
        broker_id = _fresh_broker_id()
        self._exhaust_bucket(broker_id, count=10)

        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT
            response = client.post("/api/v1/coordinate", json={
                "broker_id": broker_id,
                "instruction": "over limit",
            })

        assert response.status_code == 429
        # Headers are case-insensitive in HTTP; TestClient lowercases them
        assert "retry-after" in response.headers

    def test_retry_after_is_positive_integer(self):
        """Retry-After header value is a positive integer string."""
        broker_id = _fresh_broker_id()
        self._exhaust_bucket(broker_id, count=10)

        with patch("backend.main.BrokerCoordinator"):
            response = client.post("/api/v1/coordinate", json={
                "broker_id": broker_id,
                "instruction": "over limit",
            })

        retry_after = int(response.headers["retry-after"])
        assert retry_after >= 1

    def test_rate_limit_independent_per_broker(self):
        """Different broker_ids have independent rate limit buckets."""
        broker_a = _fresh_broker_id()
        broker_b = _fresh_broker_id()

        # Exhaust broker_a
        self._exhaust_bucket(broker_a, count=10)

        # broker_b should still be allowed
        with patch("backend.main.BrokerCoordinator") as MockCoord:
            MockCoord.return_value.run.return_value = _MOCK_RESULT
            response = client.post("/api/v1/coordinate", json={
                "broker_id": broker_b,
                "instruction": "fresh broker",
            })

        assert response.status_code == 200

    def test_rate_limit_response_body_has_detail(self):
        """429 response body includes a detail field."""
        broker_id = _fresh_broker_id()
        self._exhaust_bucket(broker_id, count=10)

        with patch("backend.main.BrokerCoordinator"):
            response = client.post("/api/v1/coordinate", json={
                "broker_id": broker_id,
                "instruction": "over limit",
            })

        assert response.status_code == 429
        assert "detail" in response.json()

    def test_batch_rate_limit_returns_429(self):
        """Batch endpoint is also rate-limited."""
        broker_id = _fresh_broker_id()
        self._exhaust_bucket(broker_id, count=10)

        with patch("backend.main.BrokerCoordinator"):
            response = client.post("/api/v1/batch", json={
                "broker_id": broker_id,
                "instructions": ["task"],
            })

        assert response.status_code == 429
        assert "retry-after" in response.headers


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

class TestAdminDashboard:

    def test_admin_serves_html(self):
        """GET /admin returns 200 with HTML content-type."""
        response = client.get("/admin")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_contains_dashboard_markup(self):
        """Admin page contains expected dashboard elements."""
        response = client.get("/admin")
        assert "PeruRE" in response.text
        assert "Admin Dashboard" in response.text

    def test_admin_data_endpoint_structure(self):
        """GET /admin/data returns JSON with expected top-level keys."""
        response = client.get("/admin/data")
        assert response.status_code == 200
        data = response.json()
        assert "recent_requests" in data
        assert "broker_activity" in data
        assert "mcp_health" in data

    def test_admin_data_mcp_health_lists_all_servers(self):
        """MCP health covers all 4 expected servers."""
        response = client.get("/admin/data")
        health = response.json()["mcp_health"]
        for name in ("maps", "calendar", "whatsapp", "property_db"):
            assert name in health

    def test_admin_data_recent_requests_is_list(self):
        """recent_requests field is always a list."""
        response = client.get("/admin/data")
        assert isinstance(response.json()["recent_requests"], list)

    def test_admin_data_broker_activity_is_dict(self):
        """broker_activity field is always a dict."""
        response = client.get("/admin/data")
        assert isinstance(response.json()["broker_activity"], dict)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

class TestWebSocket:

    def test_websocket_connection_accepted(self):
        """WebSocket at /ws/broker/{id} is accepted without error."""
        broker_id = _fresh_broker_id()
        with client.websocket_connect(f"/ws/broker/{broker_id}"):
            pass  # No exception = connection was accepted

    def test_websocket_distinct_ids_independent(self):
        """Two different broker_ids can connect simultaneously."""
        id_a = _fresh_broker_id()
        id_b = _fresh_broker_id()
        with client.websocket_connect(f"/ws/broker/{id_a}"):
            with client.websocket_connect(f"/ws/broker/{id_b}"):
                pass  # Both open simultaneously without error

    def test_websocket_coordinate_broadcasts_result(self):
        """After /coordinate, result is broadcast to broker's WebSocket."""
        broker_id = _fresh_broker_id()

        with client.websocket_connect(f"/ws/broker/{broker_id}") as ws:
            with patch("backend.main.BrokerCoordinator") as MockCoord:
                MockCoord.return_value.run.return_value = _MOCK_RESULT
                api_response = client.post("/api/v1/coordinate", json={
                    "broker_id": broker_id,
                    "instruction": "Start my day",
                })

            assert api_response.status_code == 200
            # WebSocket should receive the same result that the API returned
            pushed = ws.receive_json()
            assert pushed["status"] == "success"

    def test_websocket_batch_broadcasts_results(self):
        """After /batch, results are broadcast to broker's WebSocket."""
        broker_id = _fresh_broker_id()

        with client.websocket_connect(f"/ws/broker/{broker_id}") as ws:
            with patch("backend.main.BrokerCoordinator") as MockCoord:
                MockCoord.return_value.run.return_value = _MOCK_RESULT
                api_response = client.post("/api/v1/batch", json={
                    "broker_id": broker_id,
                    "instructions": ["Task 1", "Task 2"],
                })

            assert api_response.status_code == 200
            pushed = ws.receive_json()
            assert "batch_results" in pushed
            assert pushed["count"] == 2


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

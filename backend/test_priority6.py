"""
Priority 6 tests — Client Demo Experience
Covers: /pitch, /broker, /proposal, /api/v1/demo/*
"""

import pytest
from fastapi.testclient import TestClient

# Ensure imports work from project root
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

client = TestClient(app)


def test_pitch_page_returns_200_and_brand():
    r = client.get("/pitch")
    assert r.status_code == 200
    assert "PeruRE" in r.text


def test_broker_page_returns_200_and_panel_title():
    r = client.get("/broker")
    assert r.status_code == 200
    assert "Panel del Asesor" in r.text


def test_proposal_page_returns_200_and_executive_summary():
    r = client.get("/proposal")
    assert r.status_code == 200
    assert "Resumen Ejecutivo" in r.text


def test_demo_seed_creates_data():
    r = client.post("/api/v1/demo/seed")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("success", "already_seeded")


def test_demo_properties_returns_five():
    client.post("/api/v1/demo/seed")
    r = client.get("/api/v1/demo/properties")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["total"] == 5
    assert len(data["propiedades"]) == 5


def test_demo_clients_returns_three():
    client.post("/api/v1/demo/seed")
    r = client.get("/api/v1/demo/clients")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["total"] == 3
    assert len(data["clientes"]) == 3


def test_demo_tours_returns_at_least_one():
    client.post("/api/v1/demo/seed")
    r = client.get("/api/v1/demo/tours")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["total"] >= 1


def test_demo_reset_clears_and_reseeds():
    client.post("/api/v1/demo/seed")
    r = client.post("/api/v1/demo/reset")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    # Verify still has data after reset
    r2 = client.get("/api/v1/demo/properties")
    assert r2.json()["total"] == 5


def test_existing_health_still_works():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_existing_admin_still_works():
    r = client.get("/admin")
    assert r.status_code == 200
    assert "MCP Health" in r.text or "mcp-health" in r.text


def test_existing_batch_endpoint_still_exists():
    r = client.post("/api/v1/batch", json={"broker_id": "test-p6", "instructions": ["hello"]})
    # May return 500 if no API key, but endpoint must exist
    assert r.status_code in (200, 429, 500)

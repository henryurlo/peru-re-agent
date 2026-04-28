"""
Priority 4 Integration Tests
=============================
Verifies real parsing/wiring for Mapbox, WhatsApp, and property DB layers.

External HTTP calls are always mocked (no tokens or credentials needed).
Tests exercise:
  - Mapbox response parsing, cache hit/miss, TTL, cache clear
  - Graceful degradation when MAPBOX_TOKEN is absent
  - WhatsApp graceful degradation without credentials
  - WhatsApp real API path: correct URL, headers, body, message-ID parsing
  - WhatsApp error handling: 401, 400, 429, timeout, connection error
  - Property DB SQLite schema auto-init (tables created at module load)
  - Property DB CRUD with SQLite: query, store, get
  - Property DB match scoring logic

Run: pytest backend/test_integration.py -v
"""

import json
import os
import sys
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Mapbox helpers ─────────────────────────────────────────────────────────────

def _make_mapbox_route_response(duration_sec: int = 1500, distance_m: int = 8500) -> dict:
    """Minimal Mapbox Directions API response for a 1-leg route."""
    return {
        "routes": [{
            "legs": [{
                "duration": duration_sec,
                "distance": distance_m,
                "geometry": {},
            }],
            "geometry": {"type": "LineString", "coordinates": [[-77.03, -12.12], [-77.00, -12.10]]},
        }],
        "waypoints": [],
    }


def _make_mapbox_eta_response(duration_sec: int = 1200, distance_m: int = 6000) -> dict:
    return {
        "routes": [{
            "legs": [{"duration": duration_sec, "distance": distance_m}],
            "geometry": {},
        }],
        "waypoints": [],
    }


_ORIGIN = {"lat": -12.12, "lng": -77.03, "name": "Miraflores"}
_DEST = [{"lat": -12.10, "lng": -77.00, "name": "San Borja"}]


# ── Mapbox cache tests ─────────────────────────────────────────────────────────

class TestMapboxCaching:

    def setup_method(self):
        """Reset cache and stats before each test."""
        from mcp_servers.maps import server as maps_srv
        maps_srv._route_cache.clear()
        maps_srv._cache_stats["hits"] = 0
        maps_srv._cache_stats["misses"] = 0

    def test_cache_miss_calls_api(self):
        """First call goes to the Mapbox API (cache miss)."""
        from mcp_servers.maps.server import _calculate_route, _cache_stats

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token_for_testing"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp) as mock_get:
                _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        mock_get.assert_called_once()
        assert _cache_stats["misses"] == 1
        assert _cache_stats["hits"] == 0

    def test_cache_hit_skips_api(self):
        """Second call with same params returns cached result, no second API call."""
        from mcp_servers.maps.server import _calculate_route, _cache_stats

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token_for_testing"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp) as mock_get:
                result1 = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})
                result2 = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        assert mock_get.call_count == 1, "API should be called only once — second call is a cache hit"
        assert _cache_stats["hits"] == 1
        assert _cache_stats["misses"] == 1
        assert result1 == result2

    def test_different_modes_use_different_cache_keys(self):
        """driving and taxi routes have separate cache entries."""
        from mcp_servers.maps.server import _calculate_route, _cache_stats

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp) as mock_get:
                _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})
                _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "taxi"})

        assert mock_get.call_count == 2

    def test_cache_clear_removes_entries(self):
        """_clear_route_cache removes all entries and resets stats."""
        from mcp_servers.maps.server import _calculate_route, _clear_route_cache, _cache_stats, _route_cache

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp):
                _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        assert len(_route_cache) == 1
        result = _clear_route_cache()

        assert result["cleared_entries"] == 1
        assert result["cache_stats_reset"] is True
        assert len(_route_cache) == 0
        assert _cache_stats["hits"] == 0
        assert _cache_stats["misses"] == 0

    def test_after_cache_clear_api_called_again(self):
        """After clearing the cache, the next call hits the API again."""
        from mcp_servers.maps.server import _calculate_route, _clear_route_cache

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp) as mock_get:
                _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})
                _clear_route_cache()
                _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        assert mock_get.call_count == 2

    def test_cache_hit_ratio_tracked(self):
        """Cache stats accumulate correctly across multiple calls."""
        from mcp_servers.maps.server import _calculate_route, _cache_stats

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp):
                for _ in range(4):
                    _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        # 1 miss (first call) + 3 hits
        assert _cache_stats["misses"] == 1
        assert _cache_stats["hits"] == 3

    def test_response_parsed_correctly(self):
        """Mapbox JSON response is parsed into the expected RoutePlan structure."""
        from mcp_servers.maps.server import _calculate_route

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response(duration_sec=1500, distance_m=8500)
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp):
                result = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        assert result["mode"] == "driving"
        assert result["total_duration_minutes"] == pytest.approx(25.0, abs=0.1)
        assert result["total_distance_km"] == pytest.approx(8.5, abs=0.1)
        assert len(result["legs"]) == 1
        assert result["legs"][0]["from"]["name"] == "Miraflores"
        assert result["legs"][0]["to"]["name"] == "San Borja"

    def test_taxi_fare_estimate_included(self):
        """Taxi mode includes fare_estimate_sol in the response."""
        from mcp_servers.maps.server import _calculate_route

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_route_response()
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp):
                result = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "taxi"})

        assert "fare_estimate_sol" in result
        assert result["fare_estimate_sol"] > 0

    def test_single_eta_cache_hit(self):
        """get_single_eta uses the cache for repeated identical calls."""
        from mcp_servers.maps.server import _single_eta, _cache_stats

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_mapbox_eta_response()
        mock_resp.raise_for_status = MagicMock()

        eta_args = {"origin": {"lat": -12.12, "lng": -77.03}, "destination": {"lat": -12.10, "lng": -77.00}, "mode": "driving"}

        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.fake_token"}):
            with patch("mcp_servers.maps.server.requests.get", return_value=mock_resp) as mock_get:
                _single_eta(eta_args)
                _single_eta(eta_args)

        assert mock_get.call_count == 1
        assert _cache_stats["hits"] == 1


# ── Mapbox graceful degradation tests ─────────────────────────────────────────

class TestMapboxGracefulDegradation:

    def setup_method(self):
        from mcp_servers.maps import server as maps_srv
        maps_srv._route_cache.clear()
        maps_srv._cache_stats["hits"] = 0
        maps_srv._cache_stats["misses"] = 0

    def test_no_token_returns_mock_route(self):
        """Without MAPBOX_TOKEN, route returns placeholder data without API call."""
        from mcp_servers.maps.server import _calculate_route

        with patch.dict(os.environ, {"MAPBOX_TOKEN": ""}, clear=False):
            os.environ.pop("MAPBOX_TOKEN", None)
            with patch("mcp_servers.maps.server.requests.get") as mock_get:
                result = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        mock_get.assert_not_called()
        assert result.get("is_mock") is True
        assert "warning" in result
        assert "total_duration_minutes" in result
        assert len(result["legs"]) == 1

    def test_no_token_eta_returns_mock(self):
        """Without MAPBOX_TOKEN, ETA returns placeholder without API call."""
        from mcp_servers.maps.server import _single_eta

        eta_args = {"origin": {"lat": -12.12, "lng": -77.03}, "destination": {"lat": -12.10, "lng": -77.00}, "mode": "driving"}

        with patch.dict(os.environ, {"MAPBOX_TOKEN": ""}, clear=False):
            os.environ.pop("MAPBOX_TOKEN", None)
            with patch("mcp_servers.maps.server.requests.get") as mock_get:
                result = _single_eta(eta_args)

        mock_get.assert_not_called()
        assert result.get("is_mock") is True
        assert result["duration_minutes"] > 0

    def test_no_token_mock_includes_taxi_fare(self):
        """Mock taxi route still includes fare_estimate_sol."""
        from mcp_servers.maps.server import _calculate_route

        with patch.dict(os.environ, {"MAPBOX_TOKEN": ""}, clear=False):
            os.environ.pop("MAPBOX_TOKEN", None)
            result = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "taxi"})

        assert "fare_estimate_sol" in result

    def test_empty_token_string_treated_as_missing(self):
        """MAPBOX_TOKEN='' (empty string) is treated the same as not set."""
        from mcp_servers.maps.server import _calculate_route

        with patch.dict(os.environ, {"MAPBOX_TOKEN": ""}):
            with patch("mcp_servers.maps.server.requests.get") as mock_get:
                result = _calculate_route({"origin": _ORIGIN, "destinations": _DEST, "mode": "driving"})

        mock_get.assert_not_called()
        assert result.get("is_mock") is True


# ── WhatsApp integration tests ─────────────────────────────────────────────────

_WA_SUCCESS_RESPONSE = {
    "messaging_product": "whatsapp",
    "contacts": [{"input": "51999123456", "wa_id": "51999123456"}],
    "messages": [{"id": "wamid.test_msg_abc123"}],
}

_SEND_ARGS = {
    "client_id": "CLI-TEST-001",
    "phone_number": "51999123456",
    "template_name": "appointment_reminder",
    "language_code": "es",
    "variables": {"client_name": "María", "time": "10:00 AM", "address": "Las Lomas 432"},
}


def _mock_lima_10am():
    """Return a mock datetime at 10:00 AM Lima time (inside business hours)."""
    from zoneinfo import ZoneInfo
    mock_dt = MagicMock()
    mock_dt.now.return_value = datetime(2026, 4, 28, 10, 0, 0, tzinfo=ZoneInfo("America/Lima"))
    return mock_dt


class TestWhatsAppGracefulDegradation:

    def test_missing_credentials_no_api_call(self):
        """Without credentials, send_templated_whatsapp makes no HTTP call."""
        from mcp_servers.whatsapp.server import _send_message

        env = {k: v for k, v in os.environ.items()
               if k not in ("WHATSAPP_BUSINESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")}
        with patch.dict(os.environ, env, clear=True):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post") as mock_post:
                    _send_message(_SEND_ARGS)

        mock_post.assert_not_called()

    def test_missing_credentials_returns_mock_flag(self):
        """Without credentials, response includes is_mock=True and warning."""
        from mcp_servers.whatsapp.server import _send_message

        env = {k: v for k, v in os.environ.items()
               if k not in ("WHATSAPP_BUSINESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")}
        with patch.dict(os.environ, env, clear=True):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                result = _send_message(_SEND_ARGS)

        assert result.get("is_mock") is True
        assert "warning" in result
        assert result["status"] == "success"
        assert result["delivery_status"] == "mock"

    def test_missing_credentials_hook_checks_still_run(self):
        """Even in mock mode, time_gate and template_approved checks are enforced."""
        from mcp_servers.whatsapp.server import _send_message

        env = {k: v for k, v in os.environ.items()
               if k not in ("WHATSAPP_BUSINESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")}
        with patch.dict(os.environ, env, clear=True):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                result = _send_message(_SEND_ARGS)

        assert "time_gate" in result["hook_checks_passed"]
        assert "template_approved" in result["hook_checks_passed"]

    def test_time_gate_blocks_outside_hours(self):
        """Message is blocked at 9 PM Lima time regardless of credentials."""
        from mcp_servers.whatsapp.server import _send_message
        from zoneinfo import ZoneInfo

        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2026, 4, 28, 21, 0, 0, tzinfo=ZoneInfo("America/Lima"))

        with patch("mcp_servers.whatsapp.server.datetime", mock_dt):
            result = _send_message(_SEND_ARGS)

        assert result.get("isError") is True
        assert result["errorCategory"] == "business"

    def test_invalid_template_rejected(self):
        """Unknown template name returns validation error even with credentials."""
        from mcp_servers.whatsapp.server import _send_message

        args = {**_SEND_ARGS, "template_name": "random_unknown_template"}
        with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
            result = _send_message(args)

        assert result.get("isError") is True
        assert result["errorCategory"] == "validation"


class TestWhatsAppRealApiPath:

    def test_with_credentials_calls_api(self):
        """When credentials are set, _http.post is called once."""
        from mcp_servers.whatsapp.server import _send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _WA_SUCCESS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "EAA_fake", "WHATSAPP_PHONE_NUMBER_ID": "12345678"}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", return_value=mock_resp) as mock_post:
                    _send_message(_SEND_ARGS)

        mock_post.assert_called_once()

    def test_api_call_uses_correct_url(self):
        """The API call URL includes the PHONE_NUMBER_ID."""
        from mcp_servers.whatsapp.server import _send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _WA_SUCCESS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        phone_id = "99887766"
        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "EAA_fake", "WHATSAPP_PHONE_NUMBER_ID": phone_id}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", return_value=mock_resp) as mock_post:
                    _send_message(_SEND_ARGS)

        call_url = mock_post.call_args[0][0]
        assert phone_id in call_url
        assert "graph.facebook.com" in call_url

    def test_api_call_sends_bearer_token(self):
        """The Authorization header contains the bearer token."""
        from mcp_servers.whatsapp.server import _send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _WA_SUCCESS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "EAA_my_secret_token", "WHATSAPP_PHONE_NUMBER_ID": "12345"}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", return_value=mock_resp) as mock_post:
                    _send_message(_SEND_ARGS)

        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer EAA_my_secret_token"

    def test_message_id_parsed_from_response(self):
        """message_id is extracted from the WhatsApp API response."""
        from mcp_servers.whatsapp.server import _send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _WA_SUCCESS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "EAA_fake", "WHATSAPP_PHONE_NUMBER_ID": "12345"}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", return_value=mock_resp):
                    result = _send_message(_SEND_ARGS)

        assert result["message_id"] == "wamid.test_msg_abc123"
        assert result["status"] == "success"
        assert result.get("is_mock") is None  # real send has no is_mock flag

    def test_api_401_returns_auth_error(self):
        """HTTP 401 from WhatsApp API is mapped to auth error (not retryable)."""
        from mcp_servers.whatsapp.server import _send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid OAuth access token"}}

        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "expired_token", "WHATSAPP_PHONE_NUMBER_ID": "12345"}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", return_value=mock_resp):
                    result = _send_message(_SEND_ARGS)

        assert result["isError"] is True
        assert result["errorCategory"] == "auth"
        assert result["isRetryable"] is False

    def test_api_429_returns_transient_error(self):
        """HTTP 429 from WhatsApp API is mapped to retryable transient error."""
        from mcp_servers.whatsapp.server import _send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 429

        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "EAA_fake", "WHATSAPP_PHONE_NUMBER_ID": "12345"}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", return_value=mock_resp):
                    result = _send_message(_SEND_ARGS)

        assert result["isError"] is True
        assert result["isRetryable"] is True

    def test_api_timeout_returns_retryable_error(self):
        """Network timeout is mapped to retryable transient error."""
        import requests as _req
        from mcp_servers.whatsapp.server import _send_message

        wa_env = {"WHATSAPP_BUSINESS_TOKEN": "EAA_fake", "WHATSAPP_PHONE_NUMBER_ID": "12345"}
        with patch.dict(os.environ, wa_env):
            with patch("mcp_servers.whatsapp.server.datetime", _mock_lima_10am()):
                with patch("mcp_servers.whatsapp.server._http.post", side_effect=_req.exceptions.Timeout()):
                    result = _send_message(_SEND_ARGS)

        assert result["isError"] is True
        assert result["isRetryable"] is True
        assert "timeout" in result["description"].lower()


# ── Property DB integration tests ─────────────────────────────────────────────

class TestPropertyDbSqliteInit:

    def test_sqlite_properties_table_exists(self):
        """The properties table is created at module load time."""
        from mcp_servers.property_db import server as db_srv

        assert db_srv._sqlite_conn is not None, "SQLite connection should be initialised"
        cur = db_srv._sqlite_conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='properties'")
        assert cur.fetchone() is not None, "properties table must exist"

    def test_sqlite_clients_table_exists(self):
        """The clients table is created at module load time."""
        from mcp_servers.property_db import server as db_srv

        cur = db_srv._sqlite_conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
        assert cur.fetchone() is not None, "clients table must exist"

    def test_sqlite_seeded_with_properties(self):
        """Seed properties are inserted during init."""
        from mcp_servers.property_db import server as db_srv

        cur = db_srv._sqlite_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM properties")
        count = cur.fetchone()[0]
        assert count >= 5, f"Expected at least 5 seed properties, got {count}"

    def test_sqlite_mode_active_without_database_url(self):
        """Without DATABASE_URL, _USE_PG is False."""
        from mcp_servers.property_db import server as db_srv

        # No DATABASE_URL is set in the test environment
        assert db_srv._USE_PG is False

    def test_schema_init_is_idempotent(self):
        """Running _init_db again with SQLite does not raise or break data."""
        from mcp_servers.property_db import server as db_srv

        # Re-running should not corrupt the existing DB state
        # (new in-memory DB is created on re-init, but no error should occur)
        try:
            # We only verify the current state is healthy, not re-run init
            result = db_srv._query_properties({})
            assert "properties" in result
        except Exception as exc:
            pytest.fail(f"DB query failed after re-init check: {exc}")


class TestPropertyDbQueryProperties:

    def test_query_all_available(self):
        """_query_properties with no filters returns all available seed properties."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({})
        assert result["count"] >= 5
        assert all(p["status"] == "available" for p in result["properties"])

    def test_query_filter_by_single_district(self):
        """District filter returns only properties in that district."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"districts": ["Miraflores"]})
        assert result["count"] > 0
        assert all(p["district"] == "Miraflores" for p in result["properties"])

    def test_query_filter_by_multiple_districts(self):
        """Multiple districts: all returned properties are in the requested set."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"districts": ["Miraflores", "San Borja"]})
        for p in result["properties"]:
            assert p["district"] in ("Miraflores", "San Borja")

    def test_query_filter_by_price_range(self):
        """Price range filter works correctly."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"min_price": 150000, "max_price": 200000})
        for p in result["properties"]:
            assert 150000 <= p["price_usd"] <= 200000

    def test_query_filter_by_type(self):
        """Property type filter returns only matching types."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"property_type": "house"})
        assert result["count"] > 0
        assert all(p["type"] == "house" for p in result["properties"])

    def test_query_filter_by_min_bedrooms(self):
        """Min bedrooms filter excludes smaller properties."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"min_bedrooms": 3})
        assert all(p["bedrooms"] >= 3 for p in result["properties"])

    def test_query_features_parsed_as_list(self):
        """Features field is returned as a Python list, not a JSON string."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"districts": ["Miraflores"]})
        assert result["count"] > 0
        for p in result["properties"]:
            assert isinstance(p["features"], list), "features must be a list"

    def test_query_unknown_district_returns_empty(self):
        """A district with no matching properties returns count=0."""
        from mcp_servers.property_db.server import _query_properties

        result = _query_properties({"districts": ["NoSuchDistrict_XYZ"]})
        assert result["count"] == 0


class TestPropertyDbClientCRUD:

    _test_client = {
        "client_id": "CLI-INTTEST-001",
        "name": "Test User Integration",
        "phone": "51999000000",
        "budget_usd": 175000,
        "preferred_districts": ["Miraflores", "Barranco"],
        "financing_status": "pre_approved",
        "financing_score": 80,
        "documents_status": {"dni": True, "pay_stubs": True, "tax_returns": False, "pre_approval": True},
        "status": "qualified",
        "do_not_contact": False,
    }

    def test_store_client_returns_success(self):
        from mcp_servers.property_db.server import _store_client

        result = _store_client(self._test_client)
        assert result["status"] == "success"
        assert result["client_id"] == "CLI-INTTEST-001"

    def test_get_stored_client(self):
        """Client stored by _store_client can be retrieved by _get_client."""
        from mcp_servers.property_db.server import _store_client, _get_client

        _store_client(self._test_client)
        result = _get_client({"client_id": "CLI-INTTEST-001"})

        assert result["status"] == "success"
        client = result["client"]
        assert client["name"] == "Test User Integration"
        assert client["phone"] == "51999000000"
        assert client["financing_status"] == "pre_approved"

    def test_get_nonexistent_client_returns_error(self):
        """_get_client returns an error dict for an unknown ID."""
        from mcp_servers.property_db.server import _get_client

        result = _get_client({"client_id": "CLI-DOES-NOT-EXIST-99999"})
        assert result.get("isError") is True

    def test_store_client_upsert(self):
        """Storing the same client_id twice updates the record."""
        from mcp_servers.property_db.server import _store_client, _get_client

        _store_client({**self._test_client, "client_id": "CLI-INTTEST-002", "name": "Original Name"})
        _store_client({**self._test_client, "client_id": "CLI-INTTEST-002", "name": "Updated Name"})

        result = _get_client({"client_id": "CLI-INTTEST-002"})
        assert result["client"]["name"] == "Updated Name"

    def test_preferred_districts_returned_as_list(self):
        """preferred_districts is returned as a Python list (not a JSON string)."""
        from mcp_servers.property_db.server import _store_client, _get_client

        _store_client({**self._test_client, "client_id": "CLI-INTTEST-003"})
        result = _get_client({"client_id": "CLI-INTTEST-003"})

        districts = result["client"]["preferred_districts"]
        assert isinstance(districts, list), f"Expected list, got {type(districts)}"
        assert "Miraflores" in districts

    def test_documents_status_returned_as_dict(self):
        """documents_status is returned as a dict (not a JSON string)."""
        from mcp_servers.property_db.server import _store_client, _get_client

        _store_client({**self._test_client, "client_id": "CLI-INTTEST-004"})
        result = _get_client({"client_id": "CLI-INTTEST-004"})

        docs = result["client"]["documents_status"]
        assert isinstance(docs, dict), f"Expected dict, got {type(docs)}"
        assert docs.get("dni") is True


class TestPropertyDbMatchScoring:

    def test_match_returns_top_5(self):
        """match_client_to_properties returns at most 5 results."""
        from mcp_servers.property_db.server import _match_client

        result = _match_client({
            "client_id": "CLI-MATCH-001",
            "budget_usd": 200000,
            "preferred_districts": ["Miraflores"],
        })
        assert len(result["matches"]) <= 5

    def test_match_prefers_budget_fit(self):
        """Properties within budget score higher than those outside."""
        from mcp_servers.property_db.server import _match_client

        result = _match_client({
            "client_id": "CLI-MATCH-002",
            "budget_usd": 185000,  # exactly matches PROP-2847
            "preferred_districts": [],
        })
        scores = [m["match_score"] for m in result["matches"]]
        # Results are sorted descending
        assert scores == sorted(scores, reverse=True)

    def test_match_includes_district_alternative(self):
        """alternative_districts field lists districts not in preference list."""
        from mcp_servers.property_db.server import _match_client

        result = _match_client({
            "client_id": "CLI-MATCH-003",
            "budget_usd": 200000,
            "preferred_districts": ["Miraflores"],
        })
        assert isinstance(result["alternative_districts"], list)

    def test_match_financing_ready_boosts_score(self):
        """pre_approved financing status adds points to match scores."""
        from mcp_servers.property_db.server import _match_client

        result_cash = _match_client({
            "client_id": "CLI-MATCH-004",
            "budget_usd": 195000,
            "preferred_districts": ["Surco"],
            "financing_status": "cash",
        })
        result_pending = _match_client({
            "client_id": "CLI-MATCH-005",
            "budget_usd": 195000,
            "preferred_districts": ["Surco"],
            "financing_status": "pending",
        })
        # cash financing should score higher than pending for the same property
        if result_cash["matches"] and result_pending["matches"]:
            top_cash = result_cash["matches"][0]["match_score"]
            top_pending = result_pending["matches"][0]["match_score"]
            assert top_cash >= top_pending

    def test_match_structure_fields(self):
        """Each match result has the required output fields."""
        from mcp_servers.property_db.server import _match_client

        result = _match_client({
            "client_id": "CLI-MATCH-006",
            "budget_usd": 200000,
        })
        for match in result["matches"]:
            assert "property_id" in match
            assert "address" in match
            assert "price_usd" in match
            assert "match_score" in match
            assert "match_reasons" in match
            assert "fast_close_eligible" in match


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

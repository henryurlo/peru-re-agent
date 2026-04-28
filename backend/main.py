"""
PeruRE FastAPI Backend
======================
Serves the frontend, exposes the coordinator agent via REST, and
mounts all 4 MCP servers as SSE sub-applications.

Architecture decisions:
- Each MCP server is mounted at /mcp/{name} as a Starlette sub-app with
  SSE transport so Claude Code / external MCP clients can connect via HTTP.
- The /api/v1/coordinate endpoint is a thin wrapper around BrokerCoordinator;
  it does NOT require an Anthropic API key at import time (key is read at
  request time from ANTHROPIC_API_KEY env var).
- Static files are mounted last so API routes always take precedence.
- python-dotenv loads .env at startup; missing required keys emit warnings
  rather than crashing (the coordinator will surface a clear error at request time).

Priority 3 additions:
- Token-bucket rate limiter (10/min, burst 10) per broker_id via lru_cache
- Structured JSON request/response logging middleware with in-memory ring buffer
- POST /api/v1/batch — parallel coordinator execution via asyncio.gather
- GET  /admin        — admin dashboard (static HTML)
- GET  /admin/data   — live JSON data for the dashboard
- WS   /ws/broker/{broker_id} — real-time result push to connected brokers
"""

import asyncio
import importlib
import json as json_lib
import os
import sys
import time as time_mod
import warnings
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List

# Load .env before anything else so environment variables are available
# for MCP servers and coordinator. Existing OS env vars take precedence.
from dotenv import load_dotenv
load_dotenv(override=False)

# ---- Environment variable validation ----------------------------------------
_REQUIRED_KEYS = {
    "ANTHROPIC_API_KEY": "Anthropic API key — needed by the coordinator agent",
}
_OPTIONAL_KEYS = {
    "MAPBOX_TOKEN": "Mapbox token — needed for real driving-route calculations",
    "DATABASE_URL": "PostgreSQL URL — needed by property_db and calendar MCP servers",
}

for _key, _desc in _REQUIRED_KEYS.items():
    if not os.getenv(_key):
        print(
            f"WARNING: {_key} is not set ({_desc}). "
            f"Set it in .env or as an environment variable. "
            f"Coordinator requests will fail until it is provided.",
            file=sys.stderr,
        )

for _key, _desc in _OPTIONAL_KEYS.items():
    if not os.getenv(_key):
        warnings.warn(
            f"Optional env var {_key} is not set — {_desc}",
            stacklevel=2,
        )

# Allow imports from project root (agents/, mcp_servers/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Receive, Scope, Send

from agents.coordinator import BrokerCoordinator, BrokerState

try:
    from backend.routes_demo import router as _demo_router
except Exception:
    _demo_router = None  # type: ignore


# ---------------------------------------------------------------------------
# Rate Limiting — Token Bucket
# ---------------------------------------------------------------------------
# One bucket per broker_id, cached for process lifetime via lru_cache.
# Rate: 10 tokens/minute (≈0.1667/sec). Burst capacity: 10 tokens.
# After capacity is exhausted, requests return 429 with Retry-After header.

class _TokenBucket:
    """
    Simple leaky-token-bucket for rate limiting.
    Not thread-safe by design — FastAPI event loop is single-threaded for async
    handlers, and run_in_executor tasks that hit rate limits read from the main
    thread's bucket via the cached reference.
    """

    def __init__(self, rate: float, capacity: int):
        self._rate = rate          # tokens per second
        self._capacity = capacity  # max burst
        self._tokens = float(capacity)
        self._last = time_mod.monotonic()

    def consume(self) -> tuple:
        """
        Try to consume one token.
        Returns (allowed: bool, retry_after_seconds: float).
        """
        now = time_mod.monotonic()
        elapsed = now - self._last
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True, 0.0
        # Seconds until one token refills
        retry_after = (1.0 - self._tokens) / self._rate
        return False, retry_after


@lru_cache(maxsize=None)
def _get_rate_bucket(broker_id: str) -> _TokenBucket:
    """Return (or create) the rate-limit bucket for a broker_id."""
    return _TokenBucket(rate=10 / 60, capacity=10)


# ---------------------------------------------------------------------------
# In-Memory State — Request Log & Broker Activity
# ---------------------------------------------------------------------------

_request_log: deque = deque(maxlen=50)     # ring buffer: last 50 requests
_broker_activity: dict = defaultdict(int)  # request count per broker_id
_ws_connections: Dict[str, WebSocket] = {} # broker_id → active WebSocket


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PeruRE Agent API",
    version="1.0.0",
    description="Hub API for the PeruRE multi-agent broker logistics system",
)


# ---------------------------------------------------------------------------
# Logging Middleware
# ---------------------------------------------------------------------------
# Logs every non-streaming request as structured JSON to stdout.
# MCP SSE paths (/mcp/*) and WebSocket paths (/ws/*) are excluded because
# BaseHTTPMiddleware wraps the response stream in a way that breaks long-lived
# streaming connections.

class _LoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        # Skip streaming endpoints to avoid breaking SSE/WS
        if request.url.path.startswith(("/mcp/", "/ws/")):
            return await call_next(request)

        start = time_mod.monotonic()
        response = await call_next(request)
        duration_ms = round((time_mod.monotonic() - start) * 1000, 2)

        broker_id = getattr(request.state, "broker_id", None)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "broker_id": broker_id,
        }
        # Structured log to stdout — captured by Docker / log aggregators
        print(json_lib.dumps(entry), flush=True)
        _request_log.append(entry)
        if broker_id:
            _broker_activity[broker_id] += 1

        return response


app.add_middleware(_LoggingMiddleware)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CoordinateRequest(BaseModel):
    broker_id: str
    instruction: str
    context: Dict[str, Any] = {}


class BatchRequest(BaseModel):
    broker_id: str
    instructions: List[str]
    context: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Liveness check used by Docker and CI."""
    return {"status": "ok", "service": "peru-re-agent", "version": "1.0.0"}


@app.post("/api/v1/coordinate")
async def coordinate(req: CoordinateRequest, request: Request):
    """
    Run the coordinator agent with a broker instruction.

    Rate-limited to 10 req/min per broker_id (burst 10).
    Broadcasts result to broker's active WebSocket if connected.
    Returns the coordinator's structured JSON response.
    """
    request.state.broker_id = req.broker_id

    allowed, retry_after = _get_rate_bucket(req.broker_id).consume()
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    coordinator = BrokerCoordinator()

    if req.context.get("broker_state"):
        bs = req.context["broker_state"]
        try:
            coordinator.update_broker_state(BrokerState(
                current_location=bs.get("current_location"),
                confirmed_appointments_today=bs.get("confirmed_appointments_today", []),
                pending_proposals=bs.get("pending_proposals", []),
                active_concerns=bs.get("active_concerns", []),
                last_updated=bs.get("last_updated", ""),
            ))
        except Exception:
            pass  # Non-fatal: coordinator works without pre-loaded state

    try:
        result = coordinator.run(req.instruction)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Real-time push to broker's WebSocket if open
    ws = _ws_connections.get(req.broker_id)
    if ws:
        try:
            await ws.send_json(result)
        except Exception:
            _ws_connections.pop(req.broker_id, None)

    return result


@app.post("/api/v1/batch")
async def batch(req: BatchRequest, request: Request):
    """
    Run multiple instructions through the coordinator in parallel.

    Uses asyncio.gather + run_in_executor so instructions run concurrently
    in the default thread pool (BrokerCoordinator.run() is synchronous).
    Results are returned in the same order as the input instructions.
    Rate-limited to 10 req/min per broker_id (1 token consumed per batch call).
    """
    request.state.broker_id = req.broker_id

    allowed, retry_after = _get_rate_bucket(req.broker_id).consume()
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    bs_payload = req.context.get("broker_state")

    def _run_one(instruction: str) -> Dict[str, Any]:
        """Execute a single coordinator run in a thread-pool worker."""
        c = BrokerCoordinator()
        if bs_payload:
            try:
                c.update_broker_state(BrokerState(
                    current_location=bs_payload.get("current_location"),
                    confirmed_appointments_today=bs_payload.get("confirmed_appointments_today", []),
                    pending_proposals=bs_payload.get("pending_proposals", []),
                    active_concerns=bs_payload.get("active_concerns", []),
                    last_updated=bs_payload.get("last_updated", ""),
                ))
            except Exception:
                pass
        try:
            return c.run(instruction)
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, _run_one, instr) for instr in req.instructions]
    results = list(await asyncio.gather(*tasks))

    # Broadcast batch summary to broker's WebSocket if open
    ws = _ws_connections.get(req.broker_id)
    if ws:
        try:
            await ws.send_json({"batch_results": results, "count": len(results)})
        except Exception:
            _ws_connections.pop(req.broker_id, None)

    return results


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

_ADMIN_HTML = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static", "admin", "index.html"
)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the in-memory admin dashboard HTML."""
    with open(_ADMIN_HTML, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/admin/data")
async def admin_data():
    """
    Return live admin data as JSON:
    - recent_requests: last 50 logged requests (ring buffer)
    - broker_activity: request count per broker_id
    - mcp_health: whether each MCP server route is mounted
    """
    mcp_names = ["maps", "calendar", "whatsapp", "property_db"]
    route_paths = [str(getattr(r, "path", "")) for r in app.routes]
    mcp_health = {
        name: any(f"/mcp/{name}" in p for p in route_paths)
        for name in mcp_names
    }
    return {
        "recent_requests": list(_request_log),
        "broker_activity": dict(_broker_activity),
        "mcp_health": mcp_health,
    }


# ---------------------------------------------------------------------------
# WebSocket — Real-Time Broker Updates
# ---------------------------------------------------------------------------

@app.websocket("/ws/broker/{broker_id}")
async def websocket_endpoint(websocket: WebSocket, broker_id: str):
    """
    Accept a WebSocket connection for a broker.
    Results from /coordinate and /batch are pushed here after each run.
    Only one connection per broker_id is maintained; a new connection replaces
    the old one (last-writer-wins for reconnect scenarios).
    """
    await websocket.accept()
    _ws_connections[broker_id] = websocket
    try:
        # Keep connection alive; client may send pings or we just wait for disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_connections.pop(broker_id, None)


# ---------------------------------------------------------------------------
# Presentation pages
# ---------------------------------------------------------------------------

_FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)

@app.get("/pitch", response_class=HTMLResponse)
async def pitch_page():
    """Landing page for client presentations."""
    path = os.path.join(_FRONTEND_DIR, "pitch.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/broker", response_class=HTMLResponse)
async def broker_page():
    """Mobile-first broker dashboard for client demos."""
    path = os.path.join(_FRONTEND_DIR, "broker.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/proposal", response_class=HTMLResponse)
async def proposal_page():
    """Printable one-page proposal template."""
    path = os.path.join(_FRONTEND_DIR, "proposal.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ---------------------------------------------------------------------------
# Demo router
# ---------------------------------------------------------------------------

if _demo_router is not None:
    app.include_router(_demo_router)

    @app.on_event("startup")
    async def _seed_demo_on_startup():
        if os.getenv("DEMO_MODE", "").lower() in ("true", "1", "yes"):
            try:
                from backend.demo_data import seed_demo_data
                seed_demo_data()
                print("[startup] Demo data seeded (DEMO_MODE=true)", flush=True)
            except Exception as exc:
                print(f"[startup] Demo seed failed: {exc}", flush=True)


# ---------------------------------------------------------------------------
# MCP server mounting
# ---------------------------------------------------------------------------
# Each MCP server (mcp.server.Server instance) is exposed via SSE transport
# at /mcp/{name}/sse (GET) and /mcp/{name}/messages/ (POST).

def _make_mcp_sub_app(server_instance, messages_path: str) -> Starlette:
    """Wrap a low-level MCP Server in a Starlette sub-app with SSE transport."""
    from mcp.server.sse import SseServerTransport
    from starlette.requests import Request as _StarletteRequest
    from starlette.responses import Response as _StarletteResponse
    from starlette.routing import Mount, Route

    sse = SseServerTransport(messages_path)

    async def _handle_sse_asgi(scope: Scope, receive: Receive, send: Send) -> None:
        async with sse.connect_sse(scope, receive, send) as streams:
            await server_instance.run(
                streams[0],
                streams[1],
                server_instance.create_initialization_options(),
            )

    async def sse_endpoint(request: _StarletteRequest) -> _StarletteResponse:
        await _handle_sse_asgi(request.scope, request.receive, request._send)  # type: ignore[reportPrivateUsage]
        return _StarletteResponse()

    return Starlette(routes=[
        Route("/sse", endpoint=sse_endpoint, methods=["GET"]),
        Mount("/messages/", app=sse.handle_post_message),
    ])


_MCP_SERVERS = [
    ("maps",        "mcp_servers.maps.server"),
    ("calendar",    "mcp_servers.calendar.server"),
    ("whatsapp",    "mcp_servers.whatsapp.server"),
    ("property_db", "mcp_servers.property_db.server"),
]

for _name, _mod_path in _MCP_SERVERS:
    try:
        _mod = importlib.import_module(_mod_path)
        _sub = _make_mcp_sub_app(_mod.app, "/messages/")
        app.mount(f"/mcp/{_name}", _sub)
    except Exception:
        pass  # Best-effort: skip servers that fail to load


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
# Mounted last so all /api/*, /mcp/*, /admin, /ws/* routes take precedence.

_FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

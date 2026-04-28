"""
MCP Server: Peru Property Database
==================================
Property listings, client profiles, and intelligent matching.
Demonstrates: MCP resources for content catalogs, structured queries.

Priority 4 additions:
- PostgreSQL ThreadedConnectionPool when DATABASE_URL is set.
- SQLite in-memory fallback (with seed data) when DATABASE_URL is absent.
- Schema auto-init on first connection (simplified schema without PostGIS).
  For full PostGIS schema use mcp_servers/property_db/schema.sql via Docker.
- psycopg2 import is guarded — ImportError falls back to SQLite gracefully.
- Connection cleanup via context manager (getconn/putconn for PG, lock for SQLite).
"""

import json
import logging
import os
import sqlite3
import threading
import warnings
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from mcp.server import Server
from mcp.types import TextContent, Tool

app = Server("peru_property_db")
logger = logging.getLogger(__name__)

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# ── DB state (mutated by _init_db) ─────────────────────────────────────────────
_USE_PG: bool = False
_pg_pool: Optional[Any] = None          # psycopg2.pool.ThreadedConnectionPool
_sqlite_conn: Optional[sqlite3.Connection] = None
_sqlite_lock = threading.Lock()
_PH: str = "?"                          # SQL placeholder: ? (SQLite) or %s (PG)

# ── Schemas ────────────────────────────────────────────────────────────────────
# SQLite-compatible (no PostGIS, no JSONB, no arrays — JSON stored as TEXT).
_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id          TEXT PRIMARY KEY,
    address     TEXT NOT NULL,
    district    TEXT NOT NULL,
    price_usd   REAL NOT NULL,
    sqm         REAL,
    bedrooms    INTEGER,
    type        TEXT,
    status      TEXT DEFAULT 'available',
    features    TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS clients (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    phone                 TEXT NOT NULL,
    budget_usd            REAL,
    preferred_districts   TEXT DEFAULT '[]',
    financing_status      TEXT DEFAULT 'unknown',
    financing_score       INTEGER,
    documents_status      TEXT DEFAULT '{}',
    status                TEXT DEFAULT 'new',
    do_not_contact        INTEGER DEFAULT 0
);
"""

# PostgreSQL version without PostGIS (works on plain Postgres, not just the
# Docker image that has PostGIS).  The full PostGIS schema lives in schema.sql.
_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id          TEXT PRIMARY KEY,
    address     TEXT NOT NULL,
    district    TEXT NOT NULL,
    price_usd   NUMERIC NOT NULL,
    sqm         NUMERIC,
    bedrooms    INTEGER,
    type        TEXT,
    status      TEXT DEFAULT 'available',
    features    JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS clients (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    phone                 TEXT NOT NULL,
    budget_usd            NUMERIC,
    preferred_districts   TEXT[] DEFAULT '{}',
    financing_status      TEXT  DEFAULT 'unknown',
    financing_score       INTEGER,
    documents_status      JSONB DEFAULT '{}',
    status                TEXT DEFAULT 'new',
    do_not_contact        BOOLEAN DEFAULT FALSE
);
"""

# ── Seed data (used to populate SQLite; mirrors the 5 demo properties) ─────────
_SEED_PROPERTIES = [
    {"id": "PROP-2847", "address": "Jr. Las Lomas 432, Miraflores",    "district": "Miraflores", "price_usd": 185000, "sqm": 85,  "bedrooms": 2, "type": "apartment", "status": "available", "features": ["gym", "pool", "security"]},
    {"id": "PROP-2911", "address": "Av. Larco 780, Miraflores",        "district": "Miraflores", "price_usd": 210000, "sqm": 95,  "bedrooms": 3, "type": "apartment", "status": "available", "features": ["ocean_view", "parking"]},
    {"id": "PROP-3022", "address": "Calle Las Flores 120, San Borja",  "district": "San Borja",  "price_usd": 165000, "sqm": 78,  "bedrooms": 2, "type": "apartment", "status": "available", "features": ["garden", "pet_friendly"]},
    {"id": "PROP-3155", "address": "Av. Circunvalación 450, Surco",    "district": "Surco",      "price_usd": 195000, "sqm": 110, "bedrooms": 3, "type": "house",     "status": "available", "features": ["backyard", "garage"]},
    {"id": "PROP-3201", "address": "Av. Primavera 200, La Molina",     "district": "La Molina",  "price_usd": 320000, "sqm": 150, "bedrooms": 4, "type": "house",     "status": "available", "features": ["pool", "security", "gated"]},
]

_SEED_CLIENTS = [
    {"id": "CLI-1001", "name": "María González",   "phone": "51999123456", "budget_usd": 180000, "preferred_districts": ["Miraflores", "San Borja"], "financing_status": "pre_approved", "financing_score": 82,  "documents_status": {"dni": True, "pay_stubs": True, "tax_returns": True, "pre_approval": True},  "status": "qualified", "do_not_contact": False},
    {"id": "CLI-1002", "name": "Carlos Rodríguez", "phone": "51999876543", "budget_usd": 220000, "preferred_districts": ["Miraflores", "San Isidro"], "financing_status": "pending",      "financing_score": 55,  "documents_status": {"dni": True, "pay_stubs": True, "tax_returns": False, "pre_approval": False}, "status": "needs_docs","do_not_contact": False},
    {"id": "CLI-1003", "name": "Ana Lucero",        "phone": "51999445566", "budget_usd": 160000, "preferred_districts": ["Surco", "San Borja"],       "financing_status": "cash",         "financing_score": 90,  "documents_status": {"dni": True, "pay_stubs": True, "tax_returns": True, "pre_approval": False},  "status": "qualified", "do_not_contact": False},
]


# ── DB initialisation ──────────────────────────────────────────────────────────

def _init_db() -> None:
    global _USE_PG, _pg_pool, _sqlite_conn, _PH

    if DATABASE_URL:
        try:
            import psycopg2.pool  # noqa: PLC0415
            import psycopg2.extras  # noqa: PLC0415

            _pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 5, dsn=DATABASE_URL)
            _init_pg_schema()
            _USE_PG = True
            _PH = "%s"
            logger.info("property_db: connected to PostgreSQL via ThreadedConnectionPool")
            return
        except ImportError:
            warnings.warn("psycopg2 not installed; falling back to SQLite in-memory DB", stacklevel=2)
        except Exception as exc:
            warnings.warn(
                f"PostgreSQL connection failed ({exc}); falling back to SQLite in-memory DB",
                stacklevel=2,
            )

    # SQLite path
    _sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
    _sqlite_conn.row_factory = sqlite3.Row
    _sqlite_conn.executescript(_SQLITE_SCHEMA)
    _sqlite_conn.commit()
    _seed_sqlite()
    _USE_PG = False
    _PH = "?"
    logger.info("property_db: using SQLite in-memory database (development mode)")


def _init_pg_schema() -> None:
    """Create tables on PostgreSQL if they don't exist."""
    assert _pg_pool is not None
    import psycopg2.extras  # noqa: PLC0415

    conn = _pg_pool.getconn()
    try:
        # Try full schema.sql first (PostGIS available in Docker)
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.isfile(schema_path):
            with open(schema_path, encoding="utf-8") as f:
                sql = f.read()
            try:
                with conn.cursor() as cur:
                    # Execute statements individually; skip failures (e.g. PostGIS missing)
                    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
                        try:
                            cur.execute(stmt)
                        except Exception:
                            conn.rollback()
                conn.commit()
                return
            except Exception:
                conn.rollback()

        # Fallback: simplified schema without PostGIS
        with conn.cursor() as cur:
            cur.execute(_PG_SCHEMA)
        conn.commit()
    finally:
        _pg_pool.putconn(conn)


def _seed_sqlite() -> None:
    """Insert seed properties and clients into SQLite if tables are empty."""
    assert _sqlite_conn is not None
    cur = _sqlite_conn.cursor()

    # Only seed if tables are empty to keep init idempotent
    cur.execute("SELECT COUNT(*) FROM properties")
    if cur.fetchone()[0] == 0:
        for p in _SEED_PROPERTIES:
            cur.execute(
                "INSERT OR IGNORE INTO properties (id, address, district, price_usd, sqm, bedrooms, type, status, features) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (p["id"], p["address"], p["district"], p["price_usd"],
                 p["sqm"], p["bedrooms"], p["type"], p["status"],
                 json.dumps(p["features"])),
            )

    cur.execute("SELECT COUNT(*) FROM clients")
    if cur.fetchone()[0] == 0:
        for c in _SEED_CLIENTS:
            cur.execute(
                "INSERT OR IGNORE INTO clients "
                "(id, name, phone, budget_usd, preferred_districts, financing_status, "
                "financing_score, documents_status, status, do_not_contact) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (c["id"], c["name"], c["phone"], c["budget_usd"],
                 json.dumps(c["preferred_districts"]), c["financing_status"],
                 c["financing_score"], json.dumps(c["documents_status"]),
                 c["status"], int(c["do_not_contact"])),
            )
    _sqlite_conn.commit()


# ── Cursor context manager ─────────────────────────────────────────────────────

@contextmanager
def _get_cursor() -> Generator:
    if _USE_PG:
        import psycopg2.extras  # noqa: PLC0415

        assert _pg_pool is not None
        conn = _pg_pool.getconn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
        finally:
            _pg_pool.putconn(conn)
    else:
        assert _sqlite_conn is not None
        with _sqlite_lock:
            cur = _sqlite_conn.cursor()
            try:
                yield cur
                _sqlite_conn.commit()
            except Exception:
                _sqlite_conn.rollback()
                raise
            finally:
                cur.close()


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Normalise a DB row to a plain dict, parsing JSON string fields for SQLite."""
    d = dict(row)
    if not _USE_PG:
        for field in ("features", "documents_status"):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        if isinstance(d.get("preferred_districts"), str):
            try:
                d["preferred_districts"] = json.loads(d["preferred_districts"])
            except (json.JSONDecodeError, TypeError):
                d["preferred_districts"] = []
        # Normalise SQLite integer boolean
        if "do_not_contact" in d:
            d["do_not_contact"] = bool(d["do_not_contact"])
    return d


# ── Tool list ──────────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="query_properties",
            description=(
                "Query available properties by district, price range, size, and type. "
                "Use for matching clients to listings or checking inventory in a district."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "districts": {"type": "array", "items": {"type": "string"}, "description": "Filter by Lima district(s)"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "property_type": {"type": "string", "enum": ["apartment", "house", "office", "land"]},
                    "min_bedrooms": {"type": "integer"},
                },
            },
        ),
        Tool(
            name="match_client_to_properties",
            description=(
                "Score and rank properties for a specific client based on budget, district preferences, and financing readiness. "
                "Returns top 5 matches with scores and reasoning. Use when qualifying a lead or preparing showing recommendations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "budget_usd": {"type": "number"},
                    "preferred_districts": {"type": "array", "items": {"type": "string"}},
                    "property_type": {"type": "string", "enum": ["apartment", "house", "office", "land"]},
                    "financing_status": {"type": "string", "enum": ["cash", "pre_approved", "pending", "unknown"]},
                },
                "required": ["client_id", "budget_usd"],
            },
        ),
        Tool(
            name="store_client",
            description="Store or update a client profile in the database. Use when a new lead is qualified or profile changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "budget_usd": {"type": "number"},
                    "preferred_districts": {"type": "array", "items": {"type": "string"}},
                    "financing_status": {"type": "string", "enum": ["cash", "pre_approved", "pending", "unknown"]},
                    "financing_score": {"type": "integer", "description": "0-100 readiness score"},
                    "documents_status": {"type": "object", "properties": {"dni": {"type": "boolean"}, "pay_stubs": {"type": "boolean"}, "tax_returns": {"type": "boolean"}, "pre_approval": {"type": "boolean"}}},
                    "status": {"type": "string", "enum": ["new", "qualified", "needs_docs", "waitlist", "closed"]},
                    "do_not_contact": {"type": "boolean", "default": False},
                },
                "required": ["client_id", "name", "phone"],
            },
        ),
        Tool(
            name="get_client",
            description="Retrieve a client profile by ID. Use before appointments to check document readiness.",
            inputSchema={
                "type": "object",
                "properties": {"client_id": {"type": "string"}},
                "required": ["client_id"],
            },
        ),
    ]


# ── Resource listing ───────────────────────────────────────────────────────────

@app.list_resources()
async def list_resources() -> List[Dict[str, str]]:
    """Expose property catalog summary as an MCP resource."""
    try:
        with _get_cursor() as cur:
            cur.execute("SELECT district, price_usd FROM properties WHERE status = 'available'")
            rows = [_row_to_dict(r) for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) as n FROM properties WHERE status = 'available'")
            count_row = cur.fetchone()
            total = dict(count_row)["n"] if count_row else len(rows)

        districts = list({r["district"] for r in rows})
        prices = [r["price_usd"] for r in rows]
        price_range = {"min": min(prices), "max": max(prices)} if prices else {"min": 0, "max": 0}
    except Exception:
        districts = []
        price_range = {"min": 0, "max": 0}
        total = 0

    return [
        {
            "uri": "peru://property-catalog",
            "mimeType": "application/json",
            "name": "Property Catalog Summary",
            "text": json.dumps({"districts": districts, "price_range": price_range, "total_available": total}),
        }
    ]


# ── Tool dispatch ──────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    try:
        if name == "query_properties":
            return [TextContent(type="text", text=json.dumps(_query_properties(arguments), indent=2))]
        elif name == "match_client_to_properties":
            return [TextContent(type="text", text=json.dumps(_match_client(arguments), indent=2))]
        elif name == "store_client":
            return [TextContent(type="text", text=json.dumps(_store_client(arguments), indent=2))]
        elif name == "get_client":
            return [TextContent(type="text", text=json.dumps(_get_client(arguments), indent=2))]
        else:
            return _error("validation", False, f"Unknown tool: {name}")
    except Exception as e:
        return _error("transient", True, str(e))


# ── CRUD functions ─────────────────────────────────────────────────────────────

def _query_properties(args: Dict[str, Any]) -> Dict[str, Any]:
    conditions = ["status = " + _PH]
    params: List[Any] = ["available"]

    if args.get("districts"):
        ph_list = ",".join([_PH] * len(args["districts"]))
        conditions.append(f"district IN ({ph_list})")
        params.extend(args["districts"])
    if args.get("min_price") is not None:
        conditions.append(f"price_usd >= {_PH}")
        params.append(args["min_price"])
    if args.get("max_price") is not None:
        conditions.append(f"price_usd <= {_PH}")
        params.append(args["max_price"])
    if args.get("property_type"):
        conditions.append(f"type = {_PH}")
        params.append(args["property_type"])
    if args.get("min_bedrooms") is not None:
        conditions.append(f"bedrooms >= {_PH}")
        params.append(args["min_bedrooms"])

    sql = "SELECT * FROM properties WHERE " + " AND ".join(conditions)

    with _get_cursor() as cur:
        cur.execute(sql, params)
        rows = [_row_to_dict(r) for r in cur.fetchall()]

    return {"count": len(rows), "properties": rows}


def _match_client(args: Dict[str, Any]) -> Dict[str, Any]:
    budget = args["budget_usd"]
    districts = args.get("preferred_districts", [])
    prop_type = args.get("property_type")
    financing = args.get("financing_status", "unknown")

    # Fetch all available properties from DB, score in Python
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM properties WHERE status = " + _PH, ["available"])
        candidates = [_row_to_dict(r) for r in cur.fetchall()]

    scored = []
    for p in candidates:
        score = 0
        reasons: List[str] = []

        diff = abs(p["price_usd"] - budget) / budget
        if diff <= 0.15:
            score += 100
            reasons.append("within_budget")
        elif diff <= 0.30:
            score += 50
            reasons.append("close_to_budget")

        if not districts or p["district"] in districts:
            score += 50
            reasons.append("preferred_district")
        elif p["district"] in _adjacent_districts(districts):
            score += 25
            reasons.append("adjacent_district")

        if prop_type and p["type"] == prop_type:
            score += 30
            reasons.append("type_match")

        fast_close = financing in ["cash", "pre_approved"]
        if fast_close:
            score += 20
            reasons.append("financing_ready")

        scored.append({
            "property": p,
            "match_score": score,
            "match_reasons": reasons,
            "fast_close_eligible": fast_close and score >= 70,
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    top = scored[:5]

    return {
        "client_id": args["client_id"],
        "matches": [
            {
                "property_id": s["property"]["id"],
                "address": s["property"]["address"],
                "price_usd": s["property"]["price_usd"],
                "sqm": s["property"]["sqm"],
                "bedrooms": s["property"]["bedrooms"],
                "match_score": s["match_score"],
                "match_reasons": s["match_reasons"],
                "fast_close_eligible": s["fast_close_eligible"],
            }
            for s in top
        ],
        "alternative_districts": list({p["district"] for p in candidates if p["district"] not in districts})[:3],
    }


def _store_client(args: Dict[str, Any]) -> Dict[str, Any]:
    districts = json.dumps(args.get("preferred_districts", [])) if not _USE_PG else args.get("preferred_districts", [])
    docs = json.dumps(args.get("documents_status", {})) if not _USE_PG else args.get("documents_status", {})
    do_not_contact = int(args.get("do_not_contact", False)) if not _USE_PG else bool(args.get("do_not_contact", False))

    with _get_cursor() as cur:
        if _USE_PG:
            cur.execute(
                """
                INSERT INTO clients (id, name, phone, budget_usd, preferred_districts,
                    financing_status, financing_score, documents_status, status, do_not_contact)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    budget_usd = EXCLUDED.budget_usd,
                    preferred_districts = EXCLUDED.preferred_districts,
                    financing_status = EXCLUDED.financing_status,
                    financing_score = EXCLUDED.financing_score,
                    documents_status = EXCLUDED.documents_status,
                    status = EXCLUDED.status,
                    do_not_contact = EXCLUDED.do_not_contact
                """,
                (
                    args["client_id"], args["name"], args["phone"],
                    args.get("budget_usd"), args.get("preferred_districts", []),
                    args.get("financing_status", "unknown"), args.get("financing_score"),
                    json.dumps(args.get("documents_status", {})),
                    args.get("status", "new"), bool(args.get("do_not_contact", False)),
                ),
            )
        else:
            cur.execute(
                """
                INSERT OR REPLACE INTO clients
                    (id, name, phone, budget_usd, preferred_districts,
                     financing_status, financing_score, documents_status, status, do_not_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    args["client_id"], args["name"], args["phone"],
                    args.get("budget_usd"), districts,
                    args.get("financing_status", "unknown"), args.get("financing_score"),
                    docs, args.get("status", "new"), do_not_contact,
                ),
            )

    return {"status": "success", "client_id": args["client_id"], "operation": "stored"}


def _get_client(args: Dict[str, Any]) -> Dict[str, Any]:
    cid = args["client_id"]
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM clients WHERE id = " + _PH, [cid])
        row = cur.fetchone()

    if row is None:
        return {"isError": True, "errorCategory": "validation", "description": f"Client {cid} not found."}
    return {"status": "success", "client": _row_to_dict(row)}


# ── Matching helpers ───────────────────────────────────────────────────────────

def _adjacent_districts(districts: List[str]) -> List[str]:
    adjacency = {
        "Miraflores": ["San Isidro", "Barranco", "Surco"],
        "San Isidro": ["Miraflores", "Lince", "Surco"],
        "Surco": ["Miraflores", "San Isidro", "San Borja", "La Molina"],
        "San Borja": ["Surco", "La Molina", "Jesús María"],
        "La Molina": ["Surco", "San Borja", "Ate"],
        "Barranco": ["Miraflores", "Chorrillos"],
        "Lince": ["San Isidro", "Jesús María", "Magdalena"],
        "Jesús María": ["Lince", "San Borja", "Pueblo Libre"],
    }
    result: List[str] = []
    for d in districts:
        result.extend(adjacency.get(d, []))
    return list(set(result))


def _error(category: str, retryable: bool, description: str) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps({
        "isError": True,
        "errorCategory": category,
        "isRetryable": retryable,
        "description": description,
    }, indent=2))]


# ── Initialise DB at module load ───────────────────────────────────────────────
_init_db()


if __name__ == "__main__":
    import asyncio

    from mcp.server.stdio import stdio_server

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(main())

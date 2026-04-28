"""
MCP Server: Peru Property Database
==================================
Property listings, client profiles, and intelligent matching.
Demonstrates: MCP resources for content catalogs, structured queries.
"""

import os
import json
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("peru_property_db")

# Mock database for portfolio demonstration
_PROPERTIES = [
    {"id": "PROP-2847", "address": "Jr. Las Lomas 432, Miraflores", "district": "Miraflores", "price_usd": 185000, "sqm": 85, "bedrooms": 2, "type": "apartment", "status": "available", "features": ["gym", "pool", "security"]},
    {"id": "PROP-2911", "address": "Av. Larco 780, Miraflores", "district": "Miraflores", "price_usd": 210000, "sqm": 95, "bedrooms": 3, "type": "apartment", "status": "available", "features": ["ocean_view", "parking"]},
    {"id": "PROP-3022", "address": "Calle Las Flores 120, San Borja", "district": "San Borja", "price_usd": 165000, "sqm": 78, "bedrooms": 2, "type": "apartment", "status": "available", "features": ["garden", "pet_friendly"]},
    {"id": "PROP-3155", "address": "Av. Circunvalación 450, Surco", "district": "Surco", "price_usd": 195000, "sqm": 110, "bedrooms": 3, "type": "house", "status": "available", "features": ["backyard", "garage"]},
    {"id": "PROP-3201", "address": "Av. Primavera 200, La Molina", "district": "La Molina", "price_usd": 320000, "sqm": 150, "bedrooms": 4, "type": "house", "status": "available", "features": ["pool", "security", "gated"]},
]

_CLIENTS = {}


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
                    "min_bedrooms": {"type": "integer"}
                }
            }
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
                    "financing_status": {"type": "string", "enum": ["cash", "pre_approved", "pending", "unknown"]}
                },
                "required": ["client_id", "budget_usd"]
            }
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
                    "do_not_contact": {"type": "boolean", "default": False}
                },
                "required": ["client_id", "name", "phone"]
            }
        ),
        Tool(
            name="get_client",
            description="Retrieve a client profile by ID. Use before appointments to check document readiness.",
            inputSchema={
                "type": "object",
                "properties": {"client_id": {"type": "string"}},
                "required": ["client_id"]
            }
        )
    ]


@app.list_resources()
async def list_resources() -> List[Dict[str, str]]:
    """
    Expose content catalog as MCP resource so agents can browse
    available districts and price ranges without exploratory tool calls.
    """
    districts = list(set(p["district"] for p in _PROPERTIES))
    price_range = {
        "min": min(p["price_usd"] for p in _PROPERTIES),
        "max": max(p["price_usd"] for p in _PROPERTIES)
    }
    return [
        {"uri": "peru://property-catalog", "mimeType": "application/json", "name": "Property Catalog Summary", "text": json.dumps({"districts": districts, "price_range": price_range, "total_available": len([p for p in _PROPERTIES if p["status"] == "available"])})}
    ]


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


def _query_properties(args: Dict[str, Any]) -> Dict[str, Any]:
    results = [p for p in _PROPERTIES if p["status"] == "available"]
    
    if args.get("districts"):
        results = [p for p in results if p["district"] in args["districts"]]
    if args.get("min_price"):
        results = [p for p in results if p["price_usd"] >= args["min_price"]]
    if args.get("max_price"):
        results = [p for p in results if p["price_usd"] <= args["max_price"]]
    if args.get("property_type"):
        results = [p for p in results if p["type"] == args["property_type"]]
    if args.get("min_bedrooms"):
        results = [p for p in results if p["bedrooms"] >= args["min_bedrooms"]]
    
    return {"count": len(results), "properties": results}


def _match_client(args: Dict[str, Any]) -> Dict[str, Any]:
    budget = args["budget_usd"]
    districts = args.get("preferred_districts", [])
    prop_type = args.get("property_type")
    financing = args.get("financing_status", "unknown")
    
    candidates = [p for p in _PROPERTIES if p["status"] == "available"]
    scored = []
    
    for p in candidates:
        score = 0
        reasons = []
        
        # Budget fit: ±15% = 100pts, ±30% = 50pts
        diff = abs(p["price_usd"] - budget) / budget
        if diff <= 0.15:
            score += 100; reasons.append("within_budget")
        elif diff <= 0.30:
            score += 50; reasons.append("close_to_budget")
        
        # District preference
        if not districts or p["district"] in districts:
            score += 50; reasons.append("preferred_district")
        elif p["district"] in _adjacent_districts(districts):
            score += 25; reasons.append("adjacent_district")
        
        # Property type
        if prop_type and p["type"] == prop_type:
            score += 30; reasons.append("type_match")
        
        # Financing bonus
        fast_close = financing in ["cash", "pre_approved"]
        if fast_close:
            score += 20; reasons.append("financing_ready")
        
        scored.append({
            "property": p,
            "match_score": score,
            "match_reasons": reasons,
            "fast_close_eligible": fast_close and score >= 70
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
                "fast_close_eligible": s["fast_close_eligible"]
            }
            for s in top
        ],
        "alternative_districts": list(set(p["district"] for p in candidates if p["district"] not in districts))[:3]
    }


def _store_client(args: Dict[str, Any]) -> Dict[str, Any]:
    _CLIENTS[args["client_id"]] = args
    return {"status": "success", "client_id": args["client_id"], "operation": "stored"}


def _get_client(args: Dict[str, Any]) -> Dict[str, Any]:
    cid = args["client_id"]
    if cid not in _CLIENTS:
        return {"isError": True, "errorCategory": "validation", "description": f"Client {cid} not found."}
    return {"status": "success", "client": _CLIENTS[cid]}


def _adjacent_districts(districts: List[str]) -> List[str]:
    adjacency = {
        "Miraflores": ["San Isidro", "Barranco", "Surco"],
        "San Isidro": ["Miraflores", "Lince", "Surco"],
        "Surco": ["Miraflores", "San Isidro", "San Borja", "La Molina"],
        "San Borja": ["Surco", "La Molina", "Jesús María"],
        "La Molina": ["Surco", "San Borja", "Ate"],
        "Barranco": ["Miraflores", "Chorrillos"],
        "Lince": ["San Isidro", "Jesús María", "Magdalena"],
        "Jesús María": ["Lince", "San Borja", "Pueblo Libre"]
    }
    result = []
    for d in districts:
        result.extend(adjacency.get(d, []))
    return list(set(result))


def _error(category: str, retryable: bool, description: str) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps({
        "isError": True, "errorCategory": category, "isRetryable": retryable, "description": description
    }, indent=2))]


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    
    asyncio.run(main())

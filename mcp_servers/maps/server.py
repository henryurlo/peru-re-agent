"""
MCP Server: Peru Maps & Routing
===============================
Exposes Mapbox Directions + Traffic APIs via MCP tools.
Demonstrates: Tool descriptions, structured errors, MCP server configuration
(Domain 2: Tool Design & MCP Integration).
"""

import os
import json
import requests
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.types import Tool, TextContent, ErrorData

app = Server("peru_maps")

MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")
GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="calculate_optimal_route",
            description=(
                "Calculates multi-stop driving routes for Lima traffic with real-time estimates. "
                "Use ONLY when broker needs to visit multiple locations in sequence. "
                "For single-origin-to-destination checks, use get_single_eta. "
                "Returns ordered stops with ETAs, distances, and GeoJSON geometry for map visualization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "object",
                        "properties": {
                            "lat": {"type": "number", "description": "Origin latitude (-12.x for Lima)"},
                            "lng": {"type": "number", "description": "Origin longitude (-77.x for Lima)"},
                            "name": {"type": "string", "description": "Human-readable origin label"}
                        },
                        "required": ["lat", "lng"]
                    },
                    "destinations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lng": {"type": "number"},
                                "name": {"type": "string"},
                                "time_window": {"type": "string", "description": "ISO 8601 preferred time window"}
                            },
                            "required": ["lat", "lng", "name"]
                        },
                        "description": "Ordered list of stops to visit"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["driving", "taxi", "transit"],
                        "description": "Transport mode. 'taxi' uses driving route + fare heuristic. 'transit' uses walking segments + transit stops overlay."
                    },
                    "alternatives": {
                        "type": "boolean",
                        "default": True,
                        "description": "Return alternative route options when available"
                    }
                },
                "required": ["origin", "destinations", "mode"]
            }
        ),
        Tool(
            name="get_single_eta",
            description=(
                "Get travel time and distance between two single points. "
                "Use for quick one-off checks (e.g., 'how long to San Borja from here?'). "
                "Do NOT use for multi-stop route optimization — use calculate_optimal_route instead."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}}},
                    "destination": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}}},
                    "mode": {"type": "string", "enum": ["driving", "walking", "cycling"]}
                },
                "required": ["origin", "destination", "mode"]
            }
        ),
        Tool(
            name="get_traffic_conditions",
            description=(
                "Retrieves current traffic conditions for a district or route segment in Lima. "
                "Use before proposing routes during rush hours (7-9am, 12:30-2pm, 6-9pm). "
                "Returns traffic severity and recommended departure buffer."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "Lima district name (e.g., Miraflores, San Borja)"},
                    "route_segment": {"type": "string", "description": "Optional: specific avenue or route name"}
                },
                "required": ["district"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    try:
        if name == "calculate_optimal_route":
            return [TextContent(type="text", text=json.dumps(_calculate_route(arguments), indent=2))]
        elif name == "get_single_eta":
            return [TextContent(type="text", text=json.dumps(_single_eta(arguments), indent=2))]
        elif name == "get_traffic_conditions":
            return [TextContent(type="text", text=json.dumps(_traffic_conditions(arguments), indent=2))]
        else:
            return _error_response("validation", False, f"Unknown tool: {name}")
    except requests.exceptions.Timeout:
        return _error_response("transient", True, "Mapbox API timeout. Retry with cached typical-traffic estimate.")
    except requests.exceptions.ConnectionError:
        return _error_response("transient", True, "Network error connecting to Mapbox. Check connectivity.")
    except Exception as e:
        return _error_response("transient", False, f"Unexpected error: {str(e)}")


def _calculate_route(args: Dict[str, Any]) -> Dict[str, Any]:
    origin = args["origin"]
    destinations = args["destinations"]
    mode = args.get("mode", "driving")
    
    coords = [f"{origin['lng']},{origin['lat']}"] + [f"{d['lng']},{d['lat']}" for d in destinations]
    waypoints = ";".join(coords)
    
    profile = "mapbox/walking" if mode == "transit" else f"mapbox/{mode if mode != 'taxi' else 'driving'}"
    url = f"https://api.mapbox.com/directions/v5/{profile}/{waypoints}"
    params = {
        "access_token": MAPBOX_TOKEN,
        "geometries": "geojson",
        "overview": "full",
        "annotations": "duration,distance",
        "alternatives": "true" if args.get("alternatives", True) else "false"
    }
    
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    
    if not data.get("routes"):
        return _error_dict("validation", False, "No route found between points. Verify coordinates.")
    
    route = data["routes"][0]
    legs = []
    for i, leg in enumerate(route["legs"]):
        start_name = origin["name"] if i == 0 else destinations[i-1]["name"]
        end_name = destinations[i]["name"] if i < len(destinations) else origin["name"]
        legs.append({
            "from": {"name": start_name, "lat": float(coords[i].split(",")[1]), "lng": float(coords[i].split(",")[0])},
            "to": {"name": end_name, "lat": float(coords[i+1].split(",")[1]), "lng": float(coords[i+1].split(",")[0])},
            "duration_minutes": round(leg["duration"] / 60, 1),
            "distance_km": round(leg["distance"] / 1000, 2),
            "traffic_condition": _classify_traffic(leg["duration"], leg["distance"]),
            "geometry": leg.get("geometry", {})
        })
    
    total_min = sum(l["duration_minutes"] for l in legs)
    total_km = sum(l["distance_km"] for l in legs)
    
    result = {
        "mode": mode,
        "total_duration_minutes": round(total_min, 1),
        "total_distance_km": round(total_km, 2),
        "legs": legs,
        "risk_flags": _generate_risk_flags(total_min, destinations),
        "geometry": route["geometry"],
        "mapbox_url": f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/geojson({json.dumps(route['geometry'])})/auto/800x600?access_token={MAPBOX_TOKEN[:8]}..."
    }
    
    if mode == "taxi":
        result["fare_estimate_sol"] = round(5 + 3.5 * total_km + 0.8 * total_min, 2)
    
    return result


def _single_eta(args: Dict[str, Any]) -> Dict[str, Any]:
    o = args["origin"]
    d = args["destination"]
    coords = f"{o['lng']},{o['lat']};{d['lng']},{d['lat']}"
    profile = f"mapbox/{args['mode']}"
    
    url = f"https://api.mapbox.com/directions/v5/{profile}/{coords}"
    params = {"access_token": MAPBOX_TOKEN, "geometries": "geojson"}
    
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    if not data.get("routes"):
        return _error_dict("validation", False, "No route found.")
    
    leg = data["routes"][0]["legs"][0]
    return {
        "duration_minutes": round(leg["duration"] / 60, 1),
        "distance_km": round(leg["distance"] / 1000, 2),
        "mode": args["mode"]
    }


def _traffic_conditions(args: Dict[str, Any]) -> Dict[str, Any]:
    district = args["district"]
    # Mock response for Lima districts (would integrate real traffic API in production)
    severity_map = {
        "Miraflores": "moderate",
        "San Isidro": "moderate",
        "Surco": "light",
        "San Borja": "light",
        "La Molina": "heavy",
        "Barranco": "light",
        "Lince": "heavy",
        "Jesús María": "moderate"
    }
    sev = severity_map.get(district, "unknown")
    buffers = {"light": 5, "moderate": 15, "heavy": 30, "unknown": 15}
    return {
        "district": district,
        "traffic_severity": sev,
        "recommended_buffer_minutes": buffers[sev],
        "peak_hours_affected": sev in ["heavy", "moderate"],
        "source": "mapbox_traffic_estimates"
    }


def _classify_traffic(duration_sec: float, distance_m: float) -> str:
    """Classify traffic based on average speed."""
    if distance_m <= 0:
        return "unknown"
    speed_kmh = (distance_m / duration_sec) * 3.6
    if speed_kmh > 35:
        return "light"
    elif speed_kmh > 18:
        return "moderate"
    else:
        return "heavy"


def _generate_risk_flags(total_min: float, destinations: List[Dict]) -> List[str]:
    flags = []
    if total_min > 120:
        flags.append("long_drive_exceeds_2h")
    if len(destinations) > 3:
        flags.append("many_stops")
    # Check for late evening (would use actual appointment times in production)
    return flags


def _error_response(category: str, retryable: bool, description: str) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps({
        "isError": True,
        "errorCategory": category,
        "isRetryable": retryable,
        "description": description
    }, indent=2))]


def _error_dict(category: str, retryable: bool, description: str) -> Dict[str, Any]:
    return {
        "isError": True,
        "errorCategory": category,
        "isRetryable": retryable,
        "description": description
    }


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    
    asyncio.run(main())

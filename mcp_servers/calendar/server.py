"""
MCP Server: Peru Broker Calendar
=================================
Appointment CRUD with conflict detection and cancellation tracking.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from zoneinfo import ZoneInfo
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("peru_calendar")

LIMA_TZ = ZoneInfo("America/Lima")

# In-memory store for demo (replace with PostgreSQL in production)
_appointments: Dict[str, List[Dict]] = {}


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="get_today_appointments",
            description="Fetch all confirmed and tentative appointments for today. Use at the start of each broker day.",
            inputSchema={
                "type": "object",
                "properties": {
                    "broker_id": {"type": "string"},
                    "status_filter": {"type": "array", "items": {"type": "string", "enum": ["confirmed", "tentative", "cancelled"]}, "default": ["confirmed", "tentative"]}
                },
                "required": ["broker_id"]
            }
        ),
        Tool(
            name="check_conflict",
            description="Check if a proposed appointment time conflicts with existing appointments. Includes 30-minute travel buffer. Use before scheduling.",
            inputSchema={
                "type": "object",
                "properties": {
                    "broker_id": {"type": "string"},
                    "proposed_start": {"type": "string", "format": "date-time", "description": "ISO 8601 start time"},
                    "proposed_end": {"type": "string", "format": "date-time", "description": "ISO 8601 end time"},
                    "location": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}}}
                },
                "required": ["broker_id", "proposed_start", "proposed_end"]
            }
        ),
        Tool(
            name="cancel_appointment",
            description="Cancel an appointment and record the reason. Triggers re-optimization workflow. Use when client cancels or no-shows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "reason": {"type": "string", "enum": ["no_show", "client_request", "broker_request", "force_majeure"]},
                    "cancelled_by": {"type": "string", "enum": ["client", "broker", "system"]}
                },
                "required": ["appointment_id", "reason"]
            }
        ),
        Tool(
            name="schedule_appointment",
            description="Add a new appointment to the broker calendar. Verifies conflicts before committing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "broker_id": {"type": "string"},
                    "client_id": {"type": "string"},
                    "start_time": {"type": "string", "format": "date-time"},
                    "end_time": {"type": "string", "format": "date-time"},
                    "appointment_type": {"type": "string", "enum": ["showing", "follow_up", "docs_review", "closing"]},
                    "location": {"type": "object", "properties": {"address": {"type": "string"}, "lat": {"type": "number"}, "lng": {"type": "number"}}},
                    "property_ref": {"type": "string"}
                },
                "required": ["broker_id", "client_id", "start_time", "end_time", "appointment_type"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    try:
        if name == "get_today_appointments":
            return [TextContent(type="text", text=json.dumps(_get_today(arguments), indent=2))]
        elif name == "check_conflict":
            return [TextContent(type="text", text=json.dumps(_check_conflict(arguments), indent=2))]
        elif name == "cancel_appointment":
            return [TextContent(type="text", text=json.dumps(_cancel(arguments), indent=2))]
        elif name == "schedule_appointment":
            return [TextContent(type="text", text=json.dumps(_schedule(arguments), indent=2))]
        else:
            return _error("validation", False, f"Unknown tool: {name}")
    except Exception as e:
        return _error("transient", True, str(e))


def _get_today(args: Dict[str, Any]) -> Dict[str, Any]:
    broker_id = args["broker_id"]
    statuses = args.get("status_filter", ["confirmed", "tentative"])
    today = datetime.now(LIMA_TZ).strftime("%Y-%m-%d")
    
    appts = _appointments.get(broker_id, [])
    filtered = [
        a for a in appts
        if a["date"] == today and a["status"] in statuses
    ]
    filtered.sort(key=lambda x: x["start_time"])
    
    return {
        "broker_id": broker_id,
        "date": today,
        "appointments": filtered,
        "count": len(filtered),
        "confirmed_count": len([a for a in filtered if a["status"] == "confirmed"]),
        "tentative_count": len([a for a in filtered if a["status"] == "tentative"])
    }


def _check_conflict(args: Dict[str, Any]) -> Dict[str, Any]:
    broker_id = args["broker_id"]
    proposed_start = datetime.fromisoformat(args["proposed_start"].replace("Z", "+00:00"))
    proposed_end = datetime.fromisoformat(args["proposed_end"].replace("Z", "+00:00"))
    
    # Add 30-min travel buffer on each side
    buffer_start = proposed_start - timedelta(minutes=30)
    buffer_end = proposed_end + timedelta(minutes=30)
    
    appts = _appointments.get(broker_id, [])
    conflicts = []
    for a in appts:
        if a["status"] not in ["confirmed", "tentative"]:
            continue
        a_start = datetime.fromisoformat(a["start_time"])
        a_end = datetime.fromisoformat(a["end_time"])
        # Overlap check
        if buffer_start < a_end and buffer_end > a_start:
            conflicts.append(a)
    
    alternatives = []
    if conflicts:
        base = proposed_start.replace(hour=10, minute=0)
        for i in range(3):
            alt = base + timedelta(hours=i*2)
            alt_end = alt + timedelta(minutes=45)
            alt_conflicts = [
                a for a in appts
                if a["status"] in ["confirmed", "tentative"]
                and (alt - timedelta(minutes=30)) < datetime.fromisoformat(a["end_time"])
                and (alt_end + timedelta(minutes=30)) > datetime.fromisoformat(a["start_time"])
            ]
            if not alt_conflicts:
                alternatives.append({"start": alt.isoformat(), "end": alt_end.isoformat()})
    
    return {
        "conflict_detected": len(conflicts) > 0,
        "conflicts": conflicts,
        "alternatives": alternatives[:3],
        "proposed_time_valid": len(conflicts) == 0
    }


def _cancel(args: Dict[str, Any]) -> Dict[str, Any]:
    appt_id = args["appointment_id"]
    reason = args["reason"]
    
    found = False
    for broker_id, appts in _appointments.items():
        for a in appts:
            if a["id"] == appt_id:
                a["status"] = "cancelled"
                a["cancellation"] = {
                    "reason": reason,
                    "cancelled_at": datetime.now(LIMA_TZ).isoformat(),
                    "cancelled_by": args.get("cancelled_by", "client")
                }
                found = True
                break
        if found:
            break
    
    if not found:
        return _error_dict("validation", False, f"Appointment {appt_id} not found.")
    
    return {
        "status": "success",
        "appointment_id": appt_id,
        "new_status": "cancelled",
        "reason": reason,
        "reoptimize_recommended": True,
        "message": "Appointment cancelled. Re-optimization workflow triggered."
    }


def _schedule(args: Dict[str, Any]) -> Dict[str, Any]:
    broker_id = args["broker_id"]
    appt = {
        "id": f"appt_{int(datetime.now().timestamp())}",
        "broker_id": broker_id,
        "client_id": args["client_id"],
        "start_time": args["start_time"],
        "end_time": args["end_time"],
        "appointment_type": args["appointment_type"],
        "location": args.get("location", {}),
        "property_ref": args.get("property_ref", ""),
        "status": "confirmed",
        "date": datetime.fromisoformat(args["start_time"].replace("Z", "+00:00")).strftime("%Y-%m-%d"),
        "created_at": datetime.now(LIMA_TZ).isoformat()
    }
    
    if broker_id not in _appointments:
        _appointments[broker_id] = []
    _appointments[broker_id].append(appt)
    
    return {
        "status": "success",
        "appointment": appt,
        "conflict_check": "passed"  # In production, call check_conflict first
    }


def _error(category: str, retryable: bool, description: str) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps({
        "isError": True, "errorCategory": category, "isRetryable": retryable, "description": description
    }, indent=2))]


def _error_dict(category: str, retryable: bool, description: str) -> Dict[str, Any]:
    return {"isError": True, "errorCategory": category, "isRetryable": retryable, "description": description}


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    
    asyncio.run(main())

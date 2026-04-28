"""
MCP Server: Peru WhatsApp Business
===================================
Structured WhatsApp Business API integration with time enforcement.
Demonstrates: Tool design, structured errors, programmatic hooks, business rules.
"""

import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("peru_whatsapp")

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_BUSINESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

# Time enforcement: 8am - 8pm Lima
LIMA_TZ = ZoneInfo("America/Lima")


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="send_templated_whatsapp",
            description=(
                "Sends a pre-approved WhatsApp Business template message to a client. "
                "CRITICAL: Messages CANNOT be sent before 8:00 AM or after 8:00 PM Lima time (UTC-5). "
                "Use ONLY for appointment reminders, rescheduling, document requests, property alerts, or thank-yous. "
                "All messages require explicit broker approval before sending. "
                "For informal chat, escalate to human broker — do NOT send freeform messages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Internal client identifier"},
                    "phone_number": {"type": "string", "description": "Full international phone number (e.g., 51999123456)"},
                    "template_name": {
                        "type": "string",
                        "enum": ["appointment_reminder", "appointment_change", "docs_request", "property_available", "thank_you"],
                        "description": "Must be a pre-approved WhatsApp Business template"
                    },
                    "language_code": {"type": "string", "default": "es", "description": "ISO language code. Use 'es' for all client communication."},
                    "variables": {
                        "type": "object",
                        "description": "Template variables: client_name, property_ref, address, time, broker_name, docs_list"
                    }
                },
                "required": ["client_id", "phone_number", "template_name"]
            }
        ),
        Tool(
            name="check_template_status",
            description=(
                "Check whether a WhatsApp Business template is approved and ready to send. "
                "Use before sending messages with newly created templates."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "template_name": {"type": "string"}
                },
                "required": ["template_name"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    try:
        if name == "send_templated_whatsapp":
            return [TextContent(type="text", text=json.dumps(_send_message(arguments), indent=2))]
        elif name == "check_template_status":
            return [TextContent(type="text", text=json.dumps(_check_template(arguments), indent=2))]
        else:
            return _error("validation", False, f"Unknown tool: {name}")
    except Exception as e:
        return _error("transient", True, f"WhatsApp API error: {str(e)}")


def _send_message(args: Dict[str, Any]) -> Dict[str, Any]:
    # HOOK: Time gate enforcement (programmatic, not prompt-based)
    lima_now = datetime.now(LIMA_TZ)
    if lima_now.hour < 8 or lima_now.hour >= 20:
        return {
            "isError": True,
            "errorCategory": "business",
            "isRetryable": False,
            "description": f"Messages cannot be sent outside 8:00 AM - 8:00 PM Lima time. Current time: {lima_now.strftime('%H:%M')}.",
            "next_valid_window": f"{lima_now.strftime('%Y-%m-%d')} 08:00 Lima"
        }
    
    # HOOK: Verify template is approved
    template = args["template_name"]
    approved_templates = ["appointment_reminder", "appointment_change", "docs_request", "property_available", "thank_you"]
    if template not in approved_templates:
        return {
            "isError": True,
            "errorCategory": "validation",
            "isRetryable": False,
            "description": f"Template '{template}' is not in the approved list. Available: {approved_templates}"
        }
    
    # In production, this would call the WhatsApp Business API Graph endpoint
    # POST https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages
    
    return {
        "status": "success",
        "message_id": f"wamid.mock_{args['client_id']}_{int(datetime.now().timestamp())}",
        "template_name": template,
        "recipient": args["phone_number"],
        "sent_at": lima_now.isoformat(),
        "preview": _generate_preview(template, args.get("variables", {})),
        "delivery_status": "sent",
        "hook_checks_passed": ["time_gate", "template_approved"]
    }


def _check_template(args: Dict[str, Any]) -> Dict[str, Any]:
    template = args["template_name"]
    approved = ["appointment_reminder", "appointment_change", "docs_request", "property_available", "thank_you"]
    return {
        "template_name": template,
        "approved": template in approved,
        "status": "APPROVED" if template in approved else "PENDING_REVIEW",
        "language_availability": ["es", "es_PE"]
    }


def _generate_preview(template: str, variables: Dict[str, str]) -> str:
    previews = {
        "appointment_reminder": "Hola {client_name}, le recordamos su cita mañana a las {time} en {address}. Ref: {property_ref}",
        "appointment_change": "Hola {client_name}, su cita ha sido reprogramada para {time} en {address}. Confirme por favor.",
        "docs_request": "Hola {client_name}, para continuar necesitamos: {docs_list}. Gracias.",
        "property_available": "Hola {client_name}, encontramos una propiedad que coincide con su búsqueda: {property_ref} en {address}. ¿Le interesa verla?",
        "thank_you": "Gracias {client_name} por su tiempo hoy. Quedo atento ante cualquier consulta. — {broker_name}"
    }
    base = previews.get(template, "[Template preview not available]")
    for k, v in variables.items():
        base = base.replace(f"{{{k}}}", str(v))
    return base


def _error(category: str, retryable: bool, description: str) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps({
        "isError": True,
        "errorCategory": category,
        "isRetryable": retryable,
        "description": description
    }, indent=2))]


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    
    asyncio.run(main())

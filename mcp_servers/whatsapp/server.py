"""
MCP Server: Peru WhatsApp Business
===================================
Structured WhatsApp Business API integration with time enforcement.
Demonstrates: Tool design, structured errors, programmatic hooks, business rules.

Priority 4 additions:
- Real WhatsApp Business Cloud API calls when WHATSAPP_BUSINESS_TOKEN +
  WHATSAPP_PHONE_NUMBER_ID are present in the environment.
- Graceful degradation: returns mock-like response (is_mock=True) when
  credentials are absent so the system keeps working without Meta account.
- Explicit error handling for 401 auth, 400 bad request, 429 rate limit,
  network timeouts, and connection errors.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import requests as _http
from mcp.server import Server
from mcp.types import TextContent, Tool

app = Server("peru_whatsapp")
logger = logging.getLogger(__name__)

# Read at module load for startup logging; re-read inside functions to support
# runtime env changes (e.g. test patching via patch.dict).
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_BUSINESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
    logger.warning(
        "WHATSAPP_BUSINESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID not set — "
        "send_templated_whatsapp will return mock responses (graceful degradation)"
    )

LIMA_TZ = ZoneInfo("America/Lima")
_APPROVED_TEMPLATES = [
    "appointment_reminder",
    "appointment_change",
    "docs_request",
    "property_available",
    "thank_you",
]


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
                        "enum": _APPROVED_TEMPLATES,
                        "description": "Must be a pre-approved WhatsApp Business template",
                    },
                    "language_code": {"type": "string", "default": "es", "description": "ISO language code. Use 'es' for all client communication."},
                    "variables": {
                        "type": "object",
                        "description": "Template variables: client_name, property_ref, address, time, broker_name, docs_list",
                    },
                },
                "required": ["client_id", "phone_number", "template_name"],
            },
        ),
        Tool(
            name="check_template_status",
            description=(
                "Check whether a WhatsApp Business template is approved and ready to send. "
                "Use before sending messages with newly created templates."
            ),
            inputSchema={
                "type": "object",
                "properties": {"template_name": {"type": "string"}},
                "required": ["template_name"],
            },
        ),
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
            "description": (
                f"Messages cannot be sent outside 8:00 AM - 8:00 PM Lima time. "
                f"Current time: {lima_now.strftime('%H:%M')}."
            ),
            "next_valid_window": f"{lima_now.strftime('%Y-%m-%d')} 08:00 Lima",
        }

    # HOOK: Verify template is approved
    template = args["template_name"]
    if template not in _APPROVED_TEMPLATES:
        return {
            "isError": True,
            "errorCategory": "validation",
            "isRetryable": False,
            "description": f"Template '{template}' is not in the approved list. Available: {_APPROVED_TEMPLATES}",
        }

    phone_number = args["phone_number"]
    language_code = args.get("language_code", "es")
    variables = args.get("variables", {})

    # Re-read credentials at call time to support runtime patching in tests
    token = os.environ.get("WHATSAPP_BUSINESS_TOKEN", "")
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

    if not token or not phone_id:
        logger.warning("WhatsApp credentials absent — returning mock response for client %s", args["client_id"])
        return {
            "status": "success",
            "message_id": f"wamid.mock_{args['client_id']}_{int(datetime.now().timestamp())}",
            "template_name": template,
            "recipient": phone_number,
            "sent_at": lima_now.isoformat(),
            "preview": _generate_preview(template, variables),
            "delivery_status": "mock",
            "hook_checks_passed": ["time_gate", "template_approved"],
            "is_mock": True,
            "warning": "WhatsApp credentials not configured — message was NOT sent",
        }

    # ── Real WhatsApp Business Cloud API call ──────────────────────────────────
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Map variables dict to positional body parameters (order determined by template)
    components: List[Dict] = []
    if variables:
        params = [{"type": "text", "text": str(v)} for v in variables.values()]
        components.append({"type": "body", "parameters": params})

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language_code},
            "components": components,
        },
    }

    try:
        resp = _http.post(url, headers=headers, json=payload, timeout=10)
    except _http.exceptions.Timeout:
        return {"isError": True, "errorCategory": "transient", "isRetryable": True, "description": "WhatsApp API timeout. Retry shortly."}
    except _http.exceptions.ConnectionError:
        return {"isError": True, "errorCategory": "transient", "isRetryable": True, "description": "Network error connecting to WhatsApp API."}

    if resp.status_code == 401:
        return {"isError": True, "errorCategory": "auth", "isRetryable": False, "description": "WhatsApp API authentication failed. Verify WHATSAPP_BUSINESS_TOKEN."}
    if resp.status_code == 400:
        err_msg = resp.json().get("error", {}).get("message", resp.text)
        return {"isError": True, "errorCategory": "validation", "isRetryable": False, "description": f"WhatsApp rejected request: {err_msg}"}
    if resp.status_code == 429:
        return {"isError": True, "errorCategory": "transient", "isRetryable": True, "description": "WhatsApp API rate limit exceeded. Retry in a few seconds."}

    try:
        resp.raise_for_status()
    except _http.exceptions.HTTPError as e:
        return {"isError": True, "errorCategory": "transient", "isRetryable": True, "description": f"WhatsApp API HTTP {resp.status_code} error."}

    data = resp.json()
    message_id = data.get("messages", [{}])[0].get("id", "wamid.unknown")

    return {
        "status": "success",
        "message_id": message_id,
        "template_name": template,
        "recipient": phone_number,
        "sent_at": lima_now.isoformat(),
        "preview": _generate_preview(template, variables),
        "delivery_status": "sent",
        "hook_checks_passed": ["time_gate", "template_approved"],
    }


def _check_template(args: Dict[str, Any]) -> Dict[str, Any]:
    template = args["template_name"]
    approved = template in _APPROVED_TEMPLATES
    return {
        "template_name": template,
        "approved": approved,
        "status": "APPROVED" if approved else "PENDING_REVIEW",
        "language_availability": ["es", "es_PE"],
    }


def _generate_preview(template: str, variables: Dict[str, str]) -> str:
    previews = {
        "appointment_reminder": "Hola {client_name}, le recordamos su cita mañana a las {time} en {address}. Ref: {property_ref}",
        "appointment_change": "Hola {client_name}, su cita ha sido reprogramada para {time} en {address}. Confirme por favor.",
        "docs_request": "Hola {client_name}, para continuar necesitamos: {docs_list}. Gracias.",
        "property_available": "Hola {client_name}, encontramos una propiedad que coincide con su búsqueda: {property_ref} en {address}. ¿Le interesa verla?",
        "thank_you": "Gracias {client_name} por su tiempo hoy. Quedo atento ante cualquier consulta. — {broker_name}",
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
        "description": description,
    }, indent=2))]


if __name__ == "__main__":
    import asyncio

    from mcp.server.stdio import stdio_server

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(main())

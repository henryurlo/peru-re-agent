---
paths: ["agents/messaging*", "mcp_servers/whatsapp*"]
---

# Messaging Agent Conventions

## WhatsApp Business API Rules

- **Language:** Always use `es` (Spanish) for client messages. Broker confirmation messages can be `en` or `es-PE`.
- **Templates only:** Never send freeform messages. All messages MUST use pre-approved WhatsApp Business templates.
- **Allowed template types:**
  - `appointment_reminder` — 24h before showing
  - `appointment_change` — Rescheduling
  - `docs_request` — Document checklist followup
  - `property_available` — New matching property alert
  - `thank_you` — Post-showing thank you

## Time Enforcement (CRITICAL)

**Messages MUST NOT be sent outside 8:00 AM - 8:00 PM Lima time (UTC-5).**

Hook enforcement: `PostToolUse` on `send_templated_whatsapp` must:
1. Extract current Lima time from `datetime.now(ZoneInfo("America/Lima"))`
2. If hour < 8 or hour >= 20 → BLOCK and return scheduling_error
3. If blocked → suggest scheduling for next valid window

## Approval Gate

**All outbound messages require explicit broker approval.**

The messaging agent must:
1. Draft message content
2. Present to broker: "Draft message to [Client] using [Template]: [Preview]"
3. Only call `send_templated_whatsapp` after broker confirms with "yes" / "enviar" / "ok"

## Escalation Triggers

- Client replies with "hablar con humano" / "quiero hablar con alguien" → immediately escalate
- Client asks policy question beyond approved templates → escalate with transcribed message
- Client sends abusive content → flag and escalate without response

## Localization

- Formal "usted" form for all client communication
- Always reference district name, not just address
- Include property reference code when applicable

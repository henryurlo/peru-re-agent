---
name: handle-cancellation
description: Handle appointment cancellation dynamically. Re-routes the broker's day, finds nearby qualified leads, and drafts alternative appointments with WhatsApp messages.
context: fork
allowed-tools: [Read, Write, Bash, Grep, Glob]
argument-hint: "--client 'Client Name' --reason no_show|client_request|broker_request|force_majeure"
---

# Handle Cancellation

## Goal
Transform a cancelled appointment into an optimized re-routing with alternative opportunities.

## Execution Steps

1. **Capture Cancellation Data**:
   - Call `calendar.cancel_appointment(client_id, reason)`
   - Store cancellation in `appointment_history` for pattern analysis

2. **Fetch Broker State** (Coordinator context):
   - Current GPS location (from last known or ask broker)
   - Remaining confirmed appointments today
   - Current time in Lima (`America/Lima`)

3. **Parallel Subagent Execution** (spawn both simultaneously):

   **Subagent A: Re-routing**
   - Task routing agent with remaining appointments + new origin
   - Request `alternatives=true` for route flexibility
   - If new gap > 60 minutes, return flag: `opportunity_window`

   **Subagent B: Opportunity Discovery**
   - Query `property_db` for qualified leads within 15km of broker's current location
   - Filter: `status='qualified'`, `financing_score >= 60`, `willing_to_meet_today=true`
   - Sort by: proximity, then match_score, then last_contact_date
   - Return top 5 with full profiles and preferred contact methods

4. **Draft Communications** (Messaging Agent subtask):
   - For each discovered lead, draft personalized WhatsApp using `property_available` or `appointment_change` template
   - Include broker's availability window from re-routing results
   - Enforce time gate: no messages after 7:30 PM Lima time

5. **Broker Approval Gate**:
   - Present broker with:
     a. Re-optimized route map
     b. List of discovered leads with match scores
     c. WhatsApp draft previews
   - Require explicit "yes" / "enviar" / "ok" before any tool calls to `send_templated_whatsapp`

6. **If No Alternatives Found**:
   - Suggest admin tasks: update CRM notes, follow up on pending docs, prospect new listings
   - Propose early wrap if broker prefers

## Error Handling

- If `property_db` query returns empty → return `errorCategory: "business"`, suggest broadening radius or changing districts
- If routing fails → return cached typical-traffic estimates, ask broker to proceed manually
- If all WhatsApp templates are exhausted/unapproved → escalate to human for manual client contact

## Output Format

```json
{
  "status": "success" | "partial" | "error",
  "cancelled_appointment": {"client_id": "...", "reason": "..."},
  "new_route": {"legs": [...], "total_duration": 120},
  "opportunities": [{"client_id": "...", "match_score": 82, "distance_km": 4.2}],
  "draft_messages": [{"client_id": "...", "preview": "..."}],
  "awaiting_approval": true,
  "coverage_gaps": ["transit mode unavailable for this district pair"]
}
```

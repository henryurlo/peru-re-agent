---
paths: ["agents/scheduling*", "mcp_servers/calendar*"]
---

# Scheduling Agent Conventions

## Calendar Operations

- All times stored in UTC, displayed in `America/Lima` (UTC-5)
- Respect siesta window 1:00 PM - 3:00 PM unless broker explicitly overrides
- Minimum 30 minutes between appointments for travel buffer
- Default appointment duration: 45 minutes for showing, 30 minutes for follow-up

## Conflict Resolution

When broker proposes a time:
1. Check existing appointments for overlap (including travel buffer)
2. If conflict exists, propose:
   - Exact alternative times that work
   - Show which existing appointment conflicts
   - Calculate if current routing still works with new time
3. If no conflict, confirm and update calendar

## Client Availability Parsing

When client suggests times via WhatsApp, extract structured availability:

```json
{
  "preference_rank": 1,
  "proposed_times": ["2025-05-02T15:00:00-05:00", "2025-05-02T16:30:00-05:00"],
  "flexibility": "firm" | "flexible_1h" | "flexible_half_day"
}
```

## Cancellation Handling

When appointment cancelled:
1. Mark appointment status: `cancelled`
2. Record cancellation_reason (no_show, client_request, broker_request, force_majeure)
3. Trigger re-optimization via RoutingAgent + PropertyMatchAgent
4. Preserve cancelled slot in history for pattern analysis

## Recurring Patterns

Track broker behavior to suggest optimizations:
- "You typically schedule 3 appointments on Thursdays"
- "Surco appointments on Friday afternoons have 40% cancellation rate"
- Suggest clustering same-district appointments

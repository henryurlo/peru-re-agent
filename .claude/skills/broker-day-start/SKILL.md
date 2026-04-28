---
name: broker-day-start
description: Start the broker's day with route optimization and appointment preparation. Fetches today's schedule, optimizes the route, checks document readiness, and proposes a prioritized daily plan.
context: fork
allowed-tools: [Read, Write, Bash, Grep, Glob]
argument-hint: "--date YYYY-MM-DD (defaults to today)"
---

# Broker Day Start

## Goal
Prepare the broker's daily operating plan through coordinated subagent execution.

## Execution Steps

1. **Invoke the Coordinator Agent** to orchestrate the morning routine.

2. **Fetch Appointments** (Scheduling Agent subtask):
   - Query calendar for today's appointments where `status = 'confirmed'`
   - Return structured list with client_id, address, time_window, appointment_type

3. **Optimize Route** (Routing Agent subtask):
   - If broker's current GPS available, use it as origin
   - Otherwise, ask broker for starting location
   - Run multi-stop route optimization for confirmed appointments
   - Request `driving` mode primarily; include `transit` alternative if appointments in transit-rich districts

4. **Check Document Readiness** (Property Match Agent subtask):
   - For each showing appointment, lookup client record
   - Check `documents_status` for required items: DNI, pay_stubs, tax_returns, pre_approval
   - If any missing, flag and prepare `docs_request` template draft

5. **Identify Unscheduled Opportunities** (Property Match Agent subtask):
   - Query `clients` table for `status = 'qualified'` and `last_contact > 3 days`
   - Filter by broker's route districts for today
   - Return top 3 opportunities with match scores

6. **Synthesize** into a morning briefing:
   - Optimized route with ETA map link
   - Document alerts (who needs followup)
   - Priority new leads to contact
   - Risk flags (weather, traffic alerts)

## Output Format

Deliver to broker as structured markdown:
- 🗺️ Route summary (time-ordered stops)
- ⏰ Departure recommendation (with traffic buffer)
- 📋 Document readiness dashboard
- 🎯 Suggested outreach (today's opportunistic leads)
- ⚠️ Risk flags

All WhatsApp drafts require broker approval. Do not send automatically.

---
name: qualify-lead
description: Qualify a new real estate lead through structured data extraction, financing readiness scoring, and property matching. Stores lead in PostgreSQL and drafts onboarding WhatsApp.
context: fork
allowed-tools: [Read, Write, Bash, Grep, Glob]
argument-hint: "--source facebook|referral|whatsapp|organic"
---

# Qualify Lead

## Goal
Transform an unstructured inquiry into a scored, matched, and prioritized lead.

## Execution Steps

1. **Extract Structured Profile**:
   - Source channel: Facebook ad, WhatsApp referral, organic landing page, etc.
   - Extract fields:
     - `name`, `phone`, `email`
     - `budget_usd` (normalize PEN if given)
     - `preferred_districts` (list)
     - `property_type` (apartment|house|office|land)
     - `financing_status` (cash|pre_approved|pending|unknown)
   - If any critical field missing, ask broker for clarification before proceeding

2. **Financing Readiness Scoring** (0-100):
   - Has DNI: +10
   - Has 3 months pay stubs / bank statements: +15
   - Has SUNAT tax returns: +10
   - Pre-approved by bank (BCP, Interbank, Scotiabank, BBVA): +30
   - Total monthly income > 4x estimated mortgage payment: +15
   - **Disqualify if:** Budget stated is >80% below typical prices in preferred districts
   - **Fast-track if:** Score >= 70 AND property_type matches available inventory

3. **Property Matching** (Property Match Agent subtask):
   - Query `properties` table:
     - `status = 'available'`
     - `district IN preferred_districts`
     - `price_usd BETWEEN budget * 0.8 AND budget * 1.2`
   - Calculate match_score per property
   - Return top 5 with reasoning

4. **Store in Database**:
   - Insert into `clients` table with `status = 'qualified'` or `'needs_docs'`
   - Insert into `matches` table for top 5 properties
   - Log lead source for attribution tracking

5. **Draft Onboarding WhatsApp**:
   - Use `docs_request` template if `financing_score` suggests missing docs
   - Use `appointment_reminder` template if fast-track eligible
   - Include personalized property reference codes (e.g., "MIR-2847")
   - **Broker approval required before send**

6. **Synthesize Broker Briefing**:
   - Lead profile summary with score
   - Top 3 matching properties
   - Recommended next action (call now, send docs checklist, schedule showing)
   - Priority: `immediate`, `this_week`, `nurture`

## Few-Shot Examples (for extraction)

**Example 1 — Facebook Lead:**
Input: "Hola, me interesa un departamento en Miraflores, mi presupuesto es 180 mil dólares. Tengo mi DNI y 3 boletas de pago. Trabajo como ingeniero."
Output:
```json
{
  "name": "Desconocido",
  "phone": "Desconocido",
  "budget_usd": 180000,
  "preferred_districts": ["Miraflores"],
  "property_type": "apartment",
  "financing_status": "pending",
  "has_dni": true,
  "has_pay_stubs": true,
  "score": 65
}
```

**Example 2 — Referral:**
Input: "My friend Carlos said you're the best. I'm looking for a house in La Molina, budget $350k. I have cash."
Output:
```json
{
  "name": "Carlos's friend",
  "phone": "Desconocido",
  "budget_usd": 350000,
  "preferred_districts": ["La Molina"],
  "property_type": "house",
  "financing_status": "cash",
  "score": 85
}
```

## Error Handling

- If budget cannot be parsed → Return `errorCategory: "validation"`, ask broker to confirm
- If preferred district not in database → Suggest closest available district
- If no matching properties → Add to `waitlist` with `notify_when_available` flag

## Output Schema

See `schemas/lead_qualification.json` for full Pydantic model.

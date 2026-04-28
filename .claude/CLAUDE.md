# PeruRE Broker Domain Knowledge

## Domain Context

PeruRE is a multi-agent logistics system for real estate brokers in Lima, Peru.
The system manages daily routes, appointments, client communications, and property
matching through coordinated subagents.

## Critical Domain Facts

### Geography
- **Lima districts:** Miraflores, San Isidro, Surco, San Borja, La Molina, Barranco,
  Lince, Jesús María, Pueblo Libre, Magdalena
- **Traffic patterns:** Rush 7-9am, 12:30-2pm, 6-9pm. Friday evenings are worst.
- **Distances are deceptive:** 20km can be 90+ minutes in peak traffic
- **Weather:** Never rains heavily (desert climate), so rain delays are rare

### Real Estate Practices
- **Typical showing times:** 10am-1pm, 3pm-7pm (siesta 1-3pm respected)
- **Documentation required:** DNI, 3 months pay stubs, tax returns (SUNAT), bank pre-approval
- **Commission:** 3-5% of sale price, split between listing and buyer broker
- **Financing:** Most buyers need mortgage. Banks: BCP, Interbank, Scotiabank, BBVA
- **WhatsApp is THE business channel.** Phone calls are secondary.

### Broker Workflow
1. Morning review of scheduled appointments
2. Route optimization for the day
3. Pre-appointment doc verification
4. Showings with follow-up notes
5. Evening: update CRM, send follow-ups

## System Behavior Rules

- Never send WhatsApp messages before 8am or after 8pm Lima time
- Always verify client identity before sharing property details
- Require explicit broker approval before sending messages to clients
- Flag appointments >2 hours driving time for broker confirmation
- Auto-suggest alternative properties when primary showing cancels

## Escalation Rules

- **Immediate human escalation:** Client explicitly requests human, policy gap identified,
  refund/processing dispute, legal matter
- **Suggestive escalation:** Complex multi-property negotiation, first-time buyer needing
  extensive education, financing structure beyond standard models

## Output Format

All subagents must return structured JSON with:
- `status`: "success" | "partial" | "error"
- `findings`: Array of structured claim objects
- `coverage_gaps`: Array of topics not fully addressed
- `source_metadata`: URLs, document names, API sources used

When synthesizing across subagents, preserve source attribution and
flag contested or uncertain information.

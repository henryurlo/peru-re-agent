---
paths: ["agents/property_match*", "mcp_servers/property_db*"]
---

# Property Matching Agent Conventions

## Database Schema Conventions

The `property_db` MCP server manages these tables:
- `properties` — listings with district, price, sqm, bedrooms, status
- `clients` — buyer profiles with budget, preferred_districts, financing_status
- `matches` — broker-generated property-client pairings with notes

## Query Patterns

Always use parameterized queries. Never construct SQL from natural language.

**Availability filter:** Only return properties where `status = 'available'` unless broker asks for history.

## Matching Logic

Score properties for a client using:
- Budget fit: ±15% of stated budget = 100 points, ±30% = 50 points
- District preference: exact match = 50 points, adjacent district = 25 points
- Size fit: within ±10% of requested sqm = 30 points
- Financing ready: if client has pre-approval, flag "fast_close"

Return top 5 matches with score and reasoning.

## Structured Output

```json
{
  "matches": [
    {
      "property_id": "PROP-2847",
      "address": "Jr. Las Lomas 432, Miraflores",
      "price_usd": 185000,
      "sqm": 85,
      "bedrooms": 2,
      "match_score": 87,
      "match_reasons": ["within_budget", "preferred_district", "size_fit"],
      "fast_close_eligible": true,
      "broker_notes": "Client viewed similar property last month — follow up"
    }
  ],
  "alternative_districts": ["San Isidro", "Surco"]
}
```

## Ethics & Compliance

- Never share client financial details with property owners
- Flag dual-representation conflicts (broker representing both buyer and seller)
- Respect `do_not_contact` flags on client records

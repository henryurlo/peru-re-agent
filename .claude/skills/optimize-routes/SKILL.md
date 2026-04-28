---
name: optimize-routes
description: Run route optimization across multiple transport modes (driving, taxi, transit) for a broker's confirmed appointments. Returns comparative route options with Mapbox visualization links.
context: fork
allowed-tools: [Read, Write, Bash, Grep, Glob]
argument-hint: "--mode driving|all"
---

# Optimize Routes

## Goal
Find the most efficient travel plan across a broker's appointment schedule,
evaluating multiple transport modes and real-time conditions.

## Execution Steps

1. **Fetch Current Schedule**:
   - Query `calendar` for confirmed appointments within time window
   - Include: origin, destinations (lat/lng), time_windows, appointment_types

2. **Multi-Mode Route Calculation** (parallel where API permits):

   **Driving Mode** (always):
   - Mapbox Directions API `mapbox/driving` with `annotations=duration,distance`
   - Include traffic if token has traffic scope

   **Taxi Mode** (estimate):
   - Same route as driving
   - Fare heuristic: S/5 base + S/3.5/km + S/0.8/min
   - Note: This is approximate. Actual Uber/Taxi fare varies.

   **Transit Mode** (if available):
   - Mapbox Directions `mapbox/walking` segments + Lima transit stops overlay
   - For Lima: Metropolitano BRT + Metro Line 1 coverage
   - If Google Maps Directions key available, use `transit` mode for accurate bus/metro routing

3. **Comparative Evaluation**:

   | Mode | Time | Cost | Comfort | Best For |
   |------|------|------|---------|----------|
   | Own Car | Fastest | Fuel only | High | Multiple far appointments |
   | Taxi | Medium | Medium | High | Parking-limited districts (Miraflores) |
   | Transit | Variable | Low | Medium | Single-district cluster with BRT access |

4. **Optimization Criteria**:
   - Minimize total travel time
   - Maximize appointment value (prioritize high-commission showings)
   - Respect time windows (hard constraint)
   - Include 15-min buffer between appointments
   - Avoid >2 hours total driving (flag for broker confirmation)

5. **Visualization**:
   - Generate Mapbox Static Image API URL for route preview
   - Include GeoJSON LineString for each leg
   - Provide shareable link broker can open on phone

## Mapbox Integration

**Mapbox Directions API** — free tier includes 100,000 requests/month.
For Lima real estate: a busy broker might optimize 3x/day × 20 days = 60 requests/month.
Well within free tier.

**Required token scope:** `directions:read`

## Output Schema

```json
{
  "status": "success",
  "recommended_mode": "driving",
  "route": {
    "origin": {"lat": -12.12, "lng": -77.03, "name": "Broker Home"},
    "stops": [
      {"name": "Maria G.", "address": "...", "time": "10:00", "mode": "driving", "eta": "09:42"},
      {"name": "Carlos R.", "address": "...", "time": "11:30", "mode": "driving", "eta": "11:15"}
    ],
    "total_duration_minutes": 145,
    "total_distance_km": 28.4,
    "mapbox_url": "https://api.mapbox.com/styles/v1/..."
  },
  "alternatives": [
    {"mode": "taxi", "total_cost_sol": 145.0, "duration_minutes": 155},
    {"mode": "transit", "total_cost_sol": 18.0, "duration_minutes": 210}
  ],
  "risk_flags": ["traffic_heavy_morning"],
  "coverage_gaps": ["realtime_transit_delays_not_available"]
}
```

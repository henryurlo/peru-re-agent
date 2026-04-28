---
paths: ["agents/routing*", "mcp_servers/maps*"]
---

# Routing Agent Conventions

## Mapbox API Usage

- Always request `geometries=geojson` and `overview=full` for complete route visualization
- Use `annotations=duration,distance,speed` for per-segment analysis
- Set `approaches=unrestricted` to allow u-turns (common in Lima's grid system)
- Include `alternatives=true` to provide 2-3 route options when available

## Multi-Modal Routing Logic

When broker requests route comparison:

1. **Driving** — `mapbox/driving` profile with `annotations`
2. **Taxi/Uber** — Same route as driving, add fare estimate heuristic: base S/5 + S/3.5 per km + S/0.8 per min
3. **Public Transit** — `mapbox/walking` to nearest transit stop + transit API if available, otherwise walking segments with bus/metro annotations

## Output Schema

The routing agent MUST return a `RoutePlan` JSON matching this structure:

```json
{
  "mode": "driving" | "taxi" | "transit",
  "total_duration_minutes": 42,
  "total_distance_km": 8.5,
  "legs": [
    {
      "from": {"name": "Current Location", "lat": -12.12, "lng": -77.03},
      "to": {"name": "Client: Maria G.", "lat": -12.10, "lng": -77.01},
      "duration_minutes": 22,
      "distance_km": 5.2,
      "traffic_condition": "moderate" | "heavy" | "light",
      "geometry": { "type": "LineString", "coordinates": [...] }
    }
  ],
  "risk_flags": ["traffic_heavy", "late_evening", "unconfirmed_client"],
  "fare_estimate_sol": 28.50
}
```

## Error Handling

- **Mapbox timeout** → Return `errorCategory: "transient"`, include partial cached route
- **No route found** → Return `errorCategory: "validation"`, suggest alternative district or mode
- **Invalid coordinates** → Return `errorCategory: "validation"`, ask broker to verify location

## Lima-Specific Rules

- Avoid routing through Av. Javier Prado during 12:30-2pm (lunch rush)
- Prefer Panamericana Sur/Norte for inter-district travel outside rush
- Consider one-way street reversals: many streets change direction 7-9pm

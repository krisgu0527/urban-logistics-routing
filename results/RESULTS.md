# Measured results

Actual code run: 40 synthetic customers, demand 504 units, capacity 100 units/vehicle, fleet limit 6, search budget 10 seconds.

| Metric | Baseline | OR-Tools |
|---|---:|---:|
| Customers served | 40 | 40 |
| Vehicles used | 6 | 6 |
| Total distance (km) | 198.064 | 152.433 |
| Average route length (km) | 33.011 | 25.405 |
| Longest route (km) | 46.295 | 32.392 |
| Capacity utilization (%) | 84.00 | 84.00 |

Distance reduction: **23.04%** (45.631 km). A feasible heuristic solution; global optimality is not established.

Source: `summary.csv`, `route_details.csv`, and `run_metadata.json`.

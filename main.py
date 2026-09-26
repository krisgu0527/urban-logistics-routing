"""Run the complete synthetic routing experiment: python main.py."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import time

import pandas as pd

from data import distance_matrix, generate_dataset, validate_dataset
from plotting import plot_comparison, plot_routes
from routing import nearest_neighbor, route_metrics, solve_cvrp, validate_routes

ROOT = Path(__file__).resolve().parent


def update_result_block(path, block):
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    start, end = "<!-- RESULTS_START -->", "<!-- RESULTS_END -->"
    if start not in text or end not in text:
        raise ValueError(f"Missing results markers in {path.name}")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    path.write_text(before + start + "\n" + block + "\n" + end + after, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--capacity", type=int, default=100, help="Standardized demand units per vehicle")
    parser.add_argument("--vehicles", type=int, default=None,
                        help="Available vehicles; defaults to the baseline's feasible fleet size")
    parser.add_argument("--seconds", type=int, default=10, help="OR-Tools search time budget")
    parser.add_argument("--input", type=Path, help="Optional CSV using the documented synthetic schema")
    parser.add_argument("--output", type=Path, help="Separate experiment folder; preserves bundled results/docs")
    args = parser.parse_args()
    if args.seed < 0 or args.seconds < 1 or (args.vehicles is not None and not 1 <= args.vehicles <= 200):
        parser.error("seed must be nonnegative, seconds positive, vehicles in 1..200")

    try:
        df = pd.read_csv(args.input) if args.input else generate_dataset(args.customers, args.seed)
        validate_dataset(df, args.capacity)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    distances = distance_matrix(df)
    demands = df.demand_units.to_numpy(dtype=int)
    start = time.perf_counter()
    baseline = nearest_neighbor(distances, demands, args.capacity)
    baseline_seconds = time.perf_counter() - start
    vehicles = len(baseline) if args.vehicles is None else args.vehicles
    if len(baseline) > vehicles:
        parser.error(f"Baseline needs {len(baseline)} vehicles, exceeding fleet {vehicles}. "
                     "This does not prove the CVRP is infeasible; this comparison requires a feasible baseline.")
    validate_routes(baseline, demands, args.capacity, vehicles)
    start = time.perf_counter()
    optimized, status = solve_cvrp(distances, demands, args.capacity, vehicles, baseline, args.seconds)
    optimized_seconds = time.perf_counter() - start

    output = args.output.resolve() if args.output else ROOT / "results"
    output.mkdir(parents=True, exist_ok=True)
    data_dir = output / "data" if args.output else ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = data_dir / "synthetic_customers.csv"
    # Preserve custom coordinate precision so exported inputs reproduce the distance matrix.
    df.to_csv(dataset_path, index=False)
    tables, summaries = [], []
    for method, routes, runtime in [("Baseline", baseline, baseline_seconds),
                                     ("OR-Tools", optimized, optimized_seconds)]:
        table = route_metrics(routes, distances, demands, args.capacity, method)
        tables.append(table)
        summaries.append({
            "method": method, "customers_served": int(table.customers_served.sum()),
            "vehicles_available": vehicles, "vehicles_used": len(routes),
            "total_distance_km": float(table.distance_km.sum()),
            "average_route_km": float(table.distance_km.mean()),
            "longest_route_km": float(table.distance_km.max()),
            "total_demand_units": int(demands.sum()),
            "capacity_utilization_pct": float(demands.sum() / (len(routes) * args.capacity) * 100),
            "routing_runtime_seconds": runtime,
        })
    summary = pd.DataFrame(summaries)
    base_distance, opt_distance = summary.total_distance_km
    reduction = (base_distance - opt_distance) / base_distance * 100 if base_distance else 0.0
    summary.to_csv(output / "summary.csv", index=False)
    pd.concat(tables, ignore_index=True).to_csv(output / "route_details.csv", index=False)
    (output / "routes.json").write_text(json.dumps({"baseline": baseline, "optimized": optimized}, indent=2), encoding="utf-8")
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_type": "synthetic", "customers": len(df) - 1,
        "seed": args.seed if not args.input else None,
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "coordinate_model": "20 x 20 km square, depot at (10,10); custom input may differ",
        "distance_model": "Euclidean km, rounded per edge to integer meters",
        "capacity_units": args.capacity, "vehicles_available": vehicles,
        "fleet_rule": "baseline route count" if args.vehicles is None else "user-specified upper bound",
        "demand_based_vehicle_lower_bound": math.ceil(int(demands.sum()) / args.capacity),
        "search_seconds": args.seconds, "initial_solution": "capacity-aware nearest-neighbor baseline",
        "search_method": "GUIDED_LOCAL_SEARCH", "solver_status_code": status,
        "distance_reduction_pct": reduction, "global_optimality_proven": False,
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {name: version(name) for name in ["numpy", "pandas", "matplotlib", "ortools"]},
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    plot_routes(df, baseline, tables[0], "Baseline | capacity-aware nearest neighbor", output / "baseline_routes.png")
    plot_routes(df, optimized, tables[1], "Optimized | OR-Tools guided local search", output / "optimized_routes.png")
    plot_comparison(summary, output / "performance_comparison.png")

    rows = ["| Metric | Baseline | OR-Tools |", "|---|---:|---:|"]
    for label, key, digits in [("Customers served", "customers_served", 0),
                                ("Vehicles used", "vehicles_used", 0),
                                ("Total distance (km)", "total_distance_km", 3),
                                ("Average route length (km)", "average_route_km", 3),
                                ("Longest route (km)", "longest_route_km", 3),
                                ("Capacity utilization (%)", "capacity_utilization_pct", 2)]:
        rows.append(f"| {label} | {summary.iloc[0][key]:.{digits}f} | {summary.iloc[1][key]:.{digits}f} |")
    block = (f"Actual code run: {len(df)-1} synthetic customers, demand {demands.sum()} units, "
             f"capacity {args.capacity} units/vehicle, fleet limit {vehicles}, "
             f"search budget {args.seconds} seconds.\n\n" + "\n".join(rows) +
             f"\n\nDistance reduction: **{reduction:.2f}%** ({base_distance-opt_distance:.3f} km). "
             "A feasible heuristic solution; global optimality is not established.\n\n"
             "Source: `results/summary.csv`, `results/route_details.csv`, and `results/run_metadata.json`.")
    (output / "RESULTS.md").write_text("# Measured results\n\n" + block.replace("`results/", "`") + "\n", encoding="utf-8")
    if not args.output:
        for name in ["README.md", "PROJECT_EXPLANATION.md"]:
            update_result_block(ROOT / name, block)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"Distance reduction: {reduction:.2f}% | output: {output}")


if __name__ == "__main__":
    main()

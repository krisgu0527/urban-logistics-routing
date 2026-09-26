"""Capacity-aware nearest-neighbor baseline and a distance-minimizing CVRP."""
import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def nearest_neighbor(distances, demands, capacity):
    remaining = set(range(1, len(demands)))
    routes = []
    while remaining:
        route, load = [0], 0
        while True:
            feasible = [n for n in remaining if load + demands[n] <= capacity]
            if not feasible:
                break
            # Stable tie-break makes the baseline reproducible.
            node = min(feasible, key=lambda n: (distances[route[-1], n], n))
            route.append(node)
            load += int(demands[node])
            remaining.remove(node)
        if len(route) == 1:
            raise ValueError("A customer cannot fit into an empty vehicle")
        routes.append(route + [0])
    return routes


def validate_routes(routes, demands, capacity, vehicles):
    if not routes or len(routes) > vehicles:
        raise ValueError("Invalid number of used vehicles")
    visited = []
    for route in routes:
        if len(route) < 3 or route[0] != 0 or route[-1] != 0:
            raise ValueError("Each used route must start/end at the depot and serve customers")
        if any(not isinstance(n, (int, np.integer)) or not 1 <= n < len(demands)
               for n in route[1:-1]):
            raise ValueError("Invalid customer ID or intermediate depot")
        if sum(int(demands[n]) for n in route[1:-1]) > capacity:
            raise ValueError("Vehicle capacity exceeded")
        visited.extend(route[1:-1])
    if sorted(visited) != list(range(1, len(demands))):
        raise ValueError("Every customer must be visited exactly once")


def route_distance_m(route, distances):
    return sum(int(distances[a, b]) for a, b in zip(route, route[1:]))


def solve_cvrp(distances, demands, capacity, vehicles, initial_routes, seconds=10):
    if seconds <= 0:
        raise ValueError("Search time must be positive")
    validate_routes(initial_routes, demands, capacity, vehicles)
    manager = pywrapcp.RoutingIndexManager(len(demands), vehicles, 0)
    model = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return int(distances[manager.IndexToNode(from_index), manager.IndexToNode(to_index)])

    distance_index = model.RegisterTransitCallback(distance_callback)
    model.SetArcCostEvaluatorOfAllVehicles(distance_index)

    def demand_callback(index):
        return int(demands[manager.IndexToNode(index)])

    demand_index = model.RegisterUnaryTransitCallback(demand_callback)
    model.AddDimensionWithVehicleCapacity(demand_index, 0, [capacity] * vehicles, True, "Capacity")
    # No disjunctions: dropping customers is not permitted. Each vehicle makes at most one trip.
    parameters = pywrapcp.DefaultRoutingSearchParameters()
    parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parameters.time_limit.FromSeconds(seconds)
    model.CloseModelWithParameters(parameters)
    seed_routes = [r[1:-1] for r in initial_routes] + [[] for _ in range(vehicles - len(initial_routes))]
    initial = model.ReadAssignmentFromRoutes(seed_routes, True)
    if initial is None:
        raise RuntimeError("OR-Tools rejected the feasible baseline seed")
    solution = model.SolveFromAssignmentWithParameters(initial, parameters)
    if solution is None:
        raise RuntimeError(f"No solver solution returned (status={model.status()})")
    routes = []
    for vehicle in range(vehicles):
        index, route = model.Start(vehicle), [0]
        while not model.IsEnd(index):
            index = solution.Value(model.NextVar(index))
            route.append(manager.IndexToNode(index))
        if len(route) > 2:
            routes.append(route)
    validate_routes(routes, demands, capacity, vehicles)
    objective = int(solution.ObjectiveValue())
    if objective != sum(route_distance_m(r, distances) for r in routes):
        raise RuntimeError("Solver objective disagrees with independent distance calculation")
    if objective > sum(route_distance_m(r, distances) for r in initial_routes):
        raise RuntimeError("Solver returned a solution worse than its baseline seed")
    return routes, int(model.status())


def route_metrics(routes, distances, demands, capacity, method):
    return pd.DataFrame([{
        "method": method, "vehicle_id": i,
        "route": " -> ".join(map(str, route)), "customers_served": len(route) - 2,
        "load_units": sum(int(demands[n]) for n in route[1:-1]),
        "capacity_units": capacity,
        "distance_km": route_distance_m(route, distances) / 1000,
    } for i, route in enumerate(routes, 1)])

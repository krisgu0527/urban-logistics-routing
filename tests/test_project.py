"""Small, independent correctness checks; run python -m unittest discover -s tests -v."""
import itertools
import unittest

import numpy as np

from data import distance_matrix, generate_dataset, validate_dataset
from routing import nearest_neighbor, route_distance_m, route_metrics, solve_cvrp, validate_routes


class RoutingChecks(unittest.TestCase):
    def test_generation_and_invalid_inputs(self):
        df = generate_dataset()
        self.assertTrue(df.equals(generate_dataset()))
        self.assertEqual(len(df), 41)
        self.assertTrue(df.data_source.eq("synthetic").all())
        validate_dataset(df, 100)
        for column, value in [("demand_units", 101), ("demand_units", -1),
                              ("demand_units", 2.5), ("x_km", float("nan")),
                              ("node_id", 0), ("node_type", "depot")]:
            broken = df.copy()
            if column in ["demand_units", "x_km"]:
                broken[column] = broken[column].astype(float)
            broken.loc[1, column] = value
            with self.assertRaises(ValueError):
                validate_dataset(broken, 100)
        with self.assertRaises(ValueError):
            validate_dataset(df, 0)

    def test_distance_units_and_return_to_depot(self):
        df = generate_dataset(1)
        df.loc[:, "x_km"] = [0., 3.]
        df.loc[:, "y_km"] = [0., 4.]
        matrix = distance_matrix(df)
        self.assertEqual(matrix.tolist(), [[0, 5000], [5000, 0]])
        self.assertEqual(route_distance_m([0, 1, 0], matrix), 10000)
        table = route_metrics([[0, 1, 0]], matrix, [0, 7], 10, "test")
        self.assertEqual(table.iloc[0].distance_km, 10)
        self.assertEqual(table.iloc[0].load_units, 7)

    def test_route_rejections(self):
        for routes in [[[0, 1, 0]], [[0, 1, 2, 0]], [[0, 1, 0], [0, 1, 0]],
                       [[1, 0], [0, 2, 0]], [[0, 1, 0, 2, 0]]]:
            with self.assertRaises(ValueError):
                validate_routes(routes, [0, 6, 6], 10, 2)
        validate_routes([[0, 1, 0], [0, 2, 0]], [0, 6, 6], 10, 2)

    def test_tiny_solution_against_enumeration(self):
        df = generate_dataset(4, 8)
        matrix = distance_matrix(df)
        demand = [0, 1, 1, 1, 1]
        baseline = nearest_neighbor(matrix, demand, 4)
        routes, _ = solve_cvrp(matrix, demand, 4, 1, baseline, 1)
        exact = min(route_distance_m([0, *p, 0], matrix) for p in itertools.permutations(range(1, 5)))
        self.assertEqual(sum(route_distance_m(r, matrix) for r in routes), exact)

    def test_capacity_and_customer_coverage_at_requested_sizes(self):
        for customers in [30, 40, 50]:
            with self.subTest(customers=customers):
                df = generate_dataset(customers)
                validate_dataset(df, 100)
                matrix, demand = distance_matrix(df), df.demand_units.to_numpy(dtype=int)
                self.assertTrue(np.array_equal(matrix, matrix.T))
                self.assertTrue((np.diag(matrix) == 0).all())
                baseline = nearest_neighbor(matrix, demand, 100)
                optimized, _ = solve_cvrp(matrix, demand, 100, len(baseline), baseline, 1)
                for routes in [baseline, optimized]:
                    validate_routes(routes, demand, 100, len(baseline))
                    self.assertEqual(sum(len(r)-2 for r in routes), customers)
                    self.assertEqual(sum(sum(demand[n] for n in r[1:-1]) for r in routes), demand.sum())
                self.assertLessEqual(sum(route_distance_m(r, matrix) for r in optimized),
                                     sum(route_distance_m(r, matrix) for r in baseline))


if __name__ == "__main__":
    unittest.main()

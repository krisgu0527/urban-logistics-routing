"""Generate and validate explicitly synthetic delivery data; coordinates are km."""
import numpy as np
import pandas as pd


def generate_dataset(customers=40, seed=2027):
    if not 1 <= customers <= 200:
        raise ValueError("customers must be between 1 and 200")
    rng = np.random.default_rng(seed)
    coordinates = np.round(rng.uniform(0, 20, (customers, 2)), 3)
    coordinates = np.vstack(([10.0, 10.0], coordinates))
    return pd.DataFrame({
        "node_id": np.arange(customers + 1),
        "node_type": ["depot"] + ["customer"] * customers,
        "x_km": coordinates[:, 0], "y_km": coordinates[:, 1],
        "demand_units": np.r_[0, rng.integers(5, 21, customers)],
        "data_source": "synthetic",
    })


def validate_dataset(df, capacity):
    required = {"node_id", "node_type", "x_km", "y_km", "demand_units", "data_source"}
    if not required.issubset(df.columns) or not 2 <= len(df) <= 201:
        raise ValueError("Dataset requires the documented columns and 1-200 customers")
    if not isinstance(capacity, int) or capacity <= 0:
        raise ValueError("Vehicle capacity must be a positive integer")
    if df["node_id"].tolist() != list(range(len(df))):
        raise ValueError("node_id must be ordered, unique, and contiguous starting at 0")
    if df["node_type"].tolist() != ["depot"] + ["customer"] * (len(df) - 1):
        raise ValueError("Row 0 must be the only depot")
    values = df[["x_km", "y_km", "demand_units"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (np.abs(values[:, :2]) > 10000).any():
        raise ValueError("Coordinates/demands must be finite; coordinates within +/-10000 km")
    demand = values[:, 2]
    if demand[0] != 0 or (demand[1:] <= 0).any() or (demand != np.floor(demand)).any():
        raise ValueError("Depot demand must be zero; customer demands positive integers")
    if (demand > capacity).any():
        raise ValueError("A customer's demand exceeds vehicle capacity; split delivery is disabled")
    if not df["data_source"].eq("synthetic").all():
        raise ValueError("This educational experiment requires explicitly synthetic data")


def distance_matrix(df):
    xy = df[["x_km", "y_km"]].to_numpy(dtype=float)
    # ponytail: Euclidean proxy for 200 or fewer customers; use road-network costs for real dispatch.
    delta = xy[:, None, :] - xy[None, :, :]
    return np.rint(np.linalg.norm(delta, axis=2) * 1000).astype(np.int64)

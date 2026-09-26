"""Headless Matplotlib plots, suitable for Windows terminals and GitHub."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = ["#2166ac", "#bf812d", "#6b8e23", "#b24b78", "#725b9b"]


def plot_routes(df, routes, metrics, title, destination):
    fig, ax = plt.subplots(figsize=(10, 8), layout="constrained")
    for i, route in enumerate(routes):
        xy = df.iloc[route]
        ax.plot(xy.x_km, xy.y_km, color=COLORS[i % len(COLORS)],
                linestyle=["-", "--", "-."][i // len(COLORS) % 3],
                linewidth=1.7, marker="o", markersize=4,
                label=f"V{i+1}: {metrics.iloc[i].distance_km:.2f} km | load {metrics.iloc[i].load_units}")
    ax.scatter(df.iloc[0].x_km, df.iloc[0].y_km, marker="*", s=240,
               color="#202830", edgecolors="white", zorder=10, label="Depot (0)")
    ax.set(xlabel="Synthetic x coordinate (km)", ylabel="Synthetic y coordinate (km)",
           title=f"{title}\n{metrics.distance_km.sum():.2f} km | {len(routes)} vehicles",
           xlim=(min(-1, df.x_km.min()-1), max(21, df.x_km.max()+1)),
           ylim=(min(-1, df.y_km.min()-1), max(21, df.y_km.max()+1)))
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=9)
    fig.supxlabel("Synthetic scenario; straight-line distances, not a real road map.\n"
                  "Labels = customer IDs; ordered visits are recorded in routes.json.", fontsize=9)
    # Nearby customers can overlap: try small label offsets, without another dependency.
    fig.canvas.draw()
    renderer, occupied = fig.canvas.get_renderer(), []
    offsets = [(5, 5), (5, -12), (-5, 5), (-5, -12), (12, 14),
               (-12, 14), (12, -20), (-12, -20), (0, 25), (0, -28)]
    for row in df.iloc[1:].itertuples():
        label = ax.annotate(str(row.node_id), (row.x_km, row.y_km),
                            textcoords="offset points", xytext=offsets[0], fontsize=8)
        label.set_in_layout(False)
        for dx, dy in offsets:
            label.set_position((dx, dy))
            label.set_ha("left" if dx >= 0 else "right")
            box = label.get_window_extent(renderer).expanded(1.15, 1.2)
            if not any(box.overlaps(other) for other in occupied):
                break
        occupied.append(box)
    fig.savefig(destination, dpi=170)
    plt.close(fig)


def plot_comparison(summary, destination):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), layout="constrained")
    for ax, column, title, unit in zip(axes,
            ["total_distance_km", "vehicles_used", "average_route_km"],
            ["Total distance", "Vehicles used", "Average route length"], ["km", "vehicles", "km"]):
        values = summary[column].tolist()
        bars = ax.bar(["Baseline", "OR-Tools"], values, color=["#97a4b0", "#2166ac"], width=0.58)
        ax.bar_label(bars, labels=[f"{v:.0f}" if unit == "vehicles" else f"{v:.2f}" for v in values], padding=5)
        ax.set(title=title, ylabel=unit, ylim=(0, max(1, max(values) * 1.22)))
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("Routing performance | same synthetic dataset and fleet limit", fontsize=14)
    fig.supxlabel("Average route length = total distance / used vehicles. Panels have separate units/scales.", fontsize=9)
    fig.savefig(destination, dpi=170)
    plt.close(fig)

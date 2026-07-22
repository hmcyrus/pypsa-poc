#!/usr/bin/env python3
"""plot_pypsa_map.py — minimal proof that the OSM-derived coordinates in
bus_locations.csv can drive PyPSA's built-in static plotting (n.plot()).

Scope (deliberately small): inject lon/lat onto the network buses, then render
one topology-only map coloured by nominal voltage. No cartopy, no analysis
overlays — this only answers "do our coordinates feed PyPSA plotting?".

Usage:
    .venv/bin/python src/geo/plot_pypsa_map.py
    # Windows: .venv\\Scripts\\python.exe src\\geo\\plot_pypsa_map.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless render
import matplotlib.pyplot as plt
import pandas as pd
import pypsa

REPO = Path(__file__).resolve().parents[2]
PYPSA_DIR = REPO / "data" / "pipeline" / "pypsa-components"
GEO_CSV = REPO / "data" / "pipeline" / "geo" / "bus_locations.csv"
OUT_PNG = REPO / "data" / "pipeline" / "geo" / "pypsa_static_map.png"

# PyPSA convention: bus x = longitude, y = latitude.
VOLTAGE_COLORS = {400.0: "#d62728", 230.0: "#ff7f0e", 132.0: "#1f77b4"}


def build_coord_map() -> dict[str, tuple[float, float]]:
    """bus name -> (lon, lat) for every located place in bus_locations.csv.

    bus_names is a pipe-separated list of the network bus ids that share a
    place (e.g. "Agargaon_132kV|Agargaon_230kV").
    """
    geo = pd.read_csv(GEO_CSV)
    geo = geo[geo["lat"].notna() & geo["lon"].notna()]
    coords: dict[str, tuple[float, float]] = {}
    for _, row in geo.iterrows():
        for bus in str(row["bus_names"]).split("|"):
            bus = bus.strip()
            if bus:
                coords[bus] = (float(row["lon"]), float(row["lat"]))
    return coords


def main() -> int:
    n = pypsa.Network()
    n.import_from_csv_folder(str(PYPSA_DIR))

    coords = build_coord_map()
    n.buses["x"] = n.buses.index.map(lambda b: coords.get(b, (float("nan"),))[0])
    n.buses["y"] = n.buses.index.map(
        lambda b: coords.get(b, (float("nan"), float("nan")))[1]
    )

    located = n.buses[["x", "y"]].notna().all(axis=1)
    n_located = int(located.sum())
    print(f"buses located: {n_located}/{len(n.buses)}")
    missing = list(n.buses.index[~located])
    if missing:
        print(f"buses without coords ({len(missing)}): {', '.join(missing)}")

    # Restrict to located buses; lines with an unlocated endpoint are dropped so
    # PyPSA does not try to draw an edge to a NaN coordinate.
    n.remove("Bus", n.buses.index[~located])

    bus_colors = n.buses["v_nom"].map(VOLTAGE_COLORS).fillna("#7f7f7f")

    fig, ax = plt.subplots(figsize=(9, 12))
    n.plot(
        ax=ax,
        bus_colors=bus_colors,
        bus_sizes=0.0015,
        line_colors="#999999",
        line_widths=0.6,
        geomap=False,  # no cartopy dependency
    )
    handles = [
        plt.Line2D([], [], marker="o", ls="", color=c, label=f"{int(v)} kV")
        for v, c in VOLTAGE_COLORS.items()
    ]
    ax.legend(handles=handles, title="Nominal voltage", loc="upper left")
    ax.set_title(
        f"Bangladesh grid — PyPSA n.plot() proof\n"
        f"{n_located} buses located via OSM geocoding"
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"wrote {OUT_PNG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

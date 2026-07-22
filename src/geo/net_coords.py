#!/usr/bin/env python3
"""net_coords.py — shared helper: build the PyPSA network and inject the
OSM-derived coordinates from bus_locations.csv onto bus x/y.

Every plotting backend (static n.plot, interactive n.explore/iplot) reuses
this so they all draw from identical coordinates.

PyPSA convention: bus x = longitude, y = latitude (both EPSG:4326 degrees).
"""

from pathlib import Path

import pandas as pd
import pypsa

REPO = Path(__file__).resolve().parents[2]
PYPSA_DIR = REPO / "data" / "pipeline" / "pypsa-components"
GEO_CSV = REPO / "data" / "pipeline" / "geo" / "bus_locations.csv"

# Bangladesh bounding box [lon_min, lon_max, lat_min, lat_max] for framing maps.
BD_BOUNDARIES = [88.0, 92.7, 20.5, 26.7]

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


def build_network_with_coords(drop_unlocated: bool = True):
    """Return (network, unlocated_bus_names).

    Injects lon/lat onto bus x/y. When drop_unlocated is True, buses without a
    coordinate are removed (so branches are never drawn to a NaN endpoint).
    """
    n = pypsa.Network()
    n.import_from_csv_folder(str(PYPSA_DIR))

    coords = build_coord_map()
    nan = float("nan")
    n.buses["x"] = n.buses.index.map(lambda b: coords.get(b, (nan, nan))[0])
    n.buses["y"] = n.buses.index.map(lambda b: coords.get(b, (nan, nan))[1])

    located = n.buses[["x", "y"]].notna().all(axis=1)
    unlocated = list(n.buses.index[~located])
    if drop_unlocated and unlocated:
        n.remove("Bus", unlocated)
    return n, unlocated

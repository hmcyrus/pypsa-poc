"""Phase B of the geocoding plan: validate Phase-A coordinates against line
lengths, compute feasible regions for unresolved places, and report.

B1: flag connected place-pairs where straight-line distance exceeds
    1.1 x line_length; reopen both endpoints.
B2: for places without accepted coords, emit the disc constraints
    (neighbor coord + 1.2 x line_length radius) that any candidate must satisfy.
B3: print accepted / provisional / unresolved counts after the sweep.

Usage:
    .venv\\Scripts\\python.exe src\\geo\\validate_locations.py
"""

import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
CANONICAL = REPO / "data" / "pipeline" / "canonical"
GEO_DIR = REPO / "data" / "pipeline" / "geo"

LENGTH_TOLERANCE = 1.1     # B1: haversine > 1.1 x length -> bad geocode
SHORT_LINE_FLOOR_KM = 20.0  # secondary check: long line, near-zero distance
SHORT_RATIO = 0.2
DISC_TOLERANCE = 1.2       # B2 disc radius multiplier


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def to_place(bus: str) -> str:
    return re.sub(r"_\d+(?:\.\d+)?kV$", "", bus)


def main() -> int:
    locs = pd.read_csv(GEO_DIR / "bus_locations.csv")
    lines = pd.read_csv(CANONICAL / "lines.csv")

    # Re-promote places reopened by a previous sweep so the check is
    # idempotent: culprit detection below re-demotes the actual offenders.
    reopened_mask = locs["status"] == "reopened"
    locs.loc[reopened_mask & (locs["confidence"] == "high"), "status"] = "accepted"
    locs.loc[reopened_mask & (locs["confidence"] != "high"), "status"] = "provisional"

    lines["p0"] = lines["bus0"].map(to_place)
    lines["p1"] = lines["bus1"].map(to_place)
    # shortest declared length per place pair governs the feasibility check
    pairs = (
        lines[lines["p0"] != lines["p1"]]
        .groupby(["p0", "p1"], as_index=False)["length"]
        .min()
    )

    coords = locs.set_index("place")[["lat", "lon", "status"]]

    # ---------------- B1: line-length sweep ----------------
    flags = []
    for _, row in pairs.iterrows():
        a, b = coords.loc[row["p0"]], coords.loc[row["p1"]]
        if pd.isna(a["lat"]) or pd.isna(b["lat"]):
            continue
        if a["status"] == "unresolved" or b["status"] == "unresolved":
            continue
        dist = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
        if dist > LENGTH_TOLERANCE * row["length"]:
            kind = "too_far"
        elif row["length"] >= SHORT_LINE_FLOOR_KM and dist < SHORT_RATIO * row["length"]:
            kind = "too_close"
        else:
            continue
        flags.append(
            {
                "p0": row["p0"],
                "p1": row["p1"],
                "line_length_km": row["length"],
                "haversine_km": round(dist, 1),
                "ratio": round(dist / row["length"], 2),
                "kind": kind,
            }
        )
    flags = pd.DataFrame(flags)

    # Culprit detection: a place is reopened only if its violating pairs
    # outnumber (or tie) its passing pairs. A well-connected correct place
    # flagged by one bad neighbor keeps its anchor status.
    n_pass, n_viol = {}, {}
    viol_pairs = (
        set(map(tuple, flags.loc[flags["kind"] == "too_far", ["p0", "p1"]].values))
        if not flags.empty
        else set()
    )
    for _, row in pairs.iterrows():
        a, b = coords.loc[row["p0"]], coords.loc[row["p1"]]
        if pd.isna(a["lat"]) or pd.isna(b["lat"]):
            continue
        if a["status"] == "unresolved" or b["status"] == "unresolved":
            continue
        key = (row["p0"], row["p1"])
        bucket = n_viol if key in viol_pairs else n_pass
        for p in key:
            bucket[p] = bucket.get(p, 0) + 1

    reopened = set()
    for (p0, p1) in viol_pairs:
        culprits = [
            p for p in (p0, p1)
            if n_viol.get(p, 0) >= n_pass.get(p, 0)
        ]
        # if neither side looks guilty, distrust both
        reopened.update(culprits if culprits else (p0, p1))
    locs["status"] = locs.apply(
        lambda r: "reopened" if r["place"] in reopened and r["status"] in ("accepted", "provisional")
        else r["status"],
        axis=1,
    )

    # ---------------- B2: feasible-region constraints ----------------
    unresolved = locs[locs["status"].isin(["unresolved", "reopened", "provisional"])]["place"]
    located = locs[locs["status"] == "accepted"].set_index("place")[["lat", "lon"]]
    adjacency = {}
    for _, row in pairs.iterrows():
        adjacency.setdefault(row["p0"], []).append((row["p1"], row["length"]))
        adjacency.setdefault(row["p1"], []).append((row["p0"], row["length"]))

    regions = {}
    for place in unresolved:
        discs = [
            {
                "neighbor": nb,
                "lat": located.loc[nb, "lat"],
                "lon": located.loc[nb, "lon"],
                "radius_km": round(DISC_TOLERANCE * length, 1),
            }
            for nb, length in adjacency.get(place, [])
            if nb in located.index
        ]
        if discs:
            # crude feasible center: neighbor centroid weighted by 1/radius
            w = [1.0 / d["radius_km"] for d in discs]
            regions[place] = {
                "center_lat": round(sum(d["lat"] * wi for d, wi in zip(discs, w)) / sum(w), 5),
                "center_lon": round(sum(d["lon"] * wi for d, wi in zip(discs, w)) / sum(w), 5),
                "max_radius_km": min(d["radius_km"] for d in discs),
                "discs": discs,
            }

    # ---------------- outputs ----------------
    locs.to_csv(GEO_DIR / "bus_locations.csv", index=False)
    flags_path = GEO_DIR / "length_flags.csv"
    flags.to_csv(flags_path, index=False)
    regions_path = GEO_DIR / "feasible_regions.json"
    regions_path.write_text(json.dumps(regions, indent=1), encoding="utf-8")

    # ---------------- B3: report ----------------
    print("B1: pair sweep over", len(pairs), "connected place pairs")
    if flags.empty:
        print("  no flags")
    else:
        print(flags.sort_values("ratio", ascending=False).to_string(index=False))
        print(f"  reopened endpoints: {len(reopened)}")
    print("\nB3 status after sweep:")
    print(locs["status"].value_counts().to_string())
    print(f"\nWrote {flags_path}, {regions_path}, updated bus_locations.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
network-builder.py

Reads data/pypsa-components/buses.csv and lines.csv (produced by
line-bus-processor.py) and builds a PyPSA network.
"""

from pathlib import Path

import pandas as pd
import pypsa

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
PYPSA_DIR = ROOT / "data" / "pypsa-components"


def build_network() -> pypsa.Network:
    buses_df = pd.read_csv(PYPSA_DIR / "buses.csv", index_col="name")
    lines_df = pd.read_csv(PYPSA_DIR / "lines.csv", index_col="name")

    n = pypsa.Network()

    for name, row in buses_df.iterrows():
        n.add("Bus", name, v_nom=float(row["v_nom"]))

    for name, row in lines_df.iterrows():
        n.add(
            "Line",
            name,
            bus0=row["bus0"],
            bus1=row["bus1"],
            length=row["length"],
            r=row["r"],
            x=row["x"],
            b=row["b"],
            s_nom=row["s_nom"],
        )

    return n


def _parse_v_nom(bus_name: str) -> float | None:
    import re
    m = re.search(r'(\d+(?:\.\d+)?)kV', bus_name, re.IGNORECASE)
    return float(m.group(1)) if m else None


def main() -> None:
    n = build_network()

    print("=" * 60)
    print("PyPSA Network Summary")
    print("=" * 60)
    print(f"\n  Buses : {len(n.buses)}")
    print(f"  Lines : {len(n.lines)}")

    print("\n  Buses by voltage level:")
    for v, grp in n.buses.groupby("v_nom"):
        print(f"    {int(v):>4} kV — {len(grp):>3} buses")

    print("\n  Lines by voltage level:")
    n.lines["_v"] = n.lines["bus0"].apply(_parse_v_nom)
    for v, grp in n.lines.groupby("_v"):
        print(f"    {int(v):>4} kV — {len(grp):>3} lines")
    n.lines.drop(columns=["_v"], inplace=True)

    print()


if __name__ == "__main__":
    main()

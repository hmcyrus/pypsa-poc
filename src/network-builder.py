#!/usr/bin/env python3
"""
network-builder.py

Reads data/pipeline/pypsa-components/buses.csv and lines.csv (produced by
line-bus-processor.py) and builds a PyPSA network.
"""

from pathlib import Path

import pandas as pd
import pypsa

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
PYPSA_DIR = ROOT / "data" / "pipeline" / "pypsa-components"


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


def check_network_correctness(n: pypsa.Network) -> bool:
    """
    Checks structural correctness of the network after buses and lines are added.

    Two checks are performed:
      1. No isolated buses — every bus must be connected to at least one branch.
      2. Single connected component — no islands (groups of buses unreachable
         from the rest of the network).

    Additionally, PyPSA's built-in consistency_check() is run, which covers:
      - Unknown buses referenced by components
      - Zero-impedance lines
      - Zero s_nom on transformers
      - NaN/inf in power attributes
      - Data-type mismatches
      Use n.consistency_check(strict=['disconnected_buses', 'zero_impedances', ...])
      to turn specific warnings into hard errors.

    Other useful PyPSA soundness tools (not called here):
      - n.sanitize()              : auto-add missing buses/carriers referenced by components
      - n.graph()                 : NetworkX MultiGraph of the network topology
      - n.adjacency_matrix()      : sparse bus-to-bus connectivity matrix
      - n.cycle_matrix()          : independent cycle basis (mesh analysis)
      - n.calculate_dependent_values() : derive per-unit impedances before power flow

    Returns True if both connectivity checks pass, False otherwise.
    """
    print("\n" + "=" * 60)
    print("Network Correctness Check")
    print("=" * 60)

    passed = True

    # ── 1. Isolated buses — not attached to any branch ───────────────────
    connected_buses: set[str] = set(n.lines["bus0"]) | set(n.lines["bus1"])
    if not n.transformers.empty:
        connected_buses |= set(n.transformers["bus0"]) | set(n.transformers["bus1"])
    if not n.links.empty:
        connected_buses |= set(n.links["bus0"]) | set(n.links["bus1"])

    isolated = sorted(set(n.buses.index) - connected_buses)
    if isolated:
        print(f"\n  [FAIL] {len(isolated)} bus(es) are not connected to any branch:")
        for bus in isolated:
            print(f"    • {bus}")
        passed = False
    else:
        print(f"\n  [PASS] All {len(n.buses)} buses are attached to at least one branch.")

    # ── 2. Connected-component analysis — detect islands ─────────────────
    n.determine_network_topology()
    n_sub = len(n.sub_networks)

    if n_sub > 1:
        print(f"\n  [FAIL] Network has {n_sub} disconnected islands:")
        for idx, row in n.sub_networks.iterrows():
            sub_buses = row["obj"].components.buses.static.index.tolist()
            preview = sub_buses[:5]
            suffix = ", ..." if len(sub_buses) > 5 else ""
            print(f"    Island {idx} ({len(sub_buses)} buses): {preview}{suffix}")
        passed = False
    else:
        print(f"  [PASS] Network is fully connected — 1 sub-network, {len(n.buses)} buses.")

    # ── 3. PyPSA built-in consistency check ──────────────────────────────
    print("\n  Running PyPSA consistency_check()…")
    n.consistency_check()
    print("  Done. Any issues appear as warnings above.")

    status = "PASSED" if passed else "FAILED"
    print(f"\n  Overall: {status}")
    print("=" * 60)
    return passed


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

    check_network_correctness(n)


if __name__ == "__main__":
    main()

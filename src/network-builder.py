#!/usr/bin/env python3
"""
network-builder.py

Builds a PyPSA network from the per-component CSVs in
data/pipeline/pypsa-components/ (produced by line-bus-processor.py,
generator_builder.py, load_builder.py, transformer_builder.py,
link_builder.py, finalised by bus_supplement.py).

Uses pypsa.Network.import_from_csv_folder, which requires the directory
to contain files named exactly buses.csv, generators.csv, lines.csv,
loads.csv, transformers.csv, links.csv — schema matches our outputs.
Reference: https://docs.pypsa.org/latest/user-guide/import-export/
"""

from pathlib import Path

import pypsa

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
PYPSA_DIR = ROOT / "data" / "pipeline" / "pypsa-components"


def build_network() -> pypsa.Network:
    n = pypsa.Network()
    n.import_from_csv_folder(str(PYPSA_DIR))
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


def _bus_v_nom(n: pypsa.Network, bus_name: str) -> float | None:
    """Look up v_nom for a bus by name; None if not present."""
    if bus_name not in n.buses.index:
        return None
    return float(n.buses.at[bus_name, "v_nom"])


def main() -> None:
    n = build_network()

    print("=" * 60)
    print("PyPSA Network Summary")
    print("=" * 60)
    print(f"\n  Buses        : {len(n.buses)}")
    print(f"  Lines        : {len(n.lines)}")
    print(f"  Transformers : {len(n.transformers)}")
    print(f"  Links        : {len(n.links)}")
    print(f"  Generators   : {len(n.generators)}")
    print(f"  Loads        : {len(n.loads)}")

    print("\n  Buses by voltage level:")
    for v, grp in n.buses.groupby("v_nom"):
        print(f"    {int(v):>4} kV — {len(grp):>3} buses")

    if not n.lines.empty:
        print("\n  Lines by voltage level:")
        lv = n.lines["bus0"].map(lambda b: _bus_v_nom(n, b))
        for v, count in lv.value_counts().sort_index().items():
            print(f"    {int(v):>4} kV — {count:>3} lines")

    if not n.transformers.empty:
        print("\n  Transformers by voltage pair:")
        hv = n.transformers["bus0"].map(lambda b: _bus_v_nom(n, b))
        lv = n.transformers["bus1"].map(lambda b: _bus_v_nom(n, b))
        pairs = list(zip(hv, lv))
        for pair, count in sorted({p: pairs.count(p) for p in set(pairs)}.items()):
            print(f"    {int(pair[0]):>3}/{int(pair[1]):<3} kV — {count:>3}")

    if not n.links.empty:
        print("\n  Links by carrier:")
        for carrier, grp in n.links.groupby("carrier"):
            print(f"    {carrier:<3} — {len(grp):>2}   ({grp['p_nom'].sum():.0f} MW)")

    if not n.generators.empty:
        print("\n  Generators by carrier:")
        for carrier, grp in n.generators.groupby("carrier"):
            print(f"    {carrier:<10} {len(grp):>3}   ({grp['p_nom'].sum():.0f} MW)")

    if not n.loads.empty:
        print(f"\n  Total load p_set : {n.loads['p_set'].sum():.0f} MW")

    print()
    check_network_correctness(n)


if __name__ == "__main__":
    main()

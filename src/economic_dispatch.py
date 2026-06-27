#!/usr/bin/env python3
"""
economic_dispatch.py

Single-snapshot linear economic dispatch on one connected sub-network of
the PyPSA network produced by network-builder.py.

The full network currently has 22 disconnected islands. This script:
  1. Loads the network from data/pipeline/pypsa-components/
  2. Calls determine_network_topology() to label each bus with sub_network
  3. Restricts the network in-place to TARGET_SUB_NETWORK
  4. Solves with HiGHS via n.optimize()
  5. Prints dispatch, total cost, idle generators, and binding lines

Run:
    python src/economic_dispatch.py
"""

from pathlib import Path

import pypsa

ROOT      = Path(__file__).parent.parent
PYPSA_DIR = ROOT / "data" / "pipeline" / "pypsa-components"

TARGET_SUB_NETWORK = "0"

COMPONENT_ATTR = {
    "Bus":         "buses",
    "Line":        "lines",
    "Transformer": "transformers",
    "Link":        "links",
    "Generator":   "generators",
    "Load":        "loads",
}


def load_network() -> pypsa.Network:
    n = pypsa.Network()
    n.import_from_csv_folder(str(PYPSA_DIR))
    n.determine_network_topology()
    return n


def print_sub_network_sizes(n: pypsa.Network) -> None:
    sizes = n.buses.groupby("sub_network").size().sort_values(ascending=False)
    print("\n  Sub-network sizes (buses):")
    for sub_id, size in sizes.items():
        marker = "  <-- target" if sub_id == TARGET_SUB_NETWORK else ""
        print(f"    {sub_id:>4} : {size:>3}{marker}")


def restrict_to_sub_network(n: pypsa.Network, sub_id: str) -> None:
    """
    Drop every component not anchored to a bus in sub_network `sub_id`.

    Order matters: drop dependents (generators, loads, branches) before
    dropping the buses they reference, so we never leave dangling refs.
    """
    keep_buses = set(n.buses.index[n.buses["sub_network"] == sub_id])

    for comp in ["Generator", "Load"]:
        df = getattr(n, COMPONENT_ATTR[comp])
        drop = df.index[~df["bus"].isin(keep_buses)].tolist()
        if drop:
            n.remove(comp, drop)

    for comp in ["Line", "Transformer", "Link"]:
        df = getattr(n, COMPONENT_ATTR[comp])
        if df.empty:
            continue
        drop = df.index[~(df["bus0"].isin(keep_buses) & df["bus1"].isin(keep_buses))].tolist()
        if drop:
            n.remove(comp, drop)

    drop_buses = [b for b in n.buses.index if b not in keep_buses]
    if drop_buses:
        n.remove("Bus", drop_buses)


def print_summary(n: pypsa.Network) -> None:
    print(f"\n  Buses        : {len(n.buses)}")
    print(f"  Lines        : {len(n.lines)}")
    print(f"  Transformers : {len(n.transformers)}")
    print(f"  Links        : {len(n.links)}")
    print(f"  Generators   : {len(n.generators)}")
    print(f"  Loads        : {len(n.loads)}")


def check_feasibility(n: pypsa.Network) -> bool:
    total_load = float(n.loads["p_set"].sum()) if not n.loads.empty else 0.0
    total_cap  = float((n.generators["p_nom"] * n.generators["p_max_pu"]).sum()) \
                 if not n.generators.empty else 0.0

    print(f"\n  Total load                : {total_load:>10,.1f} MW")
    print(f"  Total available capacity  : {total_cap:>10,.1f} MW")

    if n.generators.empty:
        print("  [WARN] No generators in this sub-network — infeasible.")
        return False
    if n.loads.empty:
        print("  [WARN] No loads in this sub-network — nothing to dispatch.")
        return False
    if total_load > total_cap:
        print(f"  [WARN] Capacity shortfall of {total_load - total_cap:,.1f} MW — expect infeasibility.")
        return False
    return True


def report(n: pypsa.Network) -> None:
    print("\n" + "=" * 60)
    print("Dispatch results")
    print("=" * 60)

    dispatch   = n.generators_t.p.iloc[0].sort_values(ascending=False)
    mc         = n.generators["marginal_cost"]
    total_gen  = float(dispatch.sum())
    total_cost = float((dispatch * mc).sum())

    print(f"\n  Total generation : {total_gen:>10,.1f} MW")
    print(f"  Total cost       : {total_cost:>10,.2f} USD/h")
    if total_gen > 0:
        print(f"  Average cost     : {total_cost / total_gen:>10,.2f} USD/MWh")

    print("\n  Top 15 generators by dispatch:")
    for name, p in dispatch.head(15).items():
        cost = float(mc.at[name])
        print(f"    {name[:45]:<45} {p:>8,.1f} MW   @ {cost:>6.2f} USD/MWh")

    idle = dispatch[dispatch < 0.1]
    print(f"\n  Idle generators  : {len(idle)} / {len(dispatch)}")

    if not n.buses_t.marginal_price.empty:
        prices = n.buses_t.marginal_price.iloc[0]
        print(f"\n  Locational marginal prices (USD/MWh):")
        print(f"    min  {prices.min():>6.2f}   max  {prices.max():>6.2f}   mean  {prices.mean():>6.2f}")

    if not n.lines.empty and not n.lines_t.p0.empty:
        loading = (n.lines_t.p0.iloc[0].abs() / n.lines["s_nom"]).sort_values(ascending=False)
        tight = loading[loading > 0.9]
        if len(tight):
            print(f"\n  Lines above 90% loading ({len(tight)}):")
            for name, lf in tight.head(10).items():
                print(f"    {name[:45]:<45} {lf * 100:>5.1f}%")
        else:
            print(f"\n  Highest line loading : {loading.iloc[0] * 100:.1f}%")


def main() -> None:
    print("=" * 60)
    print("Loading network")
    print("=" * 60)
    n = load_network()
    print_sub_network_sizes(n)

    print("\n" + "=" * 60)
    print(f"Restricting to sub-network '{TARGET_SUB_NETWORK}'")
    print("=" * 60)
    restrict_to_sub_network(n, TARGET_SUB_NETWORK)
    print_summary(n)

    if not check_feasibility(n):
        return

    print("\n  Solving with HiGHS…")
    status, condition = n.optimize(solver_name="highs")
    print(f"  Solver status: {status} ({condition})")
    if status != "ok":
        return

    report(n)


if __name__ == "__main__":
    main()

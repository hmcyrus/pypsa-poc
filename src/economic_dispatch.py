#!/usr/bin/env python3
"""
economic_dispatch.py

Single-snapshot linear economic dispatch on one connected sub-network of
the PyPSA network produced by network-builder.py.

The full network currently has 22 disconnected islands. This script:
  1. Loads the network from data/pipeline/pypsa-components/
  2. Calls determine_network_topology() to label each bus with sub_network
  3. Restricts the network in-place to TARGET_SUB_NETWORK
  4. Runs structural pre-checks that flag common infeasibility causes
  5. Solves with HiGHS via n.optimize()
  6. On success: prints dispatch, total cost, idle generators, binding lines
     On failure: re-solves a slack-relaxed copy to localise *which buses*
     cannot balance and *why* (shortfall vs. forced over-supply)

Run:
    python src/economic_dispatch.py
"""

from pathlib import Path

import pandas as pd
import pypsa

ROOT      = Path(__file__).parent.parent
PYPSA_DIR = ROOT / "data" / "pipeline" / "pypsa-components"

TARGET_SUB_NETWORK = "0"

# Penalty (USD/MWh) on slack injection/absorption in the relaxed diagnostic
# solve. Must dominate any real marginal cost so slack is used only when the
# real network genuinely cannot balance a bus.
SLACK_PENALTY = 1.0e6

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


# --------------------------------------------------------------------------- #
# Structural pre-checks                                                        #
# --------------------------------------------------------------------------- #

def _branch_endpoints(n: pypsa.Network):
    """Yield (bus0, bus1) Series for every branch-like component present."""
    for comp in ["Line", "Transformer", "Link"]:
        df = getattr(n, COMPONENT_ATTR[comp])
        if not df.empty:
            yield comp, df


def structural_checks(n: pypsa.Network) -> bool:
    """
    Report structural red flags that commonly drive a dispatch LP infeasible.

    Returns False only for hard show-stoppers (no generators, no loads);
    everything else is reported as a warning but we still attempt the solve.
    """
    print("\n" + "=" * 60)
    print("Structural pre-checks")
    print("=" * 60)

    ok = True

    # --- global energy balance ------------------------------------------- #
    total_load = float(n.loads["p_set"].sum()) if not n.loads.empty else 0.0
    total_cap  = float((n.generators["p_nom"] * n.generators["p_max_pu"]).sum()) \
                 if not n.generators.empty else 0.0
    print(f"\n  Total load                : {total_load:>10,.1f} MW")
    print(f"  Total available capacity  : {total_cap:>10,.1f} MW")
    print(f"  Reserve margin            : {total_cap - total_load:>10,.1f} MW")

    if n.generators.empty:
        print("  [STOP] No generators in this sub-network — infeasible.")
        return False
    if n.loads.empty:
        print("  [STOP] No loads in this sub-network — nothing to dispatch.")
        return False
    if total_load > total_cap:
        print(f"  [WARN] System-wide capacity shortfall of "
              f"{total_load - total_cap:,.1f} MW — guaranteed infeasible.")
        ok = False

    # --- minimum forced generation vs. load ------------------------------ #
    # p_min_pu > 0 means a generator MUST produce at least that fraction.
    forced_gen = float((n.generators["p_nom"] *
                        n.generators.get("p_min_pu", 0.0)).sum())
    if forced_gen > total_load + 1e-6:
        print(f"  [WARN] Forced minimum generation {forced_gen:,.1f} MW exceeds "
              f"total load {total_load:,.1f} MW — over-supply, infeasible "
              f"unless excess can be exported/curtailed.")
        ok = False

    # --- isolated buses (no branch touches them) ------------------------- #
    touched: set[str] = set()
    for _comp, df in _branch_endpoints(n):
        touched |= set(df["bus0"]) | set(df["bus1"])
    isolated = [b for b in n.buses.index if b not in touched]
    if isolated:
        loads_on = n.loads.groupby("bus")["p_set"].sum()
        gens_on  = n.generators.groupby("bus")["p_nom"].sum()
        bad = []
        for b in isolated:
            ld = float(loads_on.get(b, 0.0))
            gn = float(gens_on.get(b, 0.0))
            # An islanded bus is only feasible if its local gen can meet its
            # local load exactly on its own.
            if ld > gn + 1e-6 or (ld == 0.0 and gn == 0.0):
                bad.append((b, ld, gn))
        if bad:
            print(f"\n  [WARN] {len(bad)} isolated bus(es) that cannot self-balance:")
            for b, ld, gn in bad[:15]:
                print(f"    {b[:45]:<45} load {ld:>7.1f}  gen-cap {gn:>7.1f}")
            ok = False

    # --- forced flows on links/lines (p_min_pu) -------------------------- #
    if not n.links.empty and "p_min_pu" in n.links:
        forced = n.links[n.links["p_min_pu"].abs() > 1e-9]
        if not forced.empty:
            print(f"\n  [INFO] {len(forced)} link(s) with forced flow "
                  f"(p_min_pu != 0) — these inject/withdraw a FIXED amount of "
                  f"power that the rest of the network must absorb:")
            for name, row in forced.head(15).iterrows():
                fixed = float(row["p_nom"]) * float(row["p_min_pu"])
                print(f"    {name[:40]:<40} {fixed:>8,.1f} MW  "
                      f"{row['bus0'][:18]} -> {row['bus1'][:18]}")

    # --- zero / NaN ratings ---------------------------------------------- #
    for comp in ["Line", "Transformer"]:
        df = getattr(n, COMPONENT_ATTR[comp])
        if df.empty:
            continue
        bad = df[(df["s_nom"].isna()) | (df["s_nom"] <= 0)]
        if not bad.empty:
            print(f"\n  [WARN] {len(bad)} {comp}(s) with zero/NaN s_nom "
                  f"(act as open circuits): {list(bad.index[:5])}")
            ok = False

    bad_x = []
    for comp in ["Line", "Transformer"]:
        df = getattr(n, COMPONENT_ATTR[comp])
        if df.empty:
            continue
        z = df[(df["x"].isna()) | (df["x"] == 0)]
        if not z.empty:
            bad_x.extend(f"{comp}:{i}" for i in z.index[:5])
    if bad_x:
        print(f"\n  [WARN] Branches with zero/NaN reactance x "
              f"(break DC power flow): {bad_x}")
        ok = False

    if ok:
        print("\n  No obvious structural problems found.")
    return ok


# --------------------------------------------------------------------------- #
# Slack-relaxed diagnostic solve                                              #
# --------------------------------------------------------------------------- #

def diagnose_infeasibility() -> None:
    """
    Rebuild the restricted sub-network, attach a slack generator (can inject
    *and* absorb) at every bus, and re-solve. The relaxed problem is always
    feasible; any bus with non-zero slack pinpoints where the real network
    cannot balance:

        slack > 0  -> bus needs UNSERVED power injected  (supply shortfall /
                      load unreachable through the network)
        slack < 0  -> bus must DUMP power                 (forced over-supply,
                      e.g. a p_min_pu link/generator feeding it)
    """
    print("\n" + "=" * 60)
    print("Diagnosing infeasibility (slack-relaxed re-solve)")
    print("=" * 60)

    n = load_network()
    restrict_to_sub_network(n, TARGET_SUB_NETWORK)

    buses = list(n.buses.index)
    big = max(float(n.loads["p_set"].sum()) * 2.0, 1.0e4)

    # Inject-only slack (covers shortfalls): p in [0, big], cost +PENALTY.
    n.add("Generator", [f"_slack_up_{b}" for b in buses],
          bus=buses, p_nom=big, marginal_cost=SLACK_PENALTY,
          p_min_pu=0.0, p_max_pu=1.0)
    # Absorb-only slack (dumps excess): p in [-big, 0], cost +PENALTY*|p|
    # (marginal_cost negative * negative dispatch = positive penalty).
    n.add("Generator", [f"_slack_dn_{b}" for b in buses],
          bus=buses, p_nom=big, marginal_cost=-SLACK_PENALTY,
          p_min_pu=-1.0, p_max_pu=0.0)

    status, condition = n.optimize(solver_name="highs")
    print(f"\n  Relaxed solve status: {status} ({condition})")
    if status != "ok":
        print("  [ERROR] Even the slack-relaxed problem failed to solve. "
              "This points to a structural break (e.g. NaN reactance, "
              "malformed component) rather than an energy-balance issue. "
              "See the structural warnings above.")
        return

    disp = n.generators_t.p.iloc[0]
    up = disp[[g for g in disp.index if g.startswith("_slack_up_")]]
    dn = disp[[g for g in disp.index if g.startswith("_slack_dn_")]]
    up.index = [g[len("_slack_up_"):] for g in up.index]
    dn.index = [g[len("_slack_dn_"):] for g in dn.index]

    shortfall = up[up > 1e-3].sort_values(ascending=False)
    oversupply = (-dn[dn < -1e-3]).sort_values(ascending=False)

    print(f"\n  Total unserved (needs injection) : {shortfall.sum():>10,.1f} MW")
    print(f"  Total over-supply (needs dumping): {oversupply.sum():>10,.1f} MW")

    if not shortfall.empty:
        print(f"\n  Buses SHORT of power ({len(shortfall)}) — load cannot be "
              f"served here:")
        _print_bus_diag(n, shortfall)

    if not oversupply.empty:
        print(f"\n  Buses with EXCESS power ({len(oversupply)}) — forced "
              f"injection cannot be absorbed here:")
        _print_bus_diag(n, oversupply)

    print("\n  Interpretation:")
    print("    - A bus appearing in BOTH lists, or short+excess pairs joined")
    print("      by a low-rated line, usually means a transmission bottleneck.")
    print("    - Excess buses that are the bus1 of a p_min_pu link/generator")
    print("      indicate forced flow with nowhere to go (set p_min_pu=0 to")
    print("      make those flows dispatchable).")


def _print_bus_diag(n: pypsa.Network, series: pd.Series) -> None:
    """Print per-bus slack with local load/gen context."""
    loads_on = n.loads.groupby("bus")["p_set"].sum()
    gens_on  = n.generators[~n.generators.index.str.startswith("_slack_")] \
        .groupby("bus")["p_nom"].sum()
    print(f"    {'bus':<40} {'slack MW':>10} {'load':>8} {'gen-cap':>8}")
    for b, val in series.head(20).items():
        ld = float(loads_on.get(b, 0.0))
        gn = float(gens_on.get(b, 0.0))
        print(f"    {b[:40]:<40} {val:>10,.1f} {ld:>8.1f} {gn:>8.1f}")


# --------------------------------------------------------------------------- #
# Success report                                                              #
# --------------------------------------------------------------------------- #

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

    hard_ok = structural_checks(n)

    print("\n  Solving with HiGHS…")
    status, condition = n.optimize(solver_name="highs")
    print(f"  Solver status: {status} ({condition})")

    if status == "ok":
        report(n)
    else:
        # Infeasible / failed — localise the cause.
        diagnose_infeasibility()


if __name__ == "__main__":
    main()

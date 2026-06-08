"""
IEEE 4-Bus Topology Variations — PyPSA Demo Runner
====================================================
Runs all five topology modules in sequence and prints a comparative summary
table.  Each topology is built, solved with AC Newton-Raphson power flow, and
its key metrics are collected.

Usage:
    python run_all.py

Reference:
    doc/learning/ieee-4bus-topology-variations.md
"""

import logging
import pypsa

# Suppress PyPSA INFO logs for a cleaner run
logging.getLogger("pypsa").setLevel(logging.WARNING)

import topology_1_radial      as t1
import topology_2_ring        as t2
import topology_3_mesh        as t3
import topology_4_star        as t4
import topology_5_dual_source as t5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pf_and_collect(n: pypsa.Network) -> dict:
    """Run AC PF on *n* and return a summary dict."""
    result = n.pf()
    snap = n.snapshots[0]

    converged = bool(result["converged"].iloc[0, 0])
    n_iter = int(result["n_iter"].iloc[0, 0])

    total_load_p = n.loads_t.p.loc[snap].sum()

    # Total generation = sum of bus net injections on generator buses
    gen_buses = n.generators["bus"].unique()
    p_gen_total = sum(
        n.buses_t.p.loc[snap, b]
        for b in gen_buses
        if b in n.buses_t.p.columns
    )
    # Add PQ/PV generator outputs (non-slack generators store p in generators_t.p)
    for gen in n.generators.index:
        if n.generators.at[gen, "control"] != "Slack":
            p_val = n.generators_t.p.loc[snap, gen]
            if not (p_val != p_val):   # skip NaN
                pass  # already counted via bus injection for slack

    losses = p_gen_total - total_load_p

    v_min = n.buses_t.v_mag_pu.loc[snap].min()
    v_max = n.buses_t.v_mag_pu.loc[snap].max()

    n_buses = len(n.buses)
    n_lines = len(n.lines)
    n_trf = len(n.transformers)
    n_gen = len(n.generators)

    return {
        "name":      n.name,
        "converged": converged,
        "n_iter":    n_iter,
        "n_buses":   n_buses,
        "n_lines":   n_lines,
        "n_trf":     n_trf,
        "n_gen":     n_gen,
        "load_mw":   total_load_p,
        "gen_mw":    p_gen_total,
        "losses_mw": losses,
        "loss_pct":  100.0 * losses / total_load_p if total_load_p else 0.0,
        "v_min_pu":  v_min,
        "v_max_pu":  v_max,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  IEEE 4-Bus Topology Variations — PyPSA AC Power Flow Demo")
    print("=" * 70)

    modules = [
        (t1, t1.build),
        (t2, t2.build),
        (t3, t3.build),
        (t4, t4.build),
        (t5, t5.build),
    ]

    rows = []
    for mod, builder in modules:
        n = builder()
        mod.print_results(n)
        n2 = builder()          # fresh network for metrics collection
        rows.append(_pf_and_collect(n2))

    # ── Summary Table ───────────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("  COMPARATIVE SUMMARY")
    print("=" * 70)

    labels = [
        "1. Radial",
        "2. Ring",
        "3. Mesh",
        "4. Star/Hub",
        "5. Dual-Source",
    ]

    header = (f"  {'Topology':<17} {'Conv':>5} {'Buses':>5} "
              f"{'Lines':>5} {'Trf':>5} {'Gens':>5} "
              f"{'Load MW':>8} {'Loss MW':>9} {'Loss %':>7} "
              f"{'Vmin pu':>8} {'Vmax pu':>8}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for lbl, r in zip(labels, rows):
        ok = "OK" if r["converged"] else "FAIL"
        print(
            f"  {lbl:<17} {ok:>5} {r['n_buses']:>5} "
            f"{r['n_lines']:>5} {r['n_trf']:>5} {r['n_gen']:>5} "
            f"{r['load_mw']:>8.2f} {r['losses_mw']:>9.4f} {r['loss_pct']:>6.2f}% "
            f"{r['v_min_pu']:>8.4f} {r['v_max_pu']:>8.4f}"
        )

    print("\n  All networks solved with PyPSA Newton-Raphson AC power flow.")
    print("  Reference: doc/learning/ieee-4bus-topology-variations.md")


if __name__ == "__main__":
    main()

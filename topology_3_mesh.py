"""
Topology 3: Mesh / Interconnected Network
==========================================
Multiple paths between every bus — the highest-reliability topology, used in
critical transmission grids and data-centre-grade infrastructure.

Two HV generator buses (1, 2) are fully interconnected.  Each HV bus connects
to both LV load buses (3, 4) through step-down transformers.  The LV buses are
also tied to each other.

Network Layout:

       [G1]                         [G2]
       (~)                           (~)
        │                             │
       [1]═══════ Line 1-2 ══════════[2]    ← 12.47 kV HV ring
        ║ ╲                         ╱ ║
        ║  Trf 1-3            Trf 2-4 ║    ← cross-voltage transformers
     Trf 1-4 ╲                  ╱ Trf 2-3
        ║      ╲              ╱      ║
       [4]═════════ Line 3-4 ════════[3]   ← 4.16 kV LV ring
        ▼                             ▼
      Load A                        Load B
      4.16 kV                       4.16 kV

Key characteristics:
  - Dual generation sources with full interconnection (N-1 secure)
  - Power flows redistribute automatically on any contingency
  - Complex protection coordination (distance / line differential)
  - Typical of transmission backbones and critical infrastructure
"""

import pypsa


def build(name: str = "Topology 3 — Mesh / Interconnected") -> pypsa.Network:
    """Construct and return the fully-meshed network."""
    n = pypsa.Network(name=name)

    # ── Buses ──────────────────────────────────────────────────────────────
    n.add("Bus", "Bus 1", v_nom=12.47)   # HV, G1 slack
    n.add("Bus", "Bus 2", v_nom=12.47)   # HV, G2 PV
    n.add("Bus", "Bus 3", v_nom=4.16)    # LV, Load B
    n.add("Bus", "Bus 4", v_nom=4.16)    # LV, Load A

    # ── Generators ─────────────────────────────────────────────────────────
    # G1 — cheaper source, designated slack
    n.add("Generator", "G1",
          bus="Bus 1",
          control="Slack",
          p_nom=10.0,
          marginal_cost=40.0,
          v_set=1.02)

    # G2 — second source, PV (voltage-controlled)
    n.add("Generator", "G2",
          bus="Bus 2",
          control="PV",
          p_nom=8.0,
          p_set=4.0,       # scheduled MW output
          marginal_cost=60.0,
          v_set=1.01)

    # ── HV Line ─────────────────────────────────────────────────────────────
    # Transmission-grade 12.47 kV inter-generator tie
    n.add("Line", "Line 1-2",
          bus0="Bus 1", bus1="Bus 2",
          r=0.20, x=0.45,
          s_nom=12.0)

    # ── LV Line ─────────────────────────────────────────────────────────────
    # 4.16 kV bus-tie between load buses
    n.add("Line", "Line 3-4",
          bus0="Bus 3", bus1="Bus 4",
          r=0.04, x=0.07,
          s_nom=8.0)

    # ── Cross-voltage Transformers (HV ↔ LV) ───────────────────────────────
    # Each HV bus feeds both LV buses — giving four transformer paths
    trf_params = dict(x=0.05, r=0.01, s_nom=6.0)

    n.add("Transformer", "Trf 1-3", bus0="Bus 1", bus1="Bus 3", **trf_params)
    n.add("Transformer", "Trf 1-4", bus0="Bus 1", bus1="Bus 4", **trf_params)
    n.add("Transformer", "Trf 2-3", bus0="Bus 2", bus1="Bus 3", **trf_params)
    n.add("Transformer", "Trf 2-4", bus0="Bus 2", bus1="Bus 4", **trf_params)

    # ── Loads ───────────────────────────────────────────────────────────────
    n.add("Load", "Load A",
          bus="Bus 4",
          p_set=4.0,
          q_set=1.2)

    n.add("Load", "Load B",
          bus="Bus 3",
          p_set=5.0,
          q_set=1.5)

    return n


def print_results(n: pypsa.Network) -> None:
    """Run AC power flow and print key results."""
    result = n.pf()
    snap = n.snapshots[0]

    converged = bool(result["converged"].iloc[0, 0])
    iters = int(result["n_iter"].iloc[0, 0])
    print(f"  AC power flow: {'CONVERGED' if converged else 'DID NOT CONVERGE'} "
          f"(iterations: {iters})")

    print("\n  Bus Voltages:")
    print(f"  {'Bus':<10} {'v_nom (kV)':>10} {'|V| (pu)':>10} {'∠ (deg)':>10}")
    print("  " + "-" * 44)
    for bus in n.buses.index:
        v_mag = n.buses_t.v_mag_pu.loc[snap, bus]
        v_ang = n.buses_t.v_ang.loc[snap, bus]
        v_kv = n.buses.at[bus, "v_nom"]
        print(f"  {bus:<10} {v_kv:>10.2f} {v_mag:>10.4f} {v_ang * 57.296:>10.4f}")

    print("\n  Branch Flows  (sending-end):")
    print(f"  {'Branch':<14} {'P (MW)':>9} {'Q (MVAr)':>10} {'|S| (MVA)':>10}")
    print("  " + "-" * 46)
    for line in n.lines.index:
        p = n.lines_t.p0.loc[snap, line]
        q = n.lines_t.q0.loc[snap, line]
        print(f"  {line:<14} {p:>9.3f} {q:>10.3f} {(p**2+q**2)**0.5:>10.3f}")
    for trf in n.transformers.index:
        p = n.transformers_t.p0.loc[snap, trf]
        q = n.transformers_t.q0.loc[snap, trf]
        print(f"  {trf:<14} {p:>9.3f} {q:>10.3f} {(p**2+q**2)**0.5:>10.3f}")

    slack_bus = n.generators.loc["G1", "bus"]
    p_g1 = n.buses_t.p.loc[snap, slack_bus]
    q_g1 = n.generators_t.q.loc[snap, "G1"]
    p_g2 = n.generators_t.p.loc[snap, "G2"]
    q_g2 = n.generators_t.q.loc[snap, "G2"]
    total_load_p = n.loads_t.p.loc[snap].sum()
    total_load_q = n.loads_t.q.loc[snap].sum()
    losses = (p_g1 + p_g2) - total_load_p

    print("\n  Generation & Load Summary:")
    print(f"  {'Generator G1 (slack)':<24}  P = {p_g1:.3f} MW   Q = {q_g1:.3f} MVAr")
    print(f"  {'Generator G2 (PV)':<24}  P = {p_g2:.3f} MW   Q = {q_g2:.3f} MVAr")
    print(f"  {'Total Load':<24}  P = {total_load_p:.3f} MW   Q = {total_load_q:.3f} MVAr")
    print(f"  {'Total Losses':<24}  P = {losses:.4f} MW")
    print("\n  Note: four transformer paths give automatic power-flow redistribution.")


def main() -> None:
    n = build()
    print(f"\n{'='*60}")
    print(f"  {n.name}")
    print(f"{'='*60}")
    print_results(n)


if __name__ == "__main__":
    main()

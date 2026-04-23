"""
Topology 1: Radial (Classic IEEE 4-Bus)
========================================
A straight radial feed from generation through a step-down transformer to load.
Single source, single path — the canonical reference topology.

Network Layout:
                                    Trf
  [G]      Line 1-2       2-3         Line 3-4       [Load]
  (~)──[Bus1]════════[Bus2]──────[Bus3]════════[Bus4]──▶
        12.47 kV      12.47 kV   4.16 kV        4.16 kV

Key characteristics:
  - Single source, single path to load
  - Lowest cost, simplest protection
  - A fault anywhere de-energises everything downstream
  - Typical of rural distribution feeders
"""

import pypsa


def build(name: str = "Topology 1 — Radial (Classic IEEE 4-Bus)") -> pypsa.Network:
    """Construct and return the radial network."""
    n = pypsa.Network(name=name)

    # ── Buses ──────────────────────────────────────────────────────────────
    n.add("Bus", "Bus 1", v_nom=12.47)   # HV source bus
    n.add("Bus", "Bus 2", v_nom=12.47)   # HV transformer primary
    n.add("Bus", "Bus 3", v_nom=4.16)    # LV transformer secondary
    n.add("Bus", "Bus 4", v_nom=4.16)    # LV load bus

    # ── Generator (single slack source) ────────────────────────────────────
    n.add("Generator", "G1",
          bus="Bus 1",
          control="Slack",
          p_nom=10.0,          # MW nameplate capacity
          marginal_cost=50.0,  # $/MWh
          v_set=1.02)          # voltage setpoint (pu)

    # ── Lines ───────────────────────────────────────────────────────────────
    # 12.47 kV overhead distribution line (~2 km)
    # Typical ACSR: r ≈ 0.2 Ω/km, x ≈ 0.35 Ω/km
    n.add("Line", "Line 1-2",
          bus0="Bus 1", bus1="Bus 2",
          r=0.40, x=0.70,
          s_nom=10.0)   # MVA thermal rating

    # 4.16 kV underground cable (~0.5 km)
    n.add("Line", "Line 3-4",
          bus0="Bus 3", bus1="Bus 4",
          r=0.05, x=0.08,
          s_nom=8.0)

    # ── Transformer ─────────────────────────────────────────────────────────
    # 12.47 / 4.16 kV, 8 MVA distribution transformer
    n.add("Transformer", "Trf 2-3",
          bus0="Bus 2", bus1="Bus 3",
          x=0.05,   # leakage reactance (pu on transformer MVA base)
          r=0.01,
          s_nom=8.0)

    # ── Load ────────────────────────────────────────────────────────────────
    n.add("Load", "Load",
          bus="Bus 4",
          p_set=5.0,    # MW active load
          q_set=1.5)    # MVAr reactive load (pf ≈ 0.96 lag)

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

    # Slack generator output = net bus injection at slack bus
    slack_bus = n.generators.loc["G1", "bus"]
    p_gen = n.buses_t.p.loc[snap, slack_bus]
    q_gen = n.generators_t.q.loc[snap, "G1"]
    total_load_p = n.loads_t.p.loc[snap].sum()
    total_load_q = n.loads_t.q.loc[snap].sum()
    losses = p_gen - total_load_p

    print("\n  Generation & Load Summary:")
    print(f"  {'Generator G1':<20}  P = {p_gen:.3f} MW   Q = {q_gen:.3f} MVAr")
    print(f"  {'Total Load':<20}  P = {total_load_p:.3f} MW   Q = {total_load_q:.3f} MVAr")
    print(f"  {'Total Losses':<20}  P = {losses:.4f} MW")


def main() -> None:
    n = build()
    print(f"\n{'='*60}")
    print(f"  {n.name}")
    print(f"{'='*60}")
    print_results(n)


if __name__ == "__main__":
    main()

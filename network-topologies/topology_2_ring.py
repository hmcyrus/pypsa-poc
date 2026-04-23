"""
Topology 2: Ring / Loop Network
================================
A closed-loop configuration — if one segment fails, power re-routes around
the ring.  All four main buses operate at 12.47 kV; Bus 4 also feeds a
step-down transformer to a 4.16 kV load bus.

Network Layout:

                    Line 1-2
       [G]    ┌════════════════┐
       (~)───[1]              [2]
        │     ║                ║
       ═╧═    ║ Line 4-1  Line 2-3
              ║                ║
             [4]════════════[3]──▶ Load B (12.47 kV)
              │    Line 3-4   │
             Trf
              │
            [4_lv]
              ▼
           Load A (4.16 kV)

Key characteristics:
  - Two independent paths to every load (N-1 secure against any single line)
  - Requires directional / differential protection
  - Common in urban distribution and industrial plants
  - Higher reliability than radial at modest extra cost
"""

import pypsa


def build(name: str = "Topology 2 — Ring / Loop Network") -> pypsa.Network:
    """Construct and return the ring network."""
    n = pypsa.Network(name=name)

    # ── Buses ──────────────────────────────────────────────────────────────
    # All four ring buses at HV; one dedicated LV bus for Load A
    n.add("Bus", "Bus 1",    v_nom=12.47)   # Generator / slack bus
    n.add("Bus", "Bus 2",    v_nom=12.47)   # Ring bus (top-right)
    n.add("Bus", "Bus 3",    v_nom=12.47)   # Ring bus (bottom-right) — Load B
    n.add("Bus", "Bus 4",    v_nom=12.47)   # Ring bus (bottom-left)
    n.add("Bus", "Bus 4_lv", v_nom=4.16)    # LV bus fed from Bus 4 via Trf

    # ── Generator ──────────────────────────────────────────────────────────
    n.add("Generator", "G1",
          bus="Bus 1",
          control="Slack",
          p_nom=12.0,
          marginal_cost=50.0,
          v_set=1.02)

    # ── Ring Lines (equal impedance to allow symmetric flow split) ──────────
    # Each segment: ~1.5 km 12.47 kV overhead line
    line_params = dict(r=0.30, x=0.55, s_nom=10.0)

    n.add("Line", "Line 1-2", bus0="Bus 1", bus1="Bus 2", **line_params)
    n.add("Line", "Line 2-3", bus0="Bus 2", bus1="Bus 3", **line_params)
    n.add("Line", "Line 3-4", bus0="Bus 3", bus1="Bus 4", **line_params)
    n.add("Line", "Line 4-1", bus0="Bus 4", bus1="Bus 1", **line_params)

    # ── Step-down Transformer (Bus 4 → 4.16 kV) ────────────────────────────
    n.add("Transformer", "Trf 4-4lv",
          bus0="Bus 4", bus1="Bus 4_lv",
          x=0.05, r=0.01,
          s_nom=8.0)

    # ── Loads ───────────────────────────────────────────────────────────────
    # Load B — directly on the 12.47 kV ring at Bus 3
    n.add("Load", "Load B",
          bus="Bus 3",
          p_set=3.0,
          q_set=0.9)

    # Load A — on the 4.16 kV bus fed from Bus 4
    n.add("Load", "Load A",
          bus="Bus 4_lv",
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
    print(f"  {'Bus':<12} {'v_nom (kV)':>10} {'|V| (pu)':>10} {'∠ (deg)':>10}")
    print("  " + "-" * 46)
    for bus in n.buses.index:
        v_mag = n.buses_t.v_mag_pu.loc[snap, bus]
        v_ang = n.buses_t.v_ang.loc[snap, bus]
        v_kv = n.buses.at[bus, "v_nom"]
        print(f"  {bus:<12} {v_kv:>10.2f} {v_mag:>10.4f} {v_ang * 57.296:>10.4f}")

    print("\n  Branch Flows  (sending-end):")
    print(f"  {'Branch':<16} {'P (MW)':>9} {'Q (MVAr)':>10} {'|S| (MVA)':>10}")
    print("  " + "-" * 48)
    for line in n.lines.index:
        p = n.lines_t.p0.loc[snap, line]
        q = n.lines_t.q0.loc[snap, line]
        sign = "→" if p >= 0 else "←"
        print(f"  {line:<16} {p:>9.3f} {q:>10.3f} {(p**2+q**2)**0.5:>10.3f}  {sign}")
    for trf in n.transformers.index:
        p = n.transformers_t.p0.loc[snap, trf]
        q = n.transformers_t.q0.loc[snap, trf]
        print(f"  {trf:<16} {p:>9.3f} {q:>10.3f} {(p**2+q**2)**0.5:>10.3f}")

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
    print("\n  Note: sign '←' on a ring line indicates reverse flow (ring effect).")


def main() -> None:
    n = build()
    print(f"\n{'='*60}")
    print(f"  {n.name}")
    print(f"{'='*60}")
    print_results(n)


if __name__ == "__main__":
    main()

"""
Topology 5: Dual-Source Tie (Hybrid Grid + Solar)
===================================================
Two independent sources — a utility grid feed (Grid/PDB) and an on-site PV
array — connected through a common tie bus.  Typical of humanitarian microgrid
projects where a weak national utility is augmented by on-site renewables.

Network Layout:

   [Grid/PDB]                           [PV Array]
      (~)                                   (☀)
       │                                     │
      ═╧═                                   ═╧═
       │                                     │
     [Bus 1]                              [Bus 4]
       ║  12.47 kV                   4.16 kV ║
    Line 1-2                          Line 4-3
       ║                                     ║
     [Bus 2]──(Trf 12.47→4.16 kV)──[Bus 3]◀══╝
                                      │
                              ┌───────┴───────┐
                              ▼               ▼
                          Load (Critical)  Load (Non-critical)
                           4.16 kV           4.16 kV

Key characteristics:
  - Two uncorrelated sources increase availability
  - PV may export to grid at low-load hours (reverse power flow on Line 1-2)
  - Requires anti-islanding protection on the PV inverter
  - Voltage regulation must account for variable PV output
  - Representative of humanitarian microgrid projects
"""

import pypsa


def build(name: str = "Topology 5 — Dual-Source Tie (Grid + Solar)") -> pypsa.Network:
    """Construct and return the dual-source tie network."""
    n = pypsa.Network(name=name)

    # ── Buses ──────────────────────────────────────────────────────────────
    n.add("Bus", "Bus 1", v_nom=12.47)   # Grid/PDB point of connection (HV)
    n.add("Bus", "Bus 2", v_nom=12.47)   # Transformer primary (HV)
    n.add("Bus", "Bus 3", v_nom=4.16)    # Tie bus / transformer secondary (LV)
    n.add("Bus", "Bus 4", v_nom=4.16)    # PV inverter output bus (LV)

    # ── Sources ─────────────────────────────────────────────────────────────
    # Grid / PDB — acts as slack (voltage and angle reference)
    n.add("Generator", "Grid",
          bus="Bus 1",
          control="Slack",
          p_nom=20.0,          # large upstream utility capacity
          marginal_cost=80.0,  # $/MWh (utility import cost)
          v_set=1.00)

    # PV Array — voltage-controlled, limited to inverter capacity
    n.add("Generator", "PV",
          bus="Bus 4",
          control="PV",
          p_nom=5.0,
          p_set=3.0,           # MW output at current irradiance
          marginal_cost=0.0,   # zero marginal cost (fuel-free)
          v_set=1.01)

    # ── HV Line: Grid → Transformer primary ────────────────────────────────
    n.add("Line", "Line 1-2",
          bus0="Bus 1", bus1="Bus 2",
          r=0.35, x=0.65,
          s_nom=12.0)

    # ── Step-down Transformer: HV → Tie Bus ────────────────────────────────
    # 12.47 / 4.16 kV, 8 MVA
    n.add("Transformer", "Trf 2-3",
          bus0="Bus 2", bus1="Bus 3",
          x=0.05, r=0.01,
          s_nom=8.0)

    # ── LV Line: PV Bus → Tie Bus ───────────────────────────────────────────
    # Short 4.16 kV cable from PV inverter to tie bus
    n.add("Line", "Line 4-3",
          bus0="Bus 4", bus1="Bus 3",
          r=0.03, x=0.06,
          s_nom=6.0)

    # ── Loads ───────────────────────────────────────────────────────────────
    # Critical load — priority supply (e.g. hospital, comms)
    n.add("Load", "Load Critical",
          bus="Bus 3",
          p_set=4.0,
          q_set=1.2)

    # Non-critical load — sheddable in emergencies
    n.add("Load", "Load Non-critical",
          bus="Bus 3",
          p_set=2.0,
          q_set=0.6)

    return n


def print_results(n: pypsa.Network) -> None:
    """Run AC power flow and print key results, highlighting reverse-flow cases."""
    result = n.pf()
    snap = n.snapshots[0]

    converged = bool(result["converged"].iloc[0, 0])
    iters = int(result["n_iter"].iloc[0, 0])
    print(f"  AC power flow: {'CONVERGED' if converged else 'DID NOT CONVERGE'} "
          f"(iterations: {iters})")

    print("\n  Bus Voltages:")
    print(f"  {'Bus':<22} {'v_nom (kV)':>10} {'|V| (pu)':>10} {'∠ (deg)':>10}")
    print("  " + "-" * 56)
    labels = {
        "Bus 1": "Bus 1  (Grid PCC)",
        "Bus 2": "Bus 2  (Trf primary)",
        "Bus 3": "Bus 3  (Tie bus)",
        "Bus 4": "Bus 4  (PV inverter)",
    }
    for bus in n.buses.index:
        v_mag = n.buses_t.v_mag_pu.loc[snap, bus]
        v_ang = n.buses_t.v_ang.loc[snap, bus]
        v_kv = n.buses.at[bus, "v_nom"]
        lbl = labels.get(bus, bus)
        print(f"  {lbl:<22} {v_kv:>10.2f} {v_mag:>10.4f} {v_ang * 57.296:>10.4f}")

    print("\n  Branch Flows:")
    print(f"  {'Branch':<14} {'P (MW)':>9} {'Q (MVAr)':>10} {'|S| (MVA)':>10}  Direction")
    print("  " + "-" * 58)

    for line in n.lines.index:
        p = n.lines_t.p0.loc[snap, line]
        q = n.lines_t.q0.loc[snap, line]
        if line == "Line 1-2":
            direction = "Grid → Trf" if p > 0 else "REVERSE (export to grid)"
        else:
            direction = "PV → Tie bus" if p > 0 else "Tie bus → PV (charging)"
        print(f"  {line:<14} {p:>9.3f} {q:>10.3f} {(p**2+q**2)**0.5:>10.3f}  {direction}")

    for trf in n.transformers.index:
        p = n.transformers_t.p0.loc[snap, trf]
        q = n.transformers_t.q0.loc[snap, trf]
        print(f"  {trf:<14} {p:>9.3f} {q:>10.3f} {(p**2+q**2)**0.5:>10.3f}  HV → Tie bus")

    grid_bus = n.generators.loc["Grid", "bus"]
    p_grid = n.buses_t.p.loc[snap, grid_bus]
    q_grid = n.generators_t.q.loc[snap, "Grid"]
    p_pv = n.generators_t.p.loc[snap, "PV"]
    q_pv = n.generators_t.q.loc[snap, "PV"]
    total_load_p = n.loads_t.p.loc[snap].sum()
    total_load_q = n.loads_t.q.loc[snap].sum()
    losses = (p_grid + p_pv) - total_load_p

    print("\n  Generation & Load Summary:")
    print(f"  {'Grid (slack)':<24}  P = {p_grid:>7.3f} MW   Q = {q_grid:>7.3f} MVAr")
    print(f"  {'PV Array':<24}  P = {p_pv:>7.3f} MW   Q = {q_pv:>7.3f} MVAr")
    print(f"  {'Total Load':<24}  P = {total_load_p:>7.3f} MW   Q = {total_load_q:>7.3f} MVAr")
    print(f"  {'Total Losses':<24}  P = {losses:>7.4f} MW")

    pv_share = 100.0 * p_pv / total_load_p if total_load_p > 0 else 0.0
    print(f"\n  PV covers {pv_share:.1f}% of total load.")
    if p_grid < 0:
        print("  Grid flow is NEGATIVE — PV is exporting surplus to the utility.")
    elif p_grid < total_load_p * 0.3:
        print("  PV is providing the majority of local demand.")
    else:
        print("  Grid supplements PV to meet the remaining load.")


def main() -> None:
    n = build()
    print(f"\n{'='*60}")
    print(f"  {n.name}")
    print(f"{'='*60}")
    print_results(n)


if __name__ == "__main__":
    main()

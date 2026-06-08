"""
Topology 4: Star / Radial Hub
===============================
A central bus distributes power to multiple independent spokes.  Common for
substation-fed distribution where one primary bus serves several feeders at
different voltage levels.

Network Layout:

                      [G]
                      (~)
                       │
                      ═╧═
                       │
                    [Bus 1]  ← Central Hub  12.47 kV
                   ╱   │   ╲
         Line 1-2 ╱  Line   ╲ Line 1-4
                 ╱    1-3    ╲
                ╱      │      ╲
             (Trf)  (Trf)   (Trf)
            12.47   12.47  12.47
             /4.16  /4.16  /0.48
              │       │       │
           [Bus 2] [Bus 3] [Bus 4]
              ▼       ▼       ▼
           Load A   Load B  Load C
           4.16 kV 4.16 kV  480 V

Key characteristics:
  - Single point of generation, multiple independent LV outlets
  - Fault on one spoke does not affect other spokes
  - Common in campus / industrial / humanitarian microgrid projects
  - Hub (Bus 1) is the single point of failure if unprotected
"""

import pypsa


def build(name: str = "Topology 4 — Star / Radial Hub") -> pypsa.Network:
    """Construct and return the star network."""
    n = pypsa.Network(name=name)

    # ── Buses ──────────────────────────────────────────────────────────────
    n.add("Bus", "Bus 1", v_nom=12.47)    # HV hub
    n.add("Bus", "Bus 2", v_nom=4.16)     # LV spoke A
    n.add("Bus", "Bus 3", v_nom=4.16)     # LV spoke B
    n.add("Bus", "Bus 4", v_nom=0.48)     # LV spoke C (480 V)

    # ── Generator (single source at hub) ────────────────────────────────────
    n.add("Generator", "G1",
          bus="Bus 1",
          control="Slack",
          p_nom=15.0,
          marginal_cost=50.0,
          v_set=1.02)

    # ── Spoke Transformers (hub → each spoke) ────────────────────────────────
    # Spoke A: 12.47 / 4.16 kV, 6 MVA
    n.add("Transformer", "Trf 1-2",
          bus0="Bus 1", bus1="Bus 2",
          x=0.05, r=0.01,
          s_nom=6.0)

    # Spoke B: 12.47 / 4.16 kV, 5 MVA
    n.add("Transformer", "Trf 1-3",
          bus0="Bus 1", bus1="Bus 3",
          x=0.05, r=0.01,
          s_nom=5.0)

    # Spoke C: 12.47 / 0.48 kV, 3 MVA
    n.add("Transformer", "Trf 1-4",
          bus0="Bus 1", bus1="Bus 4",
          x=0.06, r=0.015,
          s_nom=3.0)

    # ── Loads (one per spoke, independent) ───────────────────────────────────
    n.add("Load", "Load A",
          bus="Bus 2",
          p_set=4.0,
          q_set=1.2)    # pf ≈ 0.96 lag

    n.add("Load", "Load B",
          bus="Bus 3",
          p_set=3.0,
          q_set=0.9)

    n.add("Load", "Load C",
          bus="Bus 4",
          p_set=1.5,
          q_set=0.5)    # 480 V load (e.g. motor equipment)

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
        print(f"  {bus:<10} {v_kv:>10.3f} {v_mag:>10.4f} {v_ang * 57.296:>10.4f}")

    print("\n  Spoke Transformer Flows (hub → spoke):")
    print(f"  {'Transformer':<14} {'P (MW)':>9} {'Q (MVAr)':>10} {'|S| (MVA)':>10} {'Load %':>8}")
    print("  " + "-" * 54)
    for trf in n.transformers.index:
        p = n.transformers_t.p0.loc[snap, trf]
        q = n.transformers_t.q0.loc[snap, trf]
        s = (p**2 + q**2) ** 0.5
        s_nom = n.transformers.at[trf, "s_nom"]
        loading = 100.0 * s / s_nom
        print(f"  {trf:<14} {p:>9.3f} {q:>10.3f} {s:>10.3f} {loading:>7.1f}%")

    slack_bus = n.generators.loc["G1", "bus"]
    p_gen = n.buses_t.p.loc[snap, slack_bus]
    q_gen = n.generators_t.q.loc[snap, "G1"]
    total_load_p = n.loads_t.p.loc[snap].sum()
    total_load_q = n.loads_t.q.loc[snap].sum()
    losses = p_gen - total_load_p

    print("\n  Generation & Load Summary:")
    print(f"  {'Generator G1 (hub)':<22}  P = {p_gen:.3f} MW   Q = {q_gen:.3f} MVAr")
    print(f"  {'Total Load (all spokes)':<22}  P = {total_load_p:.3f} MW   Q = {total_load_q:.3f} MVAr")
    print(f"  {'Total Losses':<22}  P = {losses:.4f} MW")

    print("\n  Spoke independence: no lines connect Bus 2, Bus 3, or Bus 4.")
    print("  A fault on one spoke cannot propagate to another.")


def main() -> None:
    n = build()
    print(f"\n{'='*60}")
    print(f"  {n.name}")
    print(f"{'='*60}")
    print_results(n)


if __name__ == "__main__":
    main()

# Power System Concepts to Cover

## 1. Fundamentals

- **Per-unit (pu) system** — how voltages, currents, and powers are normalised to base
  values (`kVA_base`, `kV_baseL`, `I_baseL`)
- **Phasors** — complex representation of AC voltages and currents (magnitude + angle)
- **Apparent, active, and reactive power** — S, P, Q and their relationships
- **Power factor**

## 2. Network Representation

- **Bus types** — PQ (load), PV (generator), and swing/slack bus
- **Admittance matrix (Y-bus)** — how network impedances are assembled into a matrix;
  what G and B sub-matrices mean
- **3-phase unbalanced systems** — why phases A, B, C are modelled separately (not just
  as a single-phase equivalent)
- **4-wire systems** — the role of the neutral conductor and why it matters for
  unbalanced loads

## 3. Power Flow Analysis

- **Newton-Raphson load flow** — iterative solver for bus voltages; what the mismatch
  equations represent; convergence criteria
- **Current-mismatch formulation** — the specific variant used here (vs. power-mismatch),
  why it suits unbalanced 3-phase networks
- **Line flow calculations** — how sending-end/receiving-end power (S_from, S_to) and
  current (I_from) are derived from voltages

## 4. Load Modelling

- **ZIP load model** — decomposition of load into constant-**Z** impedance,
  constant-**I** current, and constant-**P** power components; what `p_P`, `p_I`, `p_Z`
  coefficients mean

## 5. Distributed Energy Resources (DER)

- **PV generation modelling** — treating solar output as a negative load (P injection)
  on a bus
- **PV ramp rate** — rate of change of PV output; why it stresses the grid
- **PV penetration level (PPL)** — ratio of peak PV output to peak load demand

## 6. Battery Energy Storage Systems (BESS)

- **State of Charge (SoC)** — energy level as a fraction of capacity; DoD (depth of
  discharge)
- **Kinetic battery model (KBM)** — the E0/K/A/B parametric model used for terminal
  voltage as a function of SoC and current
- **Coulomb counting** — how SoC is updated each time step from current and efficiency
- **Charge/discharge efficiency** — coulomb efficiency and converter efficiency losses
- **C-rate** — current relative to battery capacity; affects allowable charge/discharge
  rates

## 7. Control Concepts

- **SoC reference tracking** — following a target SoC trajectory rather than a fixed
  setpoint
- **Ramp-rate limiting** — constraining how fast battery power output can change per
  time step
- **Moving average smoothing** — used to derive a smoothed PV signal as a dispatch
  target
- **Off-peak charging** — scheduling grid charging during low-demand periods

## 8. Distribution System Context

- **Voltage rise problem** — why high PV penetration on a feeder can push bus voltages
  above limits
- **Feeder / radial network** — single-source distribution topology (relevant to the
  Gatton test case)
- **Line losses** — resistive losses per phase and neutral; why neutral losses matter in
  4-wire systems

## 9. Battery Lifetime Analysis

- **Rainflow cycle counting** — algorithm for extracting charge/discharge cycles from an
  irregular SoC time-series
- **Palmgren-Miner damage rule** — linear cumulative damage index D; how cycle amplitude
  maps to fatigue damage
- **Depth of discharge vs. cycle life** — why limiting DoD extends battery lifespan

## 10. Simulation Structure

- **Time-series simulation** — stepping through 1440 minutes (or seconds) of a day;
  what "quasi-static" simulation means
- **Convergence and numerical stability** — what it means when NR fails to converge;
  how initial conditions affect it

---

## Order of Learning

Work through these in sequence. Each stage builds the foundation the next one needs.

### Stage 1 — AC Circuit Basics
1. Phasors (complex voltage and current)
2. Apparent, active, and reactive power (S, P, Q)
3. Power factor
4. Per-unit system

> Goal: be comfortable expressing any voltage, current, or power as a complex
> number in pu. Everything in the codebase is in pu.

### Stage 2 — Network Modelling
5. Bus types (PQ, PV, swing)
6. Admittance matrix (Y-bus) — construction from line impedances
7. 3-phase unbalanced systems — why phases are separate
8. 4-wire systems — neutral wire and zero-sequence currents

> Goal: understand what `bb_pv_cluster1.m` and `ymat_3ph3_4w.m` are building.

### Stage 3 — Power Flow
9. Newton-Raphson load flow — the iterative solve loop
10. Current-mismatch formulation — how `curr_mm_3p3_4w.m` computes ΔI
11. Line flow calculations — S_from, I_from, losses from solved voltages

> Goal: be able to trace a single iteration of `nrci3ph4w.m` by hand.

### Stage 4 — Load and Generation Modelling
12. ZIP load model (p_P, p_I, p_Z coefficients)
13. PV generation as a bus injection
14. PV ramp rate and penetration level (PPL)
15. Feeder / radial network topology
16. Voltage rise problem from high PV penetration

> Goal: understand why `demand_curve.m`, `pv_curve.m`, and the ZIP indices
> exist, and what happens to bus voltages when PV is high.

### Stage 5 — Battery Fundamentals
17. State of Charge and Depth of Discharge
18. C-rate and current limits
19. Coulomb counting (SoC update per time step)
20. Charge/discharge efficiency (coulomb + converter)
21. Kinetic battery model — E0, K, A, B parameters; terminal voltage equation

> Goal: understand the BATTERY entity fields and how `charge_control.m` and
> `discharge_control.m` update SoC and Vbatt each step.

### Stage 6 — Control Strategies
22. SoC reference tracking — parabolic trajectory from `SoC_ref_gen.m`
23. Ramp-rate limiting — omega_Chg / omega_Dsch parameters
24. Moving average smoothing — how `smoothing_control.m` targets PVP_MA
25. Off-peak charging — `night_charge_control.m` logic

> Goal: understand why each control script exists and what problem it solves.

### Stage 7 — Battery Lifetime
26. Rainflow cycle counting — extracting cycles from an irregular SoC signal
27. Palmgren-Miner damage rule — cumulative damage index D
28. DoD vs. cycle life trade-off

> Goal: understand `rainflow_bins.m` output and what the damage index D means
> for battery replacement decisions.

### Stage 8 — Simulation as a Whole
29. Quasi-static time-series simulation — one NR solve per time step
30. Convergence and numerical stability — what breaks the NR loop
31. How all scripts connect inside the daily time-step loop in
    `daily_sim_combined_CD.m`

> Goal: read `daily_sim_combined_CD.m` top to bottom and follow every call
> without confusion.

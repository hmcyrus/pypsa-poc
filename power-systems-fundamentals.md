# Power Systems & Energy Modeling — Fundamentals for Software Engineers

A structured reference for a seasoned SWE / solution architect entering the power system planning and energy economics domain. Covers grounding physics through to the concepts you'll encounter daily in simulation tools (PyPSA, MATPOWER, OpenDSS, pandapower, etc.).

---

## 1. Grounding: Electrical Quantities

### 1.1 The Big Four

| Quantity       | Symbol | Unit      | Intuition                                      |
|----------------|--------|-----------|-------------------------------------------------|
| Voltage        | V      | Volt (V)  | "Pressure" pushing charge through a wire        |
| Current        | I      | Ampere (A)| "Flow rate" of charge                           |
| Resistance     | R      | Ohm (Ω)  | "Friction" opposing flow                        |
| Power          | P      | Watt (W)  | Rate of energy transfer                         |

**Ohm's Law** — the one equation everything else builds on:

```
V = I × R
```

**Power in DC circuits:**

```
P = V × I = I²R = V²/R
```

**Energy** is power integrated over time. The utility world measures it in kilowatt-hours (kWh): a 100 W bulb burning for 10 hours = 1 kWh.

### 1.2 Series vs. Parallel — Why It Matters for Grids

```
SERIES (same current flows through all)     PARALLEL (same voltage across all)

  ──[R1]──[R2]──[R3]──                       ┬──[R1]──┬
                                              ├──[R2]──┤
  R_total = R1 + R2 + R3                      ├──[R3]──┤
                                              ┴────────┴

                                              1/R_total = 1/R1 + 1/R2 + 1/R3
```

In a real grid, feeders and branches are combinations of both. Loads (homes, factories) are mostly in parallel across a distribution bus, so losing one doesn't kill the rest.

### 1.3 Kirchhoff's Laws

These are the constraint equations that every power flow solver enforces:

- **KCL (Current Law):** At any node/bus, the sum of currents in = sum of currents out. (Conservation of charge.)
- **KVL (Voltage Law):** Around any closed loop, the sum of voltage rises and drops = 0. (Conservation of energy.)

```
       I1 →         I2 →
  ──────●──────────────●──────
        │  (Bus A)     │  (Bus B)
    I3 ↓               ↓ I4
      [Load]          [Load]

  KCL at Bus A:  I1 = I2 + I3
```

Every "power flow" or "load flow" solver you'll wrap is fundamentally solving KCL and KVL simultaneously across hundreds or thousands of buses.

---

## 2. AC Circuits — The Language of Power Systems

DC is simple but the grid runs on AC. This section is where domain-specific intuition begins.

### 2.1 Why AC?

Transformers only work with AC, and transformers let you step voltage up (for long-distance transmission with low losses) and down (for safe delivery). This single fact shaped the entire architecture of the modern grid.

### 2.2 AC Waveform Basics

```
  Voltage
    ^
    |    /\      /\      /\
    |   /  \    /  \    /  \
    |  /    \  /    \  /    \
  0 |--------\/------\/------\/--->  time
    |
    |  <- one cycle ->|
    |     (1/60 sec in North America, 1/50 sec elsewhere)
```

Key parameters:

- **Frequency (f):** 60 Hz (NA) or 50 Hz (most of the world). Your simulation tool will have this as a global setting.
- **Peak voltage (V_peak):** The crest of the wave.
- **RMS voltage (V_rms):** V_peak / √2. This is what "120 V" or "230 V" means. RMS is the DC-equivalent value — it delivers the same average power. All power system calculations use RMS unless stated otherwise.
- **Phase angle (θ):** How "shifted" in time the wave is relative to a reference. This becomes critical in three-phase and power factor discussions.

### 2.3 Impedance: Resistance's AC Cousin

In AC, components don't just resist — they also store and release energy cyclically. This leads to **impedance (Z)**, which has two parts:

```
Z = R + jX

where:
  R = Resistance  (dissipates energy as heat)
  X = Reactance   (stores/releases energy, no net consumption)
  j = imaginary unit (√-1)
```

Reactance comes from two things:

- **Inductance (L):** Coils, transformer windings, long cables. X_L = 2πfL. Current *lags* voltage.
- **Capacitance (C):** Capacitor banks, cable insulation, long underground cables. X_C = 1/(2πfC). Current *leads* voltage.

```
  IMPEDANCE TRIANGLE

         |Z|
        /|
       / |
      /  |  X (reactance)
     /   |
    /θ___|
      R (resistance)

  |Z| = √(R² + X²)
  θ = arctan(X/R)     ← impedance angle
```

Why you care: every transmission line and transformer in your model is represented as an impedance (R + jX). The data sheets and model libraries you'll work with are full of these values.

### 2.4 Phasors — How Engineers Avoid Trig

Instead of tracking sine waves, AC quantities are represented as **phasors**: complex numbers with a magnitude (RMS value) and an angle (phase shift). All the simulation math works in phasor domain.

```
  Imaginary
    ^
    |   /  V = |V| ∠ θ
    |  /
    | / θ
    +--------> Real

  V = |V|(cos θ + j sin θ)
```

When you see notation like `V = 1.02 ∠ -3.5°` in a power flow result, that's a phasor: magnitude 1.02 p.u. (more on per-unit later), angle -3.5° relative to the reference bus.

---

## 3. Power in AC Systems — The Core Concept

This is the single most important section for power system planning software.

### 3.1 The Three Kinds of Power

```
  POWER TRIANGLE

        |S|
        /|
       / |
      /  |  Q (reactive power, VAR)
     /   |
    /φ___|
      P (active/real power, W)


  S = P + jQ

  S = Apparent power  [VA]   — what the equipment must be rated for
  P = Active power    [W]    — what does actual work (runs motors, lights, heaters)
  Q = Reactive power  [VAR]  — energy sloshing back and forth, no net work done
```

**Power Factor (PF):**

```
PF = P / |S| = cos(φ)

where φ = angle between voltage and current phasors
```

- PF = 1.0: purely resistive, ideal. All apparent power is doing work.
- PF = 0.8 lagging: typical industrial load (motors). 80% of capacity does work, the rest shuttles reactive power.
- "Lagging" = inductive (motors, transformers). "Leading" = capacitive.

Why you care enormously: planning tools optimize for both P and Q. Reactive power determines voltage levels across the grid. Utilities penalize customers for poor power factor. Capacitor banks and STATCOMs are placed specifically to manage Q.

### 3.2 Complex Power Equation

The master formula you'll see in every solver:

```
S = V × I*

where I* is the complex conjugate of current phasor I
```

For a load connected between two buses:

```
S = P + jQ
P = |V||I| cos(φ)
Q = |V||I| sin(φ)
```

### 3.3 Quick Reference: Scale of Power

| Unit | Value       | Typical usage                         |
|------|-------------|---------------------------------------|
| W    | 1           | LED bulb                              |
| kW   | 10³ W       | Household peak load                   |
| MW   | 10⁶ W       | Small power plant, large building     |
| GW   | 10⁹ W       | Large power plant, city-level demand  |
| TW   | 10¹² W      | National/continental scale            |

---

## 4. Three-Phase Power

Nearly all transmission and distribution is three-phase. Single-phase is what arrives at your wall outlet — it's one leg of the three.

### 4.1 Why Three Phases?

Three sine waves, 120° apart, transmit √3 ≈ 1.73 times more power than three separate single-phase circuits using the same amount of copper. The rotating magnetic field they produce also naturally spins motors, no tricks needed.

### 4.2 The Three Phases

```
  V
  ^
  |  A        B        C
  | /\      /\      /\
  |/  \    /  \    /  \
  +----\--/----\--/----\-----> t
  |     \/      \/      \
  |
  |← 120° →|← 120° →|
```

Phases are labeled A, B, C (or R, Y, B in some regions).

### 4.3 Wye (Star) vs. Delta Connections

```
  WYE (Y / Star)                     DELTA (Δ)

       A                              A
       |                             / \
      [Za]                          /   \
       |                         [Zab] [Zca]
       N (neutral)                /       \
      /|\                        B ------- C
     / | \                          [Zbc]
  [Zb] | [Zc]
   /   |   \
  B    N    C

  V_line = √3 × V_phase           V_line = V_phase
  I_line = I_phase                 I_line = √3 × I_phase
```

In models, generators and loads can be either wye or delta connected. Transformers are specified by their winding configuration (e.g., Yg-Δ means wye-grounded primary, delta secondary). Your planning tool will ask for this.

### 4.4 Three-Phase Power Formula

```
P_3φ = √3 × V_line × I_line × cos(φ)
Q_3φ = √3 × V_line × I_line × sin(φ)
S_3φ = √3 × V_line × I_line
```

Most simulation tools work in **per-phase** (divide everything by 3 and solve one phase) then scale results back up. This simplification works because balanced three-phase systems are symmetric.

---

## 5. The Per-Unit System

Every power system tool uses per-unit (p.u.) values. This initially confuses everyone, but it's elegant once you get it.

### 5.1 The Idea

Choose base values for power and voltage. Everything else is expressed as a fraction of those bases.

```
Quantity_pu = Quantity_actual / Quantity_base
```

Example: if V_base = 230 kV and actual voltage is 225 kV:

```
V_pu = 225 / 230 = 0.978 p.u.
```

### 5.2 Choosing Bases

You pick two (usually S_base and V_base). The rest follow:

```
Given:
  S_base = 100 MVA    (common system-wide choice)
  V_base = 230 kV     (for a specific voltage level)

Derived:
  I_base = S_base / (√3 × V_base) = 100×10⁶ / (√3 × 230×10³) ≈ 251 A
  Z_base = V_base² / S_base = (230×10³)² / (100×10⁶) = 529 Ω
```

### 5.3 Why Bother?

- **Eliminates transformer ratios.** In p.u., an ideal transformer just disappears — both sides are 1.0 p.u. voltage. This massively simplifies multi-voltage-level networks.
- **Normalizes values.** Voltages hover near 1.0, currents hover near 1.0, so anomalies (a bus at 0.92 p.u.) are immediately visible.
- **Standard across the industry.** All equipment datasheets give impedance in p.u. on the equipment's own base. Your model converts to the system base.

When you see a power flow output showing bus voltages between 0.95 and 1.05, that's p.u. A bus at 0.93 p.u. is a red flag (undervoltage).

---

## 6. Transmission Lines & Cables

These are the "edges" in your network graph.

### 6.1 Line Parameters

Every line segment has four distributed parameters per unit length:

```
  ──[R]──[L]──────  ← series resistance + inductance
         |    |
        [G]  [C]    ← shunt conductance + capacitance (to ground)
         |    |
  ─────────────────
```

- **R** (Ω/km): Conductor resistance. Causes I²R losses (heat).
- **X_L** (Ω/km): Inductive reactance. Dominates in overhead lines.
- **B_C** (S/km): Shunt capacitive susceptance. Significant in long lines and underground cables.
- **G** (S/km): Shunt conductance (leakage). Usually negligible and ignored.

### 6.2 Line Models by Length

| Line length     | Model used       | What's included                        |
|-----------------|------------------|----------------------------------------|
| Short (< 80 km) | Series impedance | R + jX only                            |
| Medium (80-250) | π-model          | R + jX with half the shunt B at each end |
| Long (> 250 km) | Distributed/ABCD | Hyperbolic functions, wave propagation  |

The **π-model** is what you'll see most in planning tools:

```
        R + jX
  Bus i ────────────── Bus j
    |                    |
   [B/2]               [B/2]
    |                    |
   GND                  GND
```

Your model's line database will have columns like `r_ohm_per_km`, `x_ohm_per_km`, `c_nf_per_km`, and `length_km`. The tool builds the π-model from these.

### 6.3 Power Losses in Lines

```
P_loss = I² × R

(per phase, for the series resistance)
```

This is why transmission uses high voltage: for a given power P = V × I, higher V means lower I, and losses scale with I². Doubling voltage → halving current → quartering losses.

### 6.4 Thermal Limits and Capacity

Every line has a maximum current (ampacity) determined by how much heat the conductor can tolerate before it sags too much (overhead) or damages insulation (cable). In planning, you constrain line power flow ≤ thermal rating.

---

## 7. Transformers

Transformers are the junctions between voltage levels in the grid hierarchy.

### 7.1 Ideal Transformer

```
  V₁     N₁ : N₂     V₂
  ──┤├── ||||  |||| ──┤├──
         Primary Secondary

  V₂/V₁ = N₂/N₁ = a  (turns ratio)
  I₂/I₁ = N₁/N₂ = 1/a
  S₁ = S₂              (power is conserved)
```

### 7.2 Real Transformer Model

```
                    R_eq + jX_eq
  Bus HV ──────┤├──────────────────── Bus LV
                  (referred to one side)
```

The key parameter is **X_eq** (leakage reactance), typically given as a percentage on the transformer's own base:

```
Example: 500 MVA transformer, X = 12%
→ X_pu = 0.12 on 500 MVA base
→ Convert to system base if S_base ≠ 500 MVA:
   X_pu_system = 0.12 × (S_base_system / 500)
```

### 7.3 Tap Changers

On-Load Tap Changers (OLTCs) adjust the turns ratio in small steps (±10% in ~1.25% increments) to regulate voltage. In planning models, the tap position is either fixed or optimized by the solver to keep bus voltages in band.

```
  Tap ratio t = 1.0    → nominal
  Tap ratio t = 1.05   → boosting voltage on the secondary by 5%
  Tap ratio t = 0.95   → bucking voltage by 5%
```

---

## 8. Buses, Generators, and Loads — The Network Model

### 8.1 The Bus

A **bus** is a node in the network graph. It's an idealized point where components connect. Every bus has two known and two unknown quantities out of {P, Q, |V|, θ}:

| Bus type    | Known      | Unknown    | Represents                    |
|-------------|------------|------------|-------------------------------|
| **Slack**   | \|V\|, θ   | P, Q       | Reference bus, balances system |
| **PV**      | P, \|V\|   | Q, θ       | Generator bus                 |
| **PQ**      | P, Q       | \|V\|, θ   | Load bus                      |

The slack bus is a mathematical necessity — it absorbs the mismatch between total generation and total load + losses. In planning, it's usually the largest generator or the grid connection point.

### 8.2 Generator Models (for Planning)

For steady-state planning (not dynamic simulation), generators are modeled simply:

```
  Bus
   │
   ├── P_gen (active power output, MW)
   ├── V_setpoint (voltage setpoint, p.u.)
   ├── Q_min, Q_max (reactive power limits, MVAR)
   ├── P_min, P_max (active power limits, MW)
   └── Cost curve: C(P) = a + bP + cP²  (for economic dispatch)
```

The cost curve is central to economic planning — it's the fuel cost to produce P megawatts.

### 8.3 Load Models

Loads are typically modeled as constant power (P + jQ specified), but more sophisticated models exist:

- **Constant power (CP):** P, Q fixed regardless of voltage. Most common in planning.
- **Constant current (CI):** P, Q scale linearly with voltage.
- **Constant impedance (CZ):** P, Q scale with voltage squared.
- **ZIP model:** Weighted combination of all three. Coefficients come from measurement data.

```
P = P₀ [a₁(V/V₀)² + a₂(V/V₀) + a₃]    where a₁+a₂+a₃ = 1
     └─ Z ─┘     └─ I ─┘   └─ P ─┘
```

### 8.4 Putting It Together: A Simple Network

```
        Slack Bus              PV Bus (Generator)
        (Bus 1)                (Bus 2)
          │                      │
     G ──[=]                G ──[=]
          │     Line 1-2         │
          ├──────[Z12]───────────┤
          │                      │
          │     Line 1-3         │     Line 2-3
          ├──────[Z13]──┐        ├──────[Z23]──┐
          │              │       │              │
                         │                      │
                        [=]──── Load             │
                       (Bus 3)                   │
                       PQ Bus                    │
                         └───────────────────────┘
```

This is a 3-bus system. Planning tools work with thousands of buses, but the concept is identical.

---

## 9. Power Flow (Load Flow) Analysis

This is the bread-and-butter calculation in power system planning. You'll be invoking this constantly.

### 9.1 What It Solves

Given: network topology, line impedances, generator setpoints, load values.
Find: voltage magnitude and angle at every bus, power flow on every line, losses.

### 9.2 The Equations

At each bus, KCL in power form:

```
P_i = Σⱼ |V_i||V_j|(G_ij cos θ_ij + B_ij sin θ_ij)
Q_i = Σⱼ |V_i||V_j|(G_ij sin θ_ij - B_ij cos θ_ij)

where:
  θ_ij = θ_i - θ_j
  G_ij + jB_ij = entries of the bus admittance matrix Y_bus
```

This is a system of nonlinear equations — no closed-form solution. Solvers use iterative methods.

### 9.3 The Y-Bus (Admittance Matrix)

The Y-bus is the adjacency matrix of the network, but with admittance values (Y = 1/Z = G + jB):

```
  Y_bus = [Y₁₁  Y₁₂  Y₁₃]
          [Y₂₁  Y₂₂  Y₂₃]
          [Y₃₁  Y₃₂  Y₃₃]

  Diagonal:     Y_ii = sum of all admittances connected to bus i
  Off-diagonal: Y_ij = -(admittance of branch between bus i and j)
```

If no branch connects i and j, Y_ij = 0 → the matrix is sparse for large networks. Sparsity techniques are critical for solver performance and will come up in your codebase.

### 9.4 Newton-Raphson Method

The standard power flow solver. Here's the conceptual loop:

```
1. Initialize: flat start (all |V| = 1.0, all θ = 0°)
2. Compute mismatches: ΔP, ΔQ at each bus
3. Build Jacobian matrix J (partial derivatives of P,Q w.r.t. V,θ)
4. Solve: [Δθ, Δ|V|] = J⁻¹ × [ΔP, ΔQ]
5. Update: θ ← θ + Δθ, |V| ← |V| + Δ|V|
6. If max(|ΔP|, |ΔQ|) < tolerance → converged. Else → step 2.
```

Typically converges in 3-5 iterations for well-conditioned systems. When it *doesn't* converge, it usually means the system is infeasible (overloaded, insufficient reactive support, etc.) — which is useful planning information.

### 9.5 DC Power Flow (Linearized Approximation)

For planning studies that need speed over precision (especially economic analysis across thousands of scenarios):

Assumptions: all |V| = 1.0, all R ≈ 0 (lossless), small angle differences.

```
P = B' × θ

where B' is a simplified (real-valued) susceptance matrix
```

This is a linear system → direct solve, no iterations. Fast enough to run inside an optimizer's inner loop. Gives active power flows and angles, but no voltages and no reactive power. Many economic planning tools use DC power flow by default.

---

## 10. Key Planning Analyses

### 10.1 Contingency Analysis (N-1 Security)

The grid must survive the loss of any single element (line, transformer, generator). Planning tools automate this:

```
for each element e in system:
    remove e
    run power flow
    check: all voltages in [0.95, 1.05] p.u.?
    check: all line flows < thermal limits?
    if violations → flag, record needed reinforcements
    restore e
```

This is computationally heavy (one power flow per contingency). Your architecture choices for parallelization and result caching matter here.

### 10.2 Optimal Power Flow (OPF)

Power flow finds *a* solution. OPF finds the *best* one.

```
Minimize:  Σ C_i(P_i)          ← total generation cost
Subject to:
  - Power flow equations (equality constraints)
  - V_min ≤ |V_i| ≤ V_max     ← voltage limits
  - P_min ≤ P_i ≤ P_max       ← generator limits
  - |S_line| ≤ S_max           ← line flow limits
  - Q_min ≤ Q_i ≤ Q_max       ← reactive limits
```

- **DC-OPF:** Uses linearized power flow. An LP (linear program). Fast, used in market clearing and planning screening.
- **AC-OPF:** Uses full nonlinear power flow. An NLP (nonlinear program). More accurate but harder to solve. Active research area.

The Lagrange multipliers from OPF give you **Locational Marginal Prices (LMPs)** — the cost of delivering one more MW to each bus. Central to electricity market design and economic planning.

### 10.3 Economic Dispatch

A simplified version of OPF: given total system demand, allocate generation among available units to minimize cost, respecting generator limits but ignoring network constraints.

```
Minimize:  Σ (aᵢ + bᵢPᵢ + cᵢPᵢ²)
Subject to:
  Σ Pᵢ = P_demand + P_losses
  P_min_i ≤ Pᵢ ≤ P_max_i
```

Optimality condition (when unconstrained): all generators operate at equal **incremental cost** (dC/dP).

```
λ = dC₁/dP₁ = dC₂/dP₂ = ... = dCn/dPn

λ is called the system marginal cost ($/MWh)
```

### 10.4 Unit Commitment

One level above dispatch: decide which generators to turn *on* for each hour of the planning horizon (day-ahead, week-ahead).

```
For each hour t, for each generator g:
  u_g,t ∈ {0, 1}     ← on/off (binary variable)

Minimize: Σ_t Σ_g [u_g,t × C_g(P_g,t) + startup_cost × (u_g,t - u_g,t-1)⁺]

Subject to:
  - Demand balance each hour
  - Min up/down time constraints
  - Ramp rate limits: |P_g,t - P_g,t-1| ≤ ramp_max
  - Reserve requirements
```

This is a Mixed-Integer Program (MIP). Computationally expensive. Commercial solvers (Gurobi, CPLEX) or open-source (HiGHS, GLPK) are used.

### 10.5 Capacity Expansion Planning

The long-range planning question: what to build, where, and when.

```
Decide:
  - New generation capacity (type, size, location)
  - New transmission lines/upgrades
  - Storage installations
  - Retirement of old assets

Over: 10-30 year horizon, typically in 5-year increments

Minimize: NPV of (capital costs + operating costs)
Subject to:
  - Meet demand growth projections
  - Reliability criteria (reserve margin, N-1)
  - Renewable energy targets / emissions caps
  - Network constraints (power flow feasibility)
```

This often nests the other analyses: for each candidate plan, run dispatch, check network feasibility, evaluate costs.

---

## 11. Voltage Regulation & Reactive Power Planning

### 11.1 Why Voltage Drops

```
  Sending end                     Receiving end
  V_s = 1.0 pu                   V_r = ?
       │         R + jX               │
       ├─────────[====]───────────────┤
       │                              │
                                    [Load]
                                   P + jQ
```

Approximate voltage drop:

```
ΔV ≈ (P×R + Q×X) / V

Key insight: voltage drop depends on BOTH active and reactive power,
but in HV transmission (where X >> R), reactive power Q dominates.
```

This is why reactive power management is so central to planning.

### 11.2 Reactive Power Devices

| Device           | Supplies/Absorbs Q | Notes                                |
|------------------|--------------------|--------------------------------------|
| Capacitor bank   | Supplies Q         | Cheap, discrete steps, switched      |
| Reactor          | Absorbs Q          | Used on lightly loaded long lines    |
| SVC (Static VAR) | Both, continuous   | Power electronics, fast response     |
| STATCOM          | Both, continuous   | Voltage-source converter, expensive  |
| Synchronous cond.| Both, continuous   | Rotating machine, legacy but useful  |
| OLTC transformer | Adjusts V directly | Changes turns ratio under load       |

Planning tools include placement optimization: where to put capacitors/SVCs to keep voltages in band at minimum cost.

---

## 12. Fault Analysis (Short Circuit Studies)

When planning, you must ensure the system can safely handle faults (short circuits). The fault current determines the required rating of circuit breakers and switchgear.

### 12.1 Types of Faults

```
  Three-phase (L-L-L):      Least common, most severe, symmetric
  Line-to-Line (L-L):       Unbalanced
  Line-to-Ground (L-G):     Most common (~70%), unbalanced
  Double Line-to-Ground:     Unbalanced
```

### 12.2 Symmetrical Components (Fortescue Transform)

Unbalanced three-phase problems are decomposed into three balanced systems:

```
  [V₀]       [1  1  1 ] [V_a]
  [V₁]  = ⅓  [1  a  a²] [V_b]
  [V₂]       [1  a² a ] [V_c]

  where a = 1∠120°

  V₀ = zero-sequence  (all three phases identical)
  V₁ = positive-sequence (normal balanced operation)
  V₂ = negative-sequence (reverse rotation)
```

Each sequence sees its own impedance network. For a balanced system, only positive-sequence exists. Faults introduce negative and zero-sequence components.

Your model's component data will include positive, negative, and zero-sequence impedances (Z₁, Z₂, Z₀). For lines and transformers, Z₁ ≈ Z₂ but Z₀ can be very different (depends on grounding and return path).

### 12.3 Fault Current Calculation (Simplified)

For a three-phase fault at bus k:

```
I_fault = V_prefault / Z_thevenin

where Z_thevenin is the impedance seen looking into the network from bus k
(= diagonal element of Z_bus, the bus impedance matrix, which is inv(Y_bus))
```

Fault currents are typically 10-40× normal load current. Circuit breaker ratings must exceed the maximum fault current at their location.

---

## 13. Renewable Energy Integration

Renewables introduce variability and uncertainty that planning tools must handle.

### 13.1 Solar PV in Grid Models

```
  P_solar(t) = P_rated × G(t)/G_stc × η(T)

  G(t)   = solar irradiance at time t (W/m²)
  G_stc  = 1000 W/m² (standard test conditions)
  η(T)   = temperature derating factor
```

Key modeling concerns: capacity factor (15-25% typical), inverter reactive power capability (modern inverters can provide/absorb Q), intermittency requires storage or backup.

### 13.2 Wind in Grid Models

```
  P_wind(t) = ½ × ρ × A × v(t)³ × Cp

  ρ  = air density (~1.225 kg/m³)
  A  = rotor swept area (m²)
  v  = wind speed (m/s)
  Cp = power coefficient (max ~0.593, Betz limit)
```

Actual turbine output follows a power curve: zero below cut-in (~3 m/s), rated above rated wind (~12 m/s), zero above cut-out (~25 m/s). Planning uses statistical wind speed distributions (Weibull) to estimate annual energy yield.

### 13.3 Capacity Factor and Firm Capacity

```
Capacity Factor = Actual Energy Produced / (Rated Capacity × Time Period)

  Solar PV:     15-25%
  Onshore wind: 25-45%
  Offshore wind: 35-55%
  Nuclear:      85-95%
  Gas CCGT:     40-60% (depends on dispatch economics)
```

**Firm capacity** (capacity credit) is how much a resource can be relied upon during peak demand. A 100 MW wind farm might have only 10-20 MW of firm capacity. Planning for reliability requires this distinction.

---

## 14. Energy Storage

### 14.1 Key Parameters

```
  Energy capacity:   E (MWh) — total energy stored
  Power capacity:    P (MW)  — max charge/discharge rate
  Duration:          E/P (hours)
  Round-trip efficiency: η_rt (typically 85-95% for Li-ion)
  State of Charge:   SOC(t) = E_stored(t) / E_max
```

### 14.2 Storage in Optimization Models

```
SOC(t+1) = SOC(t) + η_charge × P_charge(t) × Δt - (1/η_discharge) × P_discharge(t) × Δt

Constraints:
  0 ≤ SOC(t) ≤ E_max
  0 ≤ P_charge(t) ≤ P_max
  0 ≤ P_discharge(t) ≤ P_max
  P_charge(t) × P_discharge(t) = 0   ← can't charge and discharge simultaneously
```

The last constraint is bilinear (nonconvex). In practice, solvers handle it via binary variables or relaxation (it naturally holds at optimality in most cases).

---

## 15. Economic & Financial Concepts

### 15.1 Levelized Cost of Energy (LCOE)

```
LCOE = (Total Lifetime Cost) / (Total Lifetime Energy)

     = [CAPEX + Σ(OPEX_t / (1+r)^t)] / [Σ(E_t / (1+r)^t)]

  r = discount rate
  t = year
```

LCOE lets you compare $/MWh across technologies with very different cost structures (high CAPEX solar vs. low CAPEX/high OPEX gas).

### 15.2 Net Present Value (NPV) and Discount Rate

```
NPV = Σ [Cash_flow_t / (1 + r)^t]  for t = 0 to N
```

All planning models discount future costs. The discount rate `r` encodes the time value of money and risk. Typical values: 5-10% real for power projects. This single parameter dramatically affects technology choice (capital-intensive renewables favor low r; fuel-intensive gas favors high r).

### 15.3 Locational Marginal Pricing (LMP)

```
LMP_i = λ_energy + λ_congestion_i + λ_losses_i

  λ_energy:      system-wide energy price (from marginal generator)
  λ_congestion:  premium/discount due to transmission constraints at bus i
  λ_losses:      cost of marginal losses to deliver power to bus i
```

LMPs emerge from DC-OPF or AC-OPF as dual variables (shadow prices) of the power balance constraints. They're the foundation of wholesale electricity market design and drive investment signals for new generation and transmission.

### 15.4 Annualized Capital Cost

```
Annual_cost = CAPEX × CRF

CRF = r(1+r)^n / [(1+r)^n - 1]

  CRF = Capital Recovery Factor
  n   = asset lifetime (years)
  r   = discount rate
```

Planning models express all costs on an annual basis so capital and operating costs can be summed.

---

## 16. Key Formulas — Quick Reference

```
DC:     P = VI,  V = IR
AC:     S = P + jQ = VI*
        P = |V||I|cosφ,   Q = |V||I|sinφ
3-Phase: S = √3 × V_L × I_L
Per-unit: X_pu = X_actual / Z_base,   Z_base = V_base² / S_base
Line loss: P_loss = I²R
Voltage drop: ΔV ≈ (PR + QX) / V
Fault current: I_f = V / Z_th
Power flow: P_i = Σ |Vi||Vj|(Gij cosθij + Bij sinθij)
DC power flow: P = B'θ  (linear)
LCOE: (CAPEX + ΣOPEX) / ΣEnergy  (all discounted)
LMP: λ_energy + λ_congestion + λ_losses
Storage: SOC(t+1) = SOC(t) + η_c × P_c × Δt - P_d × Δt / η_d
```

---

## 17. Glossary of Terms You'll Encounter in Code & Data

| Term              | Meaning                                                        |
|-------------------|----------------------------------------------------------------|
| Bus               | Node in the network graph                                      |
| Branch            | Edge (line, transformer, or other series element)              |
| Slack / Swing bus | Reference bus that balances P and Q                            |
| Y-bus             | Network admittance matrix (sparse)                             |
| Z-bus             | Network impedance matrix (Y-bus inverse, used for fault calc)  |
| N-1               | System must survive loss of any single element                 |
| Dispatch          | Allocating generation to meet demand                           |
| Merit order       | Ranking generators by marginal cost, cheapest first            |
| Curtailment       | Reducing renewable output because grid can't absorb it         |
| Congestion        | When a line hits its limit, constraining cheaper generation    |
| Baseload          | Continuous minimum demand; also generation that runs 24/7      |
| Peaker            | Generator that runs only during peak demand (high marginal cost)|
| Reserve margin    | Excess capacity above peak demand for reliability              |
| Spinning reserve  | Online generation ready to ramp up within minutes              |
| SCADA             | Supervisory Control and Data Acquisition (real-time telemetry) |
| OLTC              | On-Load Tap Changer (voltage-regulating transformer)           |
| FACTS             | Flexible AC Transmission Systems (SVC, STATCOM, etc.)         |
| HVDC              | High Voltage Direct Current (long distance, undersea cables)  |
| Droop             | Governor response: frequency drops → generator increases output|

---

## 18. Mapping to Software Tools

| Tool          | Language | Typical use                              | Power flow | OPF  |
|---------------|----------|------------------------------------------|------------|------|
| pandapower    | Python   | Distribution & transmission planning     | NR, DC     | AC/DC|
| PyPSA         | Python   | Capacity expansion, market modeling      | NR, DC     | DC   |
| MATPOWER      | MATLAB   | Research, detailed AC/DC power flow      | NR, DC     | AC/DC|
| OpenDSS       | COM/Py   | Distribution, DER, time-series           | NR         | No   |
| PowerModels.jl| Julia    | Research OPF (multiple formulations)     | NR, DC     | AC/DC|
| PLEXOS / PROMOD| Commercial | Production cost, market simulation    | DC         | DC   |
| GridCal       | Python   | GUI-based, power flow & short circuit    | NR, DC     | Yes  |

When wrapping or integrating these, your software layer typically handles data ingestion (GIS, asset databases), scenario management, result storage, and visualization — while delegating the heavy math to these engines.
# First Review Diagrams (ASCII)

================================================================================
## DIAGRAM 1 — Script Interrelation
================================================================================

                        ENTRY POINTS
    ┌───────────────────────┬──────────────────────────┬─────────────┐
    │   daily_sim.m         │  daily_sim_combined_CD.m  │ randomrun.m │
    │                       │  _test1.m  /  _test2.m    │             │
    └──────┬────────────────┴──────┬───────────────────┴──────┬──────┘
           │                       │                           │
           │         NETWORK SETUP │                           │ calls
           │    ┌──────────────────▼───────────────────┐      │ daily_sim_
           └───►│  bb_pv_cluster1.m                    │◄─────┘ for_random
                │  (bus/line topology, base values,     │        _run
                │   ZIP load ratios, PPL)               │
                └──────────────────┬───────────────────┘
                                   │
                                   ▼
                ┌──────────────────────────────────────┐
                │  ymat_3ph3_4w.m                      │
                │  (build Y-bus matrix, init busV/busA, │
                │   set up load/DG index arrays)        │
                └──────────────────────────────────────┘

           DATA LOADING
    ┌──────────────────────────────────────────────────────────────┐
    │  data_read.m                                                 │
    │    ├──► demand_curve.m ──────────────────────────────────────┼──► Gatton Sub0
    │    └──► pv_curve.m ─────────────────────────────────────────┼──► 2013 Data.xlsx
    └──────────────────────────────────────────────────────────────┘
    SoC_Arrival_random_IASpaper_data1.mat ◄── loaded by entry points

           REFERENCE GENERATION  (combined_CD only)
    ┌──────────────────────────────────────────────────────────────┐
    │  SoC_ref_gen.m  (parabolic SoC reference trajectory)        │
    │  cdparam.m      (battery kinetic model parameters)           │
    └──────────────────────────────────────────────────────────────┘

    ════════════════════════ TIME-STEP LOOP ════════════════════════

           POWER FLOW SOLVER
    ┌──────────────────────────────────────────────────────────────┐
    │  nrci3ph4w.m  (Newton-Raphson iteration controller)         │
    │      │                                                        │
    │      ▼                                                        │
    │  curr_mm_3p3_4w.m  (current mismatch, Jacobian update)      │
    │      │                                                        │
    │      └──── converged? ──NO──► loop back to nrci3ph4w         │
    │                  │                                            │
    │                 YES                                           │
    │                  ▼                                            │
    │  lineflow_3p4w.m  (S, I, losses per line and phase)         │
    └──────────────────────────────────────────────────────────────┘

           BATTERY CONTROL  (each call back into curr_mm_3p3_4w)
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │  charge_control.m ──────────────────────────────────────────┤
    │  discharge_control.m ───────────────────────────────────────┼──► curr_mm_3p3_4w
    │  night_charge_control.m ────────────────────────────────────┤
    │  smoothing_control.m ───────────────────────────────────────┤
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

    ═══════════════════════ POST-SIMULATION ════════════════════════

    ┌─────────────────────────┐      ┌──────────────────────────────┐
    │  rainflow_bins.m        │      │  gbess_perf1.m               │
    │  myRainFlow_YG.m        │      │  (charge/discharge energy,   │
    │  (cycle counting,       │      │   performance metrics)        │
    │   fatigue damage index) │      │  reads GattonBESSData*.mat   │
    └─────────────────────────┘      └──────────────────────────────┘


================================================================================
## DIAGRAM 2 — Conceptual Architecture
================================================================================

  Layers flow top-to-bottom. The battery model feeds back into the power flow
  engine on every time step (marked with <<feedback>>).

  ┌─────────────────────────────────────────────────────────────┐
  │  1. INPUT DATA                                              │
  │                                                             │
  │   · Real load demand         (Gatton Sub0 2013.xlsx)        │
  │   · PV generation profiles   (.xlsx + synthetic .mat)       │
  │   · Real BESS measurements   (GattonBESSData*.mat)          │
  │   · EV arrival / SoC data    (.mat)                         │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  2. NETWORK MODEL                                           │
  │                                                             │
  │   · Bus & line topology   — bus struct, line struct         │
  │   · 3-phase Y-bus matrix  — admittance (4-wire, w/ neutral) │
  │   · ZIP load model        — constant P + I + Z components   │
  │   · DER injection model   — PV and BESS power per bus       │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐  ◄──┐
  │  3. POWER FLOW ENGINE                                       │     │
  │                                                             │     │
  │   · Newton-Raphson solver  — current-mismatch formulation   │     │
  │       loop: update voltages → recalc currents               │     │
  │             check |ΔI| < ε    (max 50 iterations)           │     │
  │   · Line flow calculator   — S, I, losses per phase/neutral │     │
  └──────────────────────────────┬──────────────────────────────┘     │
                                 │                                     │
                                 ▼                                     │
  ┌─────────────────────────────────────────────────────────────┐     │
  │  4. CONTROL STRATEGIES                                      │     │
  │                                                             │     │
  │   · Charging control    — SoC reference tracking,           │     │
  │                           ramp-rate limits, surplus PV use  │     │
  │   · Discharging control — DoD limits, ramp-rate limits,     │     │
  │                           EV departure/return scheduling     │     │
  │   · Night charging      — off-peak top-up to SoCmax         │     │
  │   · PV smoothing        — moving-average ramp-rate control  │     │
  │   · SoC reference gen   — parabolic target trajectory       │     │
  └──────────────────────────────┬──────────────────────────────┘     │
                                 │                                     │
                                 ▼                                     │
  ┌─────────────────────────────────────────────────────────────┐     │
  │  5. BATTERY MODEL                                           │     │
  │                                                             │     │
  │   · Kinetic battery model  — E0, K, A, B parameters        │     │
  │                              separate charge / discharge     │     │
  │   · SoC tracker            — coulomb counting              │     │
  │                              + coulomb & converter losses    │     │
  │   · Terminal voltage       — Vbatt = f(SoC, I, R)          │     │
  │   · BESS power injection   — updates busBTP on each bus     │     │
  │                                                             │     │
  │                    <<feedback: busBTP ──────────────────────┼─────┘
  │                      re-enters power flow engine>>          │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  6. ANALYSIS & OUTPUT                                       │
  │                                                             │
  │   · Bus voltages          — per phase, per time step        │
  │   · Line losses           — 3-phase + neutral, per segment  │
  │   · SoC profile           — daily trajectory per battery    │
  │   · Rainflow cycle count  — amplitude histogram,            │
  │                             Palmgren-Miner damage index,     │
  │                             battery lifetime estimate        │
  │   · BESS performance      — charge/discharge energy,        │
  │                             round-trip efficiency,           │
  │                             grid import / export             │
  └─────────────────────────────────────────────────────────────┘


================================================================================
## DIAGRAM 3 — Data Model
================================================================================

  Entities are grouped by concern. Relationships are listed after each group.

  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  GROUP A — NETWORK TOPOLOGY                                             ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────────────────────┐   ┌──────────────────────────────────┐
  │ BUS                              │   │ LINE                             │
  ├──────────────────────────────────┤   ├──────────────────────────────────┤
  │ id           int                 │   │ id           int                 │
  │ type         int                 │   │ from_bus     int  ─────────────► │ BUS.id
  │              1=PQ 2=PV 3=swing   │   │ to_bus       int  ─────────────► │ BUS.id
  │ V_init       float  (pu)         │   │ R_matrix     float (3×3 or 4×4) │
  │ A_init       float  (rad)        │   │ X_matrix     float (3×3 or 4×4) │
  │ PL, QL       float  load (pu)    │   │ B_shunt      float               │
  │ DGP, DGQ     float  PV inj (pu)  │   └──────────────────────────────────┘
  │ BTP          float  bat pwr (pu) │          │ each LINE contributes to
  │              +ve = charging      │          ▼
  │ PI, QI       float  const-I load │   ┌──────────────────────────────────┐
  │ PZ, QZ       float  const-Z load │   │ YBUS_MATRIX                      │
  └──────────────────────────────────┘   ├──────────────────────────────────┤
                                         │ size   3·tot_bus × 3·tot_bus     │
                                         │        (4-wire incl. neutral)    │
                                         │ Y      complex  full admittance  │
                                         │ G      float    conductance part │
                                         │ B      float    susceptance part │
                                         │ dY     complex  incremental upd  │
                                         └──────────────────────────────────┘

  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  GROUP B — BATTERY & CONTROL                                            ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────────────────────┐
  │ BATTERY                          │
  ├──────────────────────────────────┤
  │ C_bat        float  cap (Ah)     │
  │ SoC          float  [0 .. 1]     │
  │ SoC_ref      float  target       │
  │ SoC_ideal    float  ref traj.    │
  │ Vbatt        float  terminal (V) │
  │ Ibatt        float  current (A)  │
  │              +ve = charging      │
  │ — charge model params —          │
  │ E0_C, K_C, A_C, B_C   float     │
  │ — discharge model params —       │
  │ E0_D, K_D, A_D, B_D   float     │
  │ — limits & losses —              │
  │ R            float  int. resist  │
  │ DoDmax       float  [0 .. 1]     │
  │ SoCmax       float  [0 .. 1]     │
  │ eta_coulomb  float  coulomb eff  │
  │ Conv_Eff     float  conv. eff    │
  └───────────┬──────────────────────┘
              │ governed by
      ┌───────┴───────┐
      ▼               ▼
  ┌────────────────────────┐   ┌────────────────────────┐
  │ CHARGE_CTRL            │   │ DISCHARGE_CTRL         │
  ├────────────────────────┤   ├────────────────────────┤
  │ I_Chg_max   float (A)  │   │ I_Dsch_max  float (A)  │
  │ I_bat_C_mem float (A)  │   │ I_bat_D_mem float (A)  │
  │             prev step  │   │             prev step  │
  │ omega_Chg   float      │   │ omega_Dsch  float      │
  │             ramp limit │   │             ramp limit │
  │ CincSoC     threshold  │   │ DincSoC     threshold  │
  │ CdecSoC     threshold  │   │ DdecSoC     threshold  │
  │ charging_node  int     │   │ discharge_node  int    │
  └────────────────────────┘   └────────────────────────┘

              │ SoC time-series analysed by
              ▼
  ┌──────────────────────────────────┐
  │ RAINFLOW                         │
  ├──────────────────────────────────┤
  │ range_cycles  float[]  amp histo │
  │ amp_cycles    float[]  amp/count │
  │ D             float    Miner dmg │
  │ num           int      total cyc │
  │ AverageAmp    float              │
  │ MaxPeak       float    SoC high  │
  │ MinValley     float    SoC low   │
  └──────────────────────────────────┘

  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  GROUP C — TIME-SERIES PROFILES                                         ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────────────────────┐   ┌──────────────────────────────────┐
  │ PV_PROFILE                       │   │ LOAD_PROFILE                     │
  ├──────────────────────────────────┤   ├──────────────────────────────────┤
  │ pv_curve_shape_factor  float[]   │   │ demand_curve_shape_factor float[] │
  │                 1440 pu values   │   │                  1440 pu values  │
  │ PPL             float            │   │ LDM             float            │
  │                 PV penetration   │   │                 load multiplier  │
  │ PVP             float[]          │   │ rawloaddata     float[]          │
  │                 instantaneous    │   │                 from xlsx        │
  │ PVP_MA          float[]          │   │ LDP_RampRate    float[]          │
  │                 moving average   │   │                 per time step    │
  │ PVP_RampRate    float[]          │   └──────────────────────────────────┘
  │                 per time step    │
  └──────────────────────────────────┘

  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  GROUP D — SIMULATION RUNTIME & RESULTS                                 ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────────────────────┐   ┌──────────────────────────────────┐
  │ SIMULATION                       │   │ LINE_FLOW                        │
  ├──────────────────────────────────┤   ├──────────────────────────────────┤
  │ SimIter    int   current step    │   │ S_from      complex  send pwr pu │
  │ day_1min   int   1440 total      │   │ I_from      complex  send cur pu │
  │ kVA_base   float system base     │   │ line_loss   float    total (pu)  │
  │ kV_baseL   float LV base (kV)    │   │ line_loss_a float    phase A     │
  │ I_baseL    float LV base (A)     │   │ line_loss_b float    phase B     │
  │ oldV       float prev busV       │   │ line_loss_c float    phase C     │
  │ oldA       float prev busA       │   │ line_loss_n float    neutral     │
  └──────────────────────────────────┘   └──────────────────────────────────┘

  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  RELATIONSHIPS                                                          ║
  ╠══════════════════════════════════════════════════════════════════════════╣
  ║  BUS         1──* LINE           connected via from_bus / to_bus        ║
  ║  BUS         1──1 BATTERY        hosts one BESS at DER node             ║
  ║  BUS         1──1 PV_PROFILE     receives PV injection per bus          ║
  ║  BUS         1──1 LOAD_PROFILE   draws ZIP demand per bus               ║
  ║  LINE        *──1 YBUS_MATRIX    each line stamps impedance entries      ║
  ║  BATTERY     1──1 CHARGE_CTRL    charging governed by CHARGE_CTRL       ║
  ║  BATTERY     1──1 DISCHARGE_CTRL discharging governed by DISCHARGE_CTRL ║
  ║  BATTERY     1──1 RAINFLOW       SoC series fed into cycle counter      ║
  ║  SIMULATION  1──* BUS            iterates over all buses per time step  ║
  ║  SIMULATION  1──* LINE_FLOW      records one LINE_FLOW per line/step    ║
  ║  YBUS_MATRIX 1──1 SIMULATION     consumed by every NR solve call        ║
  ╚══════════════════════════════════════════════════════════════════════════╝

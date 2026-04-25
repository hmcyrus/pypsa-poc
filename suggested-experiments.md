# Suggested PyPSA Economic Dispatch Experiments

Data source: `grids-substations-data-pgcb/grids-formatted.csv` and `grids-substations-data-pgcb/substations-formatted.csv`

## Data Summary

**grids-formatted.csv** — 263 transmission lines across 3 voltage tiers:
- **400 kV** (29 lines): EHV backbone + 2 HVDC cross-border links to India (Bheramara-Baharampur, Comilla N-Bangladesh Border)
- **230 kV** (63 lines): Main inter-zonal backbone
- **132 kV** (171 lines): Sub-transmission and power plant tap lines

**substations-formatted.csv** — ~250+ substations across 8 operational zones (Dhaka, Khulna, Chattogram, Cumilla, Rajshahi, Rangpur, Sylhet, Barishal) with transformer capacities from 35 MVA to 2250 MVA.

---

## Experiment 1: Zonal Economic Dispatch (8-Zone Simplified Network)

Aggregate the grid into 8 buses (one per operational zone). Use the 400 kV and 230 kV inter-zonal lines to set transmission limits. Assign synthetic generator cost curves by zone (gas, coal, hydro, import) and run a basic economic dispatch. This shows how inter-zonal flows emerge from merit-order optimization.

## Experiment 2: DC-OPF on the 400 kV Backbone

Build a detailed network with the ~13 major 400 kV substations as buses (Aminbazar, Meghnaghat, Madunaghat, Kaliakoir, Korerhat, etc.) and their 400 kV interconnections. Run DC OPF and show how the dispatch changes when line thermal limits are binding vs. unconstrained.

## Experiment 3: Transmission Congestion & Locational Marginal Prices (LMPs)

On the Experiment 2 network, deliberately tighten one or two critical lines (e.g., Dhaka corridor Aminbazar-Kaliakoir, which is a known bottleneck) and show how LMPs diverge across the network — illustrating the value of congestion pricing.

## Experiment 4: Cross-Border HVDC Import (India Interconnects)

Add the two HVDC import links from India (Bheramara-Baharampur 400 kV, Comilla N-Border 400 kV) as controllable links with an external market price. Show how the optimal import level shifts as domestic generator costs or fuel prices change — replicating Bangladesh's real import economics.

## Experiment 5: Renewable Penetration Dispatch

Add synthetic solar plants (south: Payra, Banskhali corridor) and wind/solar at strategic 400 kV nodes. Run dispatch at different renewable penetration levels (0%, 20%, 40%) and show how dispatch changes, curtailment emerges, and where grid congestion limits renewable absorption.

## Experiment 6: 24-Hour Multi-Period Dispatch

Use a realistic Bangladesh load profile (morning/evening peaks, low night) across the 8 zones. Run a rolling 24-period economic dispatch to show how the generation stack and line flows change across the day — including how cheap baseload (coal/import) runs flat while gas peakers kick in at peak hours.

---

## Recommended Sequence

Start with **Exp 1 → Exp 2 → Exp 3** in sequence, since each builds on the last. **Exp 4** is standalone and directly relevant to Bangladesh's actual grid situation with Indian power imports.

# Bangladesh Power System Analysis Platform
## Design Proposal & Strategic Assessment

> **Audience:** Product builders, investors, policy analysts, power system engineers
> **Date:** May 2026 | **Status:** Draft v1.0
> **Codebase:** [hmcyrus/pypsa-poc](https://github.com/hmcyrus/pypsa-poc) · branch `claude/electricity-market-model-2a64p`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Available Data: What We Have from PGCB](#2-available-data-what-we-have-from-pgcb)
3. [PyPSA API Surface: The Full Toolkit](#3-pypsa-api-surface-the-full-toolkit)
4. [Framework Ecosystem: PyPSA-Earth, PyPSA-EUR, PyPSA-BD](#4-framework-ecosystem)
5. [Open-Source Power System Tools Landscape](#5-open-source-tools-landscape)
6. [Proprietary Tools Landscape](#6-proprietary-tools-landscape)
7. [Missing Data: The Gaps That Limit What We Can Build Today](#7-missing-data)
8. [What We Can Build: Analyses & Product Features](#8-what-we-can-build)
9. [Business Development: Market, Revenue, and Positioning](#9-business-development)
10. [Glossary](#10-glossary)

---

## 1. Executive Summary

Bangladesh operates one of the most under-analyzed transmission networks in South Asia. With **30+ GW of installed capacity**, a rapidly growing **1,550 MW renewable base**, two **HVDC interconnects with India**, and a national grid managed by **PGCB** (Power Grid Company of Bangladesh), the data infrastructure exists — but the analytical tooling does not.

This proposal maps what is possible at the intersection of **PyPSA** (the leading open-source power system optimizer), the **PGCB transmission and substation data** we already have, and the **business need** for a credible, data-driven power system analysis platform serving Bangladesh and the broader South Asian market.

The core thesis: **build a PyPSA-powered SaaS platform** that makes transmission-level economic dispatch, LMP (locational marginal price) analysis, renewable integration studies, and investment-grade scenario modeling accessible to IPPs, policy makers, multilateral lenders, and academic researchers — at a fraction of the cost of legacy tools like DIgSILENT or PLEXOS.

---

## 2. Available Data: What We Have from PGCB

### 2.1 Transmission Lines (`grids-formatted.csv`) — 354 records

| Field | Coverage |
|---|---|
| Line name | Endpoint names (from–to substations implied) |
| Route length (km) | All 354 lines |
| Circuit length (km) | All 354 lines |
| Number of circuits | Single / Double / Four |
| Conductor type | ACSR, AAAC, Twin/Quad Finch, Mallard, Grosbeak, etc. |
| Conductor size | MCM or mm² (some missing on switching bays) |
| Voltage level | 400 kV (29 lines), 230 kV (63 lines), 132 kV (262 lines) |

**Notable assets in this dataset:**
- 2 HVDC cross-border links to India (Bheramara–Baharampur 400 kV; Comilla N–Border 400 kV)
- Complete coverage of all three voltage tiers of the national grid
- Conductor spec data enables R/X impedance lookup from standard tables

### 2.2 Substations (`substations-formatted.csv`) — 251 records

| Field | Coverage |
|---|---|
| Substation name | All 251 |
| Operation zone | 8 zones (Dhaka, Chattogram, Cumilla, Rajshahi, Khulna, Rangpur, Sylhet, Barishal) |
| Transformer ratings (MVA) | Most substations; some switching stations show "–" |
| Total capacity (MVA) | 20 MVA to 2,250 MVA per substation |
| Ownership | PGCB (~180), BPDB, DESCO, DPDC, APSCL, private industrials |
| Voltage level | 400/230 kV, 230/132 kV, 132/33 kV |
| Grid circle | Regional grouping |

**Notable assets:**
- Major hub substations identified: Aminbazar (1,560 MVA), Meghnaghat (2,250 MVA), Kaliakoir, Korerhat, Ashuganj, Madunaghat
- Ownership layer enables multi-stakeholder analysis (who owns what capacity where)
- Transformer MVA ratings are the hard capacity ceilings for power flow

### 2.3 What This Data Directly Enables in PyPSA

| PyPSA Component | Derived From |
|---|---|
| `Bus` (one per substation) | substations-formatted.csv: name, voltage level, zone |
| `Line` (transmission line) | grids-formatted.csv: length, conductor → R/X from conductor tables |
| `Transformer` | substations-formatted.csv: voltage ratio + MVA capacity |
| `Link` (HVDC) | grids-formatted.csv: Bheramara and Comilla N cross-border entries |
| `Generator` (placeholder) | Must be added from BPDB generation unit registry |
| `Load` (zonal) | Must be added from PGCB/NLDC hourly demand data |

### 2.4 Additional Data in Repo

- **Daily substation report** (`pgcb-substation-Daily-Report-11-05-2026.xlsx`): real operational snapshot useful for model validation
- **Conductor specifications** (`Conductor-sepc-transpower.pdf`): enables R (resistance) and GMR (geometric mean radius) lookup for impedance computation
- **Network geo-map** (`network-geo-map.pdf`): geographic layout for spatial validation

---

## 3. PyPSA API Surface: The Full Toolkit

PyPSA (`pip install pypsa`) is structured around a single `pypsa.Network` object. Every analysis capability is accessed through this object or its sub-accessors.

### 3.1 Network Components

| Component | What It Models | Key Parameters |
|---|---|---|
| `Bus` | Node in the network | `v_nom`, `carrier`, `x`/`y` (geo-coordinates) |
| `Carrier` | Energy type label | `co2_emissions`, `color` |
| `Generator` | Power plant / injector | `p_nom`, `marginal_cost`, `efficiency`, `carrier`, `p_max_pu` (time-series) |
| `Load` | Demand node | `p_set` (static or time-series) |
| `Line` | AC transmission line | `x` (reactance), `r` (resistance), `s_nom` (thermal limit), `length` |
| `LineType` | Standard conductor type library | Built-in IEEE / IEC conductor specs |
| `Transformer` | Voltage-level coupling | `s_nom`, `x`, `tap_ratio` |
| `TransformerType` | Standard transformer type | Lookup table for common ratings |
| `Link` | Controllable flow: HVDC, heat, gas | `p_nom`, `efficiency`, `carrier` (multi-port capable) |
| `StorageUnit` | Battery, pumped hydro | `p_nom`, `max_hours`, `efficiency_store`, `efficiency_dispatch`, `cyclic_state_of_charge` |
| `Store` | Energy reservoir (gas, H₂, heat) | `e_nom`, `e_cyclic` |
| `ShuntImpedance` | Reactive compensation (capacitor banks, reactors) | `b` (susceptance) — critical for Bangladesh's northern grid |
| `GlobalConstraint` | System-wide CO₂ budget, minimum RE share | `sense`, `constant` |
| `Shape` | Geographic shapes for regions | GeoDataFrame integration |

### 3.2 Optimization Methods

```
n.optimize()         ← main entry point: LOPF, investment, multi-period
n.optimize.solve_model()
n.optimize.create_model()    ← returns linopy model for inspection/modification
n.optimize.add_custom_constraints()
n.lopf()             ← legacy linear OPF (still supported)
n.pf()               ← full non-linear AC power flow (Newton-Raphson)
n.lpf()              ← DC linearized power flow (fast, no solver)
```

**Solver backends supported:** HiGHS (default, free), GLPK, Gurobi, CPLEX, MOSEK, Xpress  
**Optimization formulations:**
- `linearized_dc` — DC-OPF (fast, LP, suitable for large networks)
- `ac` — Full AC-OPF (NLP, uses IPOPT or similar)
- Multi-period rolling horizon (investment + dispatch co-optimization)
- Capacity expansion with `p_nom_extendable=True` on any component

### 3.3 Statistics & Results

```python
n.statistics()                  # summary: CAPEX, OPEX, curtailment, etc.
n.statistics.capex()
n.statistics.opex()
n.statistics.curtailment()
n.statistics.capacity_factor()
n.statistics.market_value()
n.statistics.revenue()
n.statistics.withdrawal()
n.statistics.supply()
n.buses_t.marginal_price       # LMPs at every bus × every time step
n.lines_t.p0 / p1              # line flows
n.lines_t.mu_lower / mu_upper  # shadow prices → congestion rents
n.generators_t.p               # dispatch per generator
n.storage_units_t.state_of_charge
```

### 3.4 Clustering & Aggregation

```python
n.cluster                   # sub-accessor for network clustering
# k-means clustering of buses by geography or load pattern
# SpectralClustering, AgglomerativeClustering
# Reduces 251-bus BD network to any N-zone aggregate model
```

### 3.5 Visualization

```python
n.plot()                    # geographic plot via matplotlib + cartopy
n.plot.mapdraw()            # interactive folium/plotly map
n.iplot()                   # interactive plotly-based network diagram
```

### 3.6 I/O

```python
pypsa.Network.import_from_csv_folder()    # bulk CSV import
pypsa.Network.export_to_csv_folder()
pypsa.Network.import_from_netcdf()        # compressed .nc files
pypsa.Network.import_from_pandapower_net()
pypsa.Network.import_from_pypower_ppc()   # MATPOWER/PYPOWER .m cases
```

### 3.7 Sector Coupling (Advanced)

PyPSA's `Link` component with multiple ports (`bus0`, `bus1`, `bus2`, `bus3`) enables:
- **Electrolysis:** electricity → hydrogen
- **Heat pumps:** electricity → district heat
- **Gas turbines:** gas → electricity + waste heat
- **CHP plants:** gas → electricity + heat simultaneously
- **EV charging:** electricity ↔ vehicle battery

This is the backbone of PyPSA-EUR's whole-energy-system models and directly applicable to Bangladesh's proposed gas-to-power transition scenarios.

---

## 4. Framework Ecosystem

### 4.1 PyPSA-Earth

PyPSA-Earth is the **open-source global energy system model for the Global South** built on PyPSA. It is the most directly applicable framework for Bangladesh.

**Key capabilities:**
- Extracts transmission grid topology from **OpenStreetMap** (OSM) → can supplement and validate our PGCB data
- Uses **ERA5 reanalysis** (via atlite) to generate hourly solar/wind capacity factor time-series at 30km × 30km resolution
- Uses **Shared Socioeconomic Pathway (SSP)** demand projections for 2030, 2040, 2050
- Pulls **technology cost curves** from the `PyPSA/technology-data` repository
- Full Snakemake workflow: data download → network build → clustering → optimization → results

**What Bangladesh already has via PyPSA-Earth:**
- Grid topology from OSM (though less accurate than PGCB's own data)
- Renewable potential maps (solar irradiance, wind speed)
- Country-level demand projections
- Technology cost assumptions (LCOE for gas, coal, solar, wind, battery)

**PyPSA-BD (2024):** A team at the Asian Institute of Technology and IUBAT Dhaka published a **customized Bangladesh-specific PyPSA-Earth model** that:
- Uses 30 km × 30 km spatial resolution
- Projects installed capacity growing from 18.94 GW (2019) → 61.45 GW (2030) → 281.52 GW (2050)
- Models full decarbonization pathways and job creation (~6.7 million jobs by 2050)
- Open-source: directly forkable as a starting point

### 4.2 PyPSA-EUR

The European flagship model — sector-coupled, covering 37 countries. Its value to this project is architectural:
- The **most mature example** of what a national/regional PyPSA model can produce
- Demonstrates electricity + heating + hydrogen + transport coupling in a single optimization
- Technology cost database is directly reusable
- Provides the code architecture patterns for multi-year investment optimization

### 4.3 Our Strategic Position

| Source | What We Get |
|---|---|
| PGCB data (this repo) | **Ground-truth topology** — more accurate than OSM |
| PyPSA-BD (AIT/IUBAT) | **Validated scenarios** and cost assumptions for Bangladesh |
| PyPSA-Earth | **Renewable profiles + demand projections + snakemake workflow** |
| PyPSA-EUR | **Sector-coupling architecture** for future roadmap |
| Our platform | **Product layer** — UI, APIs, business logic, client-facing outputs |

We are not replicating PyPSA-BD. We are **productizing it** — wrapping the open-source research model in a platform that non-engineers can use.

---

## 5. Open-Source Tools Landscape

### 5.1 Transmission & Market Optimization

| Tool | Language | Strengths | Limitations |
|---|---|---|---|
| **PyPSA** | Python | Time-series LOPF, investment opt., sector coupling, active dev | No transient/dynamic simulation |
| **MATPOWER** | MATLAB/Octave | Proven OPF, large library of test cases, AC/DC OPF | No time-series, MATLAB dependency |
| **PowerModels.jl** | Julia | Rigorous AC-OPF, multiple formulations (SDP, SOC) | Steep Julia learning curve |
| **GridCal** | Python | GUI + API, power flow, OPF, time series, short circuit | Smaller community than pandapower |
| **PyPSA-Earth** | Python | Global coverage, renewables data pipeline, Snakemake | High complexity, steep setup |

### 5.2 Distribution & DER

| Tool | Language | Strengths |
|---|---|---|
| **pandapower** | Python | Fast load flow for large networks, IEC 60909 short circuit, state estimation |
| **OpenDSS** | C++/Python API | Industry-standard for DER hosting capacity, harmonic analysis, unbalanced 3-phase |
| **GridLAB-D** | C++ | Distribution simulation with AMI, smart grid controls |
| **Power Grid Model** | C++/Python | High-performance, developed by Alliander (Dutch DSO), handles 1M+ nodes |

### 5.3 Dynamic/EMT Simulation

| Tool | Language | Strengths |
|---|---|---|
| **PSAT** | MATLAB | Transient stability, small signal analysis |
| **Dynawo** | C++ | RTE (France) open-source dynamic simulator |
| **PowerSystems.jl** | Julia | NREL's production simulation framework |

### 5.4 Market Simulation

| Tool | Language | Strengths |
|---|---|---|
| **DEECO** (ENTSO-E reference) | Python | Day-ahead market clearing |
| **Calliope** | Python | Multi-energy system planning |
| **OSeMOSYS** | Python/GNU MathProg | Long-run capacity planning, widely used by IEA/IRENA |

**Key insight:** No open-source tool combines (a) accurate transmission topology, (b) real-time data integration, (c) a non-engineer-facing UI. That is the gap this product fills.

---

## 6. Proprietary Tools Landscape

### 6.1 Engineering/Utility Tools

| Tool | Vendor | Price (USD/yr) | Strengths | Limitation |
|---|---|---|---|---|
| **DIgSILENT PowerFactory** | DIgSILENT | $8K–$70K/user/yr | Gold standard: load flow, fault, stability, OPF | Expensive, Windows-only, no API-first design |
| **ETAP** | ETAP | $3K–$25K/user/yr | Industrial focus, arc flash, relay coordination | Same as above |
| **PSS/E** | Siemens | $5K–$30K/user/yr | Transmission planning standard in US/EU | Very steep learning curve, dated UI |
| **PSCAD** | Manitoba Hydro | $4K+/user/yr | Best-in-class EMT simulation | EMT only, not economic dispatch |
| **PowerWorld** | PowerWorld Corp | $2K–$15K/user/yr | Visual load flow, contingency analysis | Not Python-native |

### 6.2 Market/Planning Tools

| Tool | Vendor | Focus |
|---|---|---|
| **PLEXOS** | Energy Exemplar | Global market simulation, capacity planning, price forecasting |
| **Aurora** | Energy Exemplar | North American power market forecasting |
| **BID3** | AFRY | European market design testing, policy analysis |
| **PROMOD** | Hitachi ABB | Production cost modeling |
| **GE MAPS** | GE Energy | Utility-scale production cost, US-focused |

### 6.3 Strategic Observation

PLEXOS licenses start at **~$50K/yr** for a full simulation license. The same analysis — economic dispatch, congestion pricing, renewable integration — can be reproduced in PyPSA for **$0 in software costs**. The business opportunity is in the **productization** layer: data pipelines, a clean UI, validated results, and client-ready reports.

---

## 7. Missing Data

This section maps what is needed to build each class of analysis, and how severe each gap is.

### 7.1 Generation Data (Critical Gap)

| Missing Item | Impact | Potential Source |
|---|---|---|
| Generator unit list (plant name, bus, MW rating) | Cannot run any dispatch optimization | BPDB Power Generation Unit Registry (public website) |
| Fuel type per plant (gas, coal, oil, solar, hydro) | Cannot set merit order | BPDB annual report |
| Marginal cost / fuel price per generator | Cannot clear the market | BERC tariff orders, BPDB cost accounts |
| Generator minimum stable generation (p_min_pu) | Cannot model unit commitment | Engineering manuals / NLDC |
| Generator ramp rates | Cannot model intra-hour dispatch | Power plant O&M contracts |
| Capacity factors for IPPs (availability, forced outage rate) | Cannot model reliability | BPDB annual generation reports |

**Workaround available today:** Use published fuel price benchmarks (gas: ~BDT 12/m³, coal: $90–110/ton) and standard heat rates (gas CC: 7,000–8,000 BTU/kWh; coal: 9,000–10,500 BTU/kWh) to build synthetic cost curves with ±15% accuracy.

### 7.2 Load / Demand Data (Partial Gap)

| Missing Item | Impact | Potential Source |
|---|---|---|
| Hourly zonal load profiles | Cannot run time-series dispatch | PGCB NLDC hourly data (available on request); UCI dataset (PGCB Hourly Generation Dataset) |
| Load disaggregation by sector (residential/commercial/industrial) | Cannot model demand response | BPDB tariff category data |
| Spatial load distribution within zones | Cannot do nodal analysis | Census + land-use data; DESCO/DPDC billing data |
| Peak demand growth forecast by zone | Cannot do investment planning | PSMP 2016/2023 data |

**Workaround available today:** UCI Machine Learning Repository hosts the **PGCB Hourly Generation Dataset** — publicly available hourly generation and demand data that can serve as a load proxy for model calibration.

### 7.3 Transmission Physical Parameters (Moderate Gap)

| Missing Item | Impact | Potential Source |
|---|---|---|
| Bus-to-bus connectivity (which lines connect which substations) | Cannot build network topology | Must parse from PGCB grid map PDF; some derivable from line names |
| Geographic coordinates of substations | Cannot run PTDF/LODF or geographic plots | Can approximate from district-level data; some in OSM |
| Line R (resistance) values | Cannot run AC power flow | Derivable from conductor type + length (Conductor-sepc-transpower.pdf is in repo) |
| Line X (reactance) values | DC-OPF requires this | Same derivation |
| Transformer impedance (% Z) | Affects short circuit and voltage profiles | Standard IEC values by rating as fallback |
| Shunt compensation locations and sizes | Reactive power balance | PGCB substation diagrams |

**Status:** Resistance and reactance can be computed from the conductor data already in the repo. The critical missing piece is the **bus-to-bus connectivity matrix** — knowing exactly which substations each line connects. This can be partially reconstructed from line names (e.g., "Aminbazar–Meghnaghat") but requires a systematic parsing pass.

### 7.4 Market & Regulatory Data (Structural Gap)

| Missing Item | Impact | Potential Source |
|---|---|---|
| Pool purchase prices (BPDB–IPP contracts) | Needed for realistic marginal costs | BERC (Bangladesh Energy Regulatory Commission) public orders |
| Cross-border import prices (India HVDC) | Needed for Experiment 4 (see suggested-experiments.md) | BERC/BPDB annual reports |
| Ancillary service structure (frequency regulation, reserves) | Cannot model security-constrained dispatch | NLDC grid code |
| Capacity payment terms | Cannot model capacity market | BPDB/BERC contracts |
| Transmission open-access rules | Cannot model third-party access | Bangladesh Grid Code 2012 |

### 7.5 Renewables Data (Low Gap — Available via PyPSA-Earth)

| Data Item | Status | Source |
|---|---|---|
| Solar irradiance (hourly, 30km grid) | Available | ERA5 via atlite + PyPSA-Earth |
| Wind speed profiles | Available | ERA5 via atlite + PyPSA-Earth |
| Land-use constraints for RE siting | Partial | SREDA, FAO Global Land Cover |
| Offshore wind resource | Available | ERA5 + GEBCO bathymetry |
| Rooftop solar potential by district | Needs processing | NASA POWER + GIS |

### 7.6 Data Priority Matrix

```
Priority 1 (blocks all analysis):
  → Bus-to-bus connectivity (parse from grid map)
  → Generator unit list with bus assignment

Priority 2 (needed for market analysis):
  → Hourly load profiles by zone (PGCB UCI dataset)
  → Marginal costs by generator type (derive from fuel prices)

Priority 3 (needed for investment/planning):
  → Demand growth forecasts
  → Cross-border power purchase prices
  → Renewable pipeline data (SREDA)

Priority 4 (needed for product polish):
  → Substation GPS coordinates
  → Transformer impedance data
  → Demand sector disaggregation
```

---

## 8. What We Can Build

### 8.1 Immediately Buildable (With Current Data + Synthetic Costs)

**Experiment A: 8-Zone Zonal Dispatch**
- Aggregate to 8 operational zones as buses
- Assign inter-zonal capacity limits from 400 kV / 230 kV line ratings
- Run LP economic dispatch with synthetic merit-order (gas > coal > oil > import)
- Output: zonal prices, inter-zonal flows, merit-order stack charts

**Experiment B: DC-OPF on 400 kV Backbone**
- 13-bus detailed model of EHV network
- Show how LMPs diverge when lines are congested
- Map the Dhaka corridor (Aminbazar–Kaliakoir) as a known bottleneck

**Experiment C: HVDC Import Analysis**
- Model both Indian interconnects as `Link` components with external price signals
- Show optimal import volume as domestic fuel prices vary
- Directly relevant to BPDB's actual import economics

**Experiment D: 24-Hour Rolling Dispatch**
- Use PGCB UCI hourly dataset for load profile
- Run 24-period economic dispatch showing peaker activation at morning/evening peaks

### 8.2 Buildable After Priority 1+2 Data Gaps Are Closed

**Experiment E: Nodal LMP Map**
- Full 251-bus network with all substations
- Show geographic LMP heatmap — where is power cheapest and most expensive
- Identify congestion rents available to transmission owners

**Experiment F: Renewable Penetration Stress Test**
- Add solar plants at Payra, Banskhali, Sirajganj, Mymensingh
- Run dispatch at 0%, 20%, 40% renewable penetration
- Show where curtailment emerges and which lines bind

**Experiment G: Capacity Expansion Planning**
- Turn on `p_nom_extendable=True` on candidate generators and storage
- Solve multi-year investment optimization: what to build where for least-cost 2030 target

### 8.3 Advanced Platform Features (6–18 month roadmap)

| Feature | What It Does | PyPSA Mechanism |
|---|---|---|
| Contingency analysis (N-1) | Remove one line and re-dispatch | Iterate over `n.lines.index`, remove + re-solve |
| Transmission investment screening | Rank new line projects by congestion rent reduction | `p_nom_extendable=True` on candidate lines |
| Carbon pricing impact | Add CO₂ constraint and price → how does dispatch shift? | `GlobalConstraint` with `co2_limit` |
| Gas-to-power sector coupling | Model gas supply network feeding gas plants | Multi-port `Link` with gas `Bus` and `Store` |
| H₂ export potential | Model electrolysis for green hydrogen export | `Link` with hydrogen carrier |
| Battery storage dispatch | Optimal storage operation | `StorageUnit` with cycling constraints |
| Rooppur nuclear integration | Modeled as must-run baseload | `Generator` with `p_min_pu=0.9` |
| Short-circuit analysis | Fault level at each bus | pandapower integration |
| Transient stability | Generator ride-through | Dynawo or Dyna-wo (not PyPSA — separate module) |

---

## 9. Business Development

### 9.1 Market Segmentation & Target Users

#### Tier 1: IPPs and Project Developers
**Who:** Independent Power Producers, renewable energy developers (solar, wind), EPC contractors  
**Need:** Understand where to connect to the grid, what the locational value of generation is, what curtailment risk they face  
**Willingness to pay:** High — wrong siting decisions cost tens of millions USD  
**Product feature:** Interconnection screening tool — "plant my 50 MW solar here, show me expected revenue and curtailment"

#### Tier 2: Multilateral Lenders & Development Finance
**Who:** World Bank, ADB, IFC, KfW, AIIB — financing Bangladesh's $25B+ energy expansion  
**Need:** Independent technical validation of grid capacity, transmission investment justification, climate scenario analysis  
**Willingness to pay:** Very high — pay for studies, not SaaS; entry via consulting layer  
**Product feature:** Grid adequacy reports, transmission investment screener, renewable integration studies

#### Tier 3: Policy Makers & Regulators (BERC, BPDB, PGCB, MoPEMR)
**Who:** Ministry of Power, Energy, and Mineral Resources; BERC; PGCB planning department  
**Need:** Scenario modeling for power sector master plan updates, tariff reform analysis, cross-border trade policy  
**Willingness to pay:** Low direct pay; accessible via grants/donor programs (EU, USAID, UNDP)  
**Product feature:** Policy scenario dashboard — "what if we add 5 GW solar by 2030? what if Indian import price rises 20%?"

#### Tier 4: Academic Researchers
**Who:** BUET, KUET, RUET, AIT, IUT — power systems and energy economics departments  
**Need:** Validated national grid dataset, reproducible optimization models, publication-grade results  
**Willingness to pay:** Very low direct; high indirect (citations, credibility, talent pipeline)  
**Product feature:** Open data portal + research API + free academic tier

#### Tier 5: Regional Utilities (SAARC + Southeast Asia)
**Who:** Nepal Electricity Authority, Sri Lanka CEB, Myanmar MOEE, EGAT (Thailand)  
**Need:** Cross-border trade analysis, transmission planning, renewable integration  
**Willingness to pay:** Medium — SAARC energy market is nascent but growing  
**Product feature:** Multi-country network model with HVDC interconnection scenarios

### 9.2 Competitive Moat

| Moat | Description |
|---|---|
| **Data** | PGCB ground-truth topology data (more accurate than OSM) + ongoing data partnerships |
| **Domain specificity** | Built for Bangladesh / South Asia — not a generic simulation tool |
| **Language accessibility** | Results in Bengali and English; policy-readable output formats |
| **Price** | ~10x cheaper than PLEXOS for equivalent market analysis |
| **Open-source core** | PyPSA community credibility; academic trust |
| **Network** | Relationships with BPDB, PGCB, BERC as data partners + reference clients |

### 9.3 Revenue Model

```
Freemium Research API
  └─ Free for academics: 5 API calls/day, public data only
  └─ Purpose: build academic citations, validate models publicly

Professional SaaS (IPPs / Consultants)
  └─ $500–2,000/month
  └─ Full optimization runs, private scenario storage, PDF reports
  └─ Target: 20–50 paying users in first 12 months

Enterprise Contracts (Banks / Multilaterals)
  └─ $20,000–$100,000/project or $5,000–$15,000/month
  └─ Custom scenarios, dedicated compute, branded reports, on-prem option

Government Partnerships
  └─ Grant/donor funded: USAID, EU, UNDP, GIZ energy programs
  └─ Provide free access in exchange for data partnerships (real-time NLDC data)

Training & Capacity Building
  └─ PyPSA workshops for BUET, PGCB, BPDB engineers
  └─ BDT 50,000–150,000 per workshop (2 day)
```

### 9.4 Build Sequence

**Phase 0 (Now — 4 weeks): Proof of Concept**
- Close Priority 1 data gap: parse bus-to-bus connectivity from grid map PDF
- Build 8-zone Bangladesh model with synthetic costs
- Run all 6 experiments from `suggested-experiments.md`
- Create a demo notebook showing LMPs, congestion rents, HVDC import analysis

**Phase 1 (Months 1–3): Minimum Viable Product**
- Integrate PGCB UCI hourly demand dataset
- Build full 251-bus PyPSA model
- Add solar/wind profiles from PyPSA-Earth/ERA5
- Simple web UI: upload scenario → run → download results

**Phase 2 (Months 3–9): Product**
- Interactive LMP map (Folium/Mapbox)
- Renewable integration screener
- Scenario comparison (policy dashboard)
- API for programmatic access
- Pilot with 2–3 paying IPP/consultant clients

**Phase 3 (Months 9–18): Scale**
- Multi-year investment optimization module
- Carbon pricing / NDC scenario module
- Regional model: India–Bangladesh–Nepal interconnection
- Enterprise sales to multilateral lenders

### 9.5 Comparable Companies (Inspiration, not Competition)

| Company | What They Do | Lesson |
|---|---|---|
| **Open Energy Transition** (Germany) | Open-source PyPSA consulting + tooling | The research→product bridge is viable |
| **Energy Exemplar** (PLEXOS) | Enterprise simulation SaaS | $300M+ ARR; market exists |
| **Aurora Energy Research** | Power market analytics | Data + models = premium pricing |
| **SAMAWATT** | RE trading SaaS | Algorithmic market access |
| **Modo Energy** | Battery storage analytics UK | Niche but defensible market |
| **GridLens OE** (this project) | Owner's engineer platform | Existing pitch; humanitarian + national grid dual track |

---

## 10. Glossary

**AC OPF (AC Optimal Power Flow):** Full nonlinear optimization of generator dispatch subject to AC power flow equations. Captures reactive power and voltage effects but requires NLP solvers. More accurate than DC-OPF for voltage-constrained systems.

**ACSR (Aluminium Conductor Steel Reinforced):** Standard transmission line conductor. Outer aluminium strands carry current; central steel core provides tensile strength. The dominant conductor type in Bangladesh's 132 kV network.

**Atlite:** Python library that converts ERA5 climate reanalysis data into renewable energy capacity factor time-series. Used by PyPSA-Earth to generate solar and wind profiles.

**BERC (Bangladesh Energy Regulatory Commission):** Regulates tariffs, licensing, and market rules for Bangladesh's power sector.

**BPDB (Bangladesh Power Development Board):** The state-owned vertically integrated utility responsible for generation and retail distribution outside of Dhaka.

**Bus:** A node in the power system network. Represents a substation busbar. All generation, load, lines, and transformers connect to buses.

**Capacity Expansion Optimization:** Jointly optimizing which power plants and transmission lines to build and where, alongside how to dispatch them — the long-run planning problem.

**Capacity Factor:** Ratio of actual energy output to maximum possible output over a period. A solar plant with 20% capacity factor runs at full rated output only 20% of the time on average.

**Carrier:** In PyPSA, the energy type (electricity, gas, hydrogen, heat) transported by a component. Defines which energy network a component belongs to.

**Congestion Rent:** Revenue collected by a transmission system operator when a congested line creates a price difference between two nodes. Equals `(LMP_receiving - LMP_sending) × power_flow`.

**DC-OPF (DC Optimal Power Flow):** Linearized approximation of power flow that ignores reactive power and assumes small voltage angle differences. Fast, solvable as a linear program (LP). Sufficient for economic dispatch and congestion analysis.

**DESCO / DPDC:** Dhaka Electric Supply Company / Dhaka Power Distribution Company. The two distribution utilities serving Dhaka metropolitan area.

**Economic Dispatch:** Finding the least-cost combination of generators to serve a given load, subject to capacity and (if network-constrained) transmission limits.

**ERA5:** ECMWF Reanalysis v5 — the global hourly climate dataset (wind speed, solar irradiance, temperature) used as the primary data source for renewable energy potential modeling.

**HVDC (High Voltage Direct Current):** Transmission technology for long-distance bulk power transfer or asynchronous grid connections. Bangladesh has two HVDC links to India at Bheramara and Comilla North.

**IPP (Independent Power Producer):** Private electricity generator that sells power to the grid under a Power Purchase Agreement (PPA) rather than being state-owned.

**LCOE (Levelized Cost of Energy):** The present value of total lifetime cost of a power plant divided by lifetime energy generation. Used to compare technologies. Typically expressed in USD/MWh or BDT/kWh.

**Link:** In PyPSA, a controllable power flow component. Models HVDC lines, heat pumps, electrolysers, gas turbines, or any device that converts one energy carrier to another.

**LMP (Locational Marginal Price):** The price of electricity at a specific node in the network, derived from the dual variables of the power flow constraints in DC-OPF. Also called nodal price or shadow price. LMPs differ across nodes when transmission is congested.

**LOPF (Linear Optimal Power Flow):** PyPSA's core optimization: linear (DC-approximation) optimal power flow solved as a linear program. The primary tool for economic dispatch with network constraints.

**Merit Order:** Ranking of power plants from lowest to highest marginal cost. The cheapest plants run first and set the system marginal price up to the point where supply meets demand.

**MVA (Mega Volt-Ampere):** The apparent power rating of a transformer or substation. The hard thermal limit on how much power can flow through that equipment.

**N-1 Criterion:** Power system reliability standard requiring the network to remain stable following the sudden loss of any single component (one line, one transformer, one generator).

**NLDC (National Load Dispatch Center):** Operated by PGCB. Controls real-time generation scheduling and load balancing for Bangladesh's entire national grid.

**OSeMOSYS:** Open Source energy Modelling SYStem. Used by IEA and IRENA for long-run national energy planning. Less granular than PyPSA for transmission analysis.

**pandapower:** Python-based power system tool focused on distribution networks. Implements IEC 60909 short-circuit calculations, state estimation, and OPF. Complements PyPSA for distribution-level analysis.

**PGCB (Power Grid Company of Bangladesh):** The national transmission system operator (TSO). Owns and operates all 400 kV, 230 kV, and 132 kV transmission infrastructure. The source of our grid dataset.

**PSMP (Power System Master Plan):** Bangladesh's long-term power sector development roadmap. The 2016 PSMP targeted 40 GW by 2030; the 2023 update revised this for the energy transition.

**PTDF (Power Transfer Distribution Factor):** Linear sensitivity factor showing how much of a 1 MW injection at one bus flows on each transmission line. Core to linear power flow analysis.

**PyPSA (Python for Power System Analysis):** Open-source Python toolbox for simulating and optimizing modern power systems. Core components: Network, Bus, Generator, Load, Line, Link, StorageUnit, Store. Primary optimization: LOPF via `n.optimize()`.

**PyPSA-BD:** A customized PyPSA-Earth model for Bangladesh published in 2024 by AIT and IUBAT. Models decarbonization pathways to 2050 at 30 km resolution.

**PyPSA-Earth:** Extension of PyPSA for global energy system modeling. Uses OSM for grid topology, ERA5 for renewables, and SSP projections for demand. Designed for Global South countries.

**PyPSA-EUR:** The European flagship PyPSA model. Sector-coupled (electricity + heat + hydrogen + transport) across 37 countries. The architectural reference for multi-sector models.

**Reactance (X):** Imaginary part of line impedance. Determines how active power distributes across a meshed AC network. Used in DC-OPF as the primary line parameter.

**Resistance (R):** Real part of line impedance. Determines ohmic (I²R) losses. More important in AC-OPF and distribution analysis.

**Sector Coupling:** Modeling the interconnection between energy sectors — electricity, heat, gas, hydrogen, transport — in a single optimization. Enabled in PyPSA via the multi-port Link component.

**Shadow Price:** The marginal value of a constraint in an optimization problem. The shadow price of a transmission line capacity constraint equals the congestion rent. The shadow price of system load balance equals the LMP.

**Slack Bus:** The reference bus in a power flow calculation. Absorbs any system imbalance; its voltage angle is fixed at 0°. There must be exactly one per connected network.

**Snakemake:** Python workflow management tool used by PyPSA-Earth and PyPSA-EUR to define and run reproducible multi-step data pipelines.

**SREDA (Sustainable and Renewable Energy Development Authority):** Bangladesh's renewable energy regulator. Manages RE deployment targets, net metering policy, and the 40 GW renewable plan.

**StorageUnit:** PyPSA component for battery storage, pumped hydro, or any energy storage device. Characterized by power rating (MW), energy capacity (MWh), and round-trip efficiency.

**TSO (Transmission System Operator):** Entity responsible for operating and planning the high-voltage transmission grid. In Bangladesh: PGCB.

**Unit Commitment:** The binary (on/off) scheduling of generators, accounting for startup costs, minimum run times, and ramp rates. An integer programming problem, harder than LP economic dispatch.

**Y-bus (Admittance Matrix):** The nodal admittance matrix of a power network. Assembled from line impedances; used in full AC power flow (Newton-Raphson).

---

*This document was generated from the Bangladesh PGCB transmission and substation dataset, research into PyPSA / PyPSA-Earth / PyPSA-EUR documentation, and competitive landscape analysis as of May 2026.*

*Next step: build the Priority 1 data gap — bus-to-bus connectivity parsing — and run the 8-zone zonal dispatch proof of concept.*

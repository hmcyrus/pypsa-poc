# Vertical A — Network Modeling & Analysis (PyPSA): Assessment & Plan

> **Scope:** Constructing the Bangladesh power system network in PyPSA and running
> analyses — economic dispatch, DC-OPF, LMP, contingency, renewable integration,
> capacity expansion.
> **Date:** June 2026 | **Status:** Plan v1.0
> **Companions:** [Status assessment](01-project-status-assessment.md) ·
> [Vertical B plan](03-vertical-b-geo-visualization-plan.md)

---

## 1. Current State

### 1.1 What works today

- `src/line-bus-processor.py` + `src/network-builder.py` build a validated
  **304-bus / 615-line** PyPSA network from `data/pipeline/`, with isolated-bus,
  island, and consistency checks.
- The conductor reference table (18 conductor types → r/x/b per km, ampacity →
  s_nom) is implemented and documented in
  `data/pipeline/processed/processing-notes.md`.
- `pypsa_dataset.xlsx` supersedes the pipeline's raw input and adds the component
  classes the pipeline deferred: 121 transformers, 479 loads, 147 generators,
  4 HVDC links.

### 1.2 What is missing, per component class

| Component | Have | Missing | Closure path |
|---|---|---|---|
| Buses (305) | Names, v_nom, connectivity | Coordinates for ~20–25% | KMZ stitching (Vertical B feeds this back) |
| Lines (638) | bus0/bus1 all; r/x/b/s_nom for 548 | Params for 90 lines | Conductor-table defaults by voltage class |
| Transformers (121) | Bus pairs, s_nom | r/x ("typical") | Standard IEC %Z by MVA rating (e.g. 12.5% @ 100 MVA base, scaled) |
| Loads (479) | Trafo MVA | bus (parseable from name), p_set | Name parsing + UCI hourly allocation |
| Generators (147) | name, p_nom, Area (9 zones); tech for 30 | bus, marginal_cost, fuel | powerplantmatching + technology-data |
| Links (4) | Bheramara ×2, Adani | Tripura params | Public BPDB data |

---

## 2. Phase A0 — Full Network Construction (Weeks 1–2)

Successor to the current pipeline, reading from the canonical store (status doc §5).

### 2.1 Ingest upgrade

Replace `powergridlinedata.csv` ingestion with xlsx ingestion (or its CSV export into
the canonical store). Resolve the pipeline's two documented simplifications:

1. **Transformers:** stop skipping cross-voltage rows; add the 121 `gridsubs` records
   as `Transformer` components. Impedance fallback: standard IEC values by rating
   (uk ≈ 10–14% depending on MVA class; r from typical X/R ratios 20–40 at these
   ratings), flagged `impedance_source=default` for later refinement.
2. **Duplicate circuits:** keep all circuits with `_Line1/_Line2/...` suffixes
   (xlsx convention already does this); verify no residual collisions.

### 2.2 Load attachment

- Parse bus from load name: `AKSPL_230kV_Load1` → bus `AKSPL_230kV`. Validate every
  parsed bus exists; emit residual report for manual mapping.
- Static `p_set` placeholder until Phase A2: national peak (~16 GW) allocated by
  transformer-MVA share, power factor 0.95 for `q_set`.

### 2.3 Generator attachment (powerplantmatching)

```
powerplantmatching → BD fleet (name, lat/lon, fuel, capacity, year)
   │ fuzzy-match against generators sheet names (expect ~70–80% auto)
   ▼
matched: snap plant coordinate → nearest bus at appropriate voltage
         (≥100 MW → 230/400 kV preference; <100 MW → 132 kV allowed)
unmatched: fall back to zonal placement using the Area column
           (attach to the zone's highest-MVA bus, flagged provenance=zonal)
```

Cross-checks: sum of matched p_nom vs. ~30 GW installed capacity; per-Area capacity
totals vs. BPDB annual report.

### 2.4 Validation gates (extend `network-builder.py`)

- No isolated buses; single connected component (now including transformers/links —
  the current check already unions these).
- Load sum ≈ national peak; generation capacity ≥ load + reserve margin per island.
- `n.lpf()` converges on the full network (smoke test, no solver needed).
- Per-voltage-level line counts match source counts.

**Exit criterion:** a `pypsa.Network` with all six component classes that passes all
gates and solves a trivial dispatch.

---

## 3. PyPSA-Earth: Component-by-Component Adoption Decision

PyPSA-Earth is used **dismantled for parts**, called as libraries — not via its
Snakemake workflow, which is designed to bootstrap a country from nothing and would
discard the PGCB ground-truth topology in favor of inferior OSM data.

### 3.1 ADOPT — atlite + ERA5 (renewable profiles) — highest value

- Standalone library; PyPSA-Earth wrapper not needed.
- Bangladesh cutout ≈ 7°×4°: one-time CDS-API download (a few GB per weather year),
  minutes of compute.
- Produces hourly `p_max_pu` series for solar PV and wind at any coordinate —
  **enabled by the KMZ coordinates**.
- Setup: CDS account → `atlite.Cutout(module="era5", bounds=BD bbox, year=2024)` →
  `cutout.pv(...)` / `cutout.wind(turbine=..., ...)` at generator coordinates.
- Used for: existing solar fleet profiles, hypothetical plants (Payra, Banskhali,
  Sirajganj, Mymensingh), coastal wind assessment.

### 3.2 ADOPT — technology-data (costs) — cheapest gap closure

- Plain CSVs: CAPEX/OPEX, efficiencies, lifetimes per technology per year.
- Combine standard heat rates with Bangladesh fuel benchmarks
  (gas ~BDT 12/m³; coal $90–110/t; HFO/HSD from BPC postings) → synthetic marginal
  costs, ±15% accuracy, sufficient for merit order and relative LMP patterns.
- Indicative merit order to encode: hydro ≈ 0 → nuclear ~12 → gas CC ~35–45 →
  coal ~50–65 → gas OC ~55–70 → HVDC import (contract price ~60–75) → HFO ~90–120 →
  HSD ~150+ USD/MWh. Each generator gets `marginal_cost_source` provenance.

### 3.3 ADOPT — powerplantmatching (generator fleet) — see §2.3

### 3.4 PARTIAL — demand workflow

- **Take:** SSP-based projections for future-year scenarios (2030/2040 growth).
- **Skip:** hourly synthesis (UCI PGCB measured data is better for BD) and
  raster-based spatial disaggregation (479 load points with transformer MVA is
  strictly more faithful than population rasters).

### 3.5 REFERENCE ONLY — PyPSA-BD (AIT/IUBAT 2024)

Published, peer-reviewed BD scenarios at 30 km resolution. Use as a validation
benchmark for dispatch results and as a source of cost/scenario assumptions. Do not
fork the code.

### 3.6 REJECT

- **OSM grid extraction** for topology (PGCB data is ground truth; OSM retained only
  as cross-validation/gap-fill geometry for Vertical B).
- **Snakemake workflow adoption** (integration cost exceeds calling the three
  libraries directly).
- **Its clustering setup** (PyPSA's native `n.cluster` on our own network suffices
  for the 8-zone aggregate).

---

## 4. Phase A1 — Synthetic Costs & First Dispatch (Weeks 2–3)

**Experiment A — 8-zone zonal dispatch.** Cluster 305 buses to the 8 PGCB operation
zones (`n.cluster` or manual zone mapping from substation data). Inter-zonal limits
from 400/230 kV line s_nom sums. LP dispatch via `n.optimize()` (HiGHS). Outputs:
zonal prices, inter-zonal flows, merit-order stack.

**Experiment B — DC-OPF on the 400 kV backbone.** ~13-bus EHV subnetwork. Show LMP
divergence under congestion; characterize the Dhaka corridor (Aminbazar–Kaliakoir).

**Experiment C — HVDC import optimization.** Bheramara/Adani/Tripura as `Link`
components with contract-price marginal costs; sweep domestic gas price ±50%, output
optimal import volume curve.

**Exit criterion:** all three experiments produce plausible numbers (sanity-checked
against PGCB daily report dispatch shares and PyPSA-BD).

---

## 5. Phase A2 — Time Series (Weeks 3–5)

### 5.1 Load profiles

- Ingest UCI PGCB Hourly Generation Dataset → national hourly demand profile.
- Allocate to the 479 load points by transformer-MVA share (optionally refined later
  with zone-level NLDC data).
- `n.set_snapshots(...)`; `loads_t.p_set` as the (snapshots × loads) frame.

### 5.2 Experiment D — 24-hour and weekly rolling dispatch

- 24-period dispatch showing peaker activation at morning/evening peaks; weekly run
  showing weekend/weekday structure.
- Validation: dispatch mix vs. UCI measured generation shares per fuel.

### 5.3 Experiment E — Nodal LMP map (flagship)

- Full-network DC-OPF (`n.optimize()` with `linearized_dc`) over representative days.
- Outputs: `n.buses_t.marginal_price` (LMP per bus per hour), `n.lines_t.p0`
  (flows), `mu_lower/mu_upper` (congestion shadow prices → congestion rents).
- **This is the first product handoff to Vertical B** — name-keyed result tables for
  the LMP heatmap overlay.

---

## 6. Phase A3 — Renewables & Expansion (Weeks 5–8)

### 6.1 Experiment F — RE penetration stress test

- atlite profiles at candidate sites; add solar `Generator`s with hourly `p_max_pu`.
- Sweep 0/20/40% penetration; report curtailment (`n.statistics.curtailment()`) and
  binding lines per scenario.

### 6.2 Experiment G — capacity expansion

- `p_nom_extendable=True` on candidate generators/storage; CAPEX from
  technology-data; SSP-scaled 2030 demand.
- Multi-period investment optimization: least-cost build-out for a 2030 target;
  sensitivity to gas price and solar CAPEX.

### 6.3 Stretch analyses (ordered by value)

1. **N-1 contingency screening** — iterate line outages on the 400/230 kV set,
   re-solve, rank by load shed / overload (feeds Vertical B contingency view).
2. **Storage dispatch** — `StorageUnit` at solar-heavy buses, cycling economics.
3. **CO₂ constraint scenarios** — `GlobalConstraint`, carbon price sweeps.
4. **Rooppur integration** — must-run nuclear (`p_min_pu=0.9`) displacement effects.

---

## 7. Deliverables & Interfaces

### 7.1 Code layout

```
src/
  ingest/        xlsx → canonical store; validation gates
  enrich/        powerplantmatching matcher; cost synthesizer; UCI loader;
                 atlite profile builder
  network/       store → pypsa.Network builder (extends network-builder.py)
  experiments/   exp_a_zonal.py ... exp_g_expansion.py  (one runnable module each)
  results/       writers → results/<run_id>/{lmp.csv, flows.csv, loading.csv,
                 dispatch.csv, meta.json}
```

### 7.2 Result artifact contract (consumed by Vertical B)

All result tables keyed by **component name**, one file per quantity per run:

| File | Keyed by | Columns |
|---|---|---|
| `lmp.csv` | bus name | snapshot, price (USD/MWh) |
| `line_loading.csv` | line name | snapshot, p0 (MW), loading (% of s_nom) |
| `dispatch.csv` | generator name | snapshot, p (MW) |
| `meta.json` | — | run id, scenario params, solve status, timestamps |

### 7.3 Risks

| Risk | Mitigation |
|---|---|
| powerplantmatching BD coverage poor | Area-column zonal fallback keeps every experiment runnable |
| Synthetic costs misrank merit order | Validate dispatch shares vs. UCI/PGCB actuals; tune fuel prices |
| 90 unparameterized lines distort flows | Default by voltage class; sensitivity run with ±30% on defaulted values |
| CDS API queue delays | Order the cutout download in week 1; nothing before A3 depends on it |
| Full-network OPF infeasible due to data errors | Island/limit gates in A0; start from 400 kV backbone and grow |

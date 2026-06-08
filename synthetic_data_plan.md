# Synthetic Data Plan: Bangladesh Transmission Grid

> Grounded in: existing codebase, PyPSA-BD (2024), BPDB published statistics, Bangladesh
> load curve research (2024-25), synthetic-grid literature (arXiv 1706.09294, 1911.06934,
> 2107.03547), and the Lund thesis (executive summary provided by user, June 2026).
> The thesis's core contribution — constrained conditional simulation via a shape library
> under partial observability — is incorporated throughout §4 Phase C and §5.

---

## 1. What analyses this network can support

The current network — 304 buses across 132/230/400 kV, 615 lines, ~120 transformers, 2-3
HVDC Links to India — is a complete transmission skeleton. Once populated with generators,
loads, and time-series snapshots, it supports all of the following analyses, ordered from
simplest to most demanding on data quality.

### Tier 1 — Static, no time-series required

| Analysis | What you learn | Key output |
|---|---|---|
| **AC power flow** (Newton-Raphson) | Bus voltages, line loading, system losses | Voltage profile, MW losses map |
| **N-1 contingency screening** | Which single outages cause overload or islanding | Contingency ranking table |
| **Network topology metrics** | Betweenness centrality, critical corridors, weak links | Risk map |
| **Thermal limit audit** | Which lines are already near their s_nom limit at peak load | Congestion hotspot list |

### Tier 2 — Single-snapshot economic dispatch

| Analysis | What you learn | Key output |
|---|---|---|
| **DC-OPF** | Least-cost dispatch respecting line limits | Generator dispatch table, system cost |
| **Locational Marginal Prices (LMPs)** | Where is power expensive? Where is cheap generation stranded? | LMP map per bus |
| **Congestion rent** | Value locked by transmission limits | Shadow prices on binding lines |
| **Import optimization (HVDC)** | At what domestic price does Indian import improve welfare? | Import level vs domestic gas price curve |
| **Zonal price formation** | Dhaka/Chittagong/Sylhet/Khulna price divergence | Zonal price heatmap |

### Tier 3 — Multi-period dispatch (time-series)

| Analysis | What you learn | Key output |
|---|---|---|
| **24-hour rolling dispatch** | How generation stack and line flows shift across the day | Daily dispatch stack chart |
| **8760-hour annual dispatch** | Unit utilization, annual curtailment, seasonal patterns | Annual dispatch and cost summary |
| **Ramadan load shape effect** | How the shifted evening peak changes LMPs and dispatch | Before/after Ramadan dispatch comparison |
| **Renewable integration** | At what penetration does curtailment emerge? Where? | Curtailment map vs solar/wind capacity |
| **Storage dispatch** | Battery/pumped-hydro arbitrage across daily price spread | SOC trace + revenue |
| **Cross-border trade dynamics** | When does import displace domestic gas vs coal? | Import merit-order stack |

### Tier 4 — Forecasting (requires synthetic historical data)

| Analysis | What you learn | Key output |
|---|---|---|
| **Short-term load forecasting (STLF)** | 24h-ahead demand prediction per zone | Forecast accuracy (MAPE) |
| **Feature importance** | Temperature, Ramadan, day-of-week drivers | Feature importance plot |
| **Model benchmark** | ARIMA vs Random Forest vs LSTM | MAE/RMSE comparison table |
| **Probabilistic forecasting** | Prediction intervals for OPF inputs | 10/50/90 percentile load bands |
| **Renewable generation forecast** | Solar capacity factor 24h ahead | Solar forecast error distribution |

### Tier 5 — Planning & investment (longer horizon)

| Analysis | What you learn | Key output |
|---|---|---|
| **Transmission expansion** | Which new lines reduce total system cost most? | Candidate corridor ranking |
| **Generator capacity expansion** | Optimal mix (gas/coal/solar) for 2030 demand | Least-cost expansion plan |
| **Solar siting analysis** | Which 400kV buses can absorb most new solar without curtailment | Solar hosting capacity per bus |
| **Rooppur nuclear integration** | Impact of 2,400 MW baseload at Rooppur bus | Dispatch stack change |

---

## 1b. The thesis framing: constrained conditional simulation

The Lund thesis reframes load synthesis as **constrained conditional simulation**, not
noise injection. The distinction matters for everything downstream.

> "We are not recovering the truth. We are generating plausible realizations conditioned
> on known constraints."

Applied to our problem: we know *daily peak load* per substation (derived from transformer
capacity and BPDB totals). We do not know the hourly trajectory. Many different hourly
profiles are consistent with the same daily peak — the problem is underdetermined.

**The thesis's 5-step strategy (applied to our network):**

```
Step 1: Build a shape library
        Normalize historical or archetype load curves by their daily peak → shape ∈ [0,1]^24
        Condition shapes on metadata: month, day_type, zone_type

Step 2: Model P(shape | month, day_type, zone_type)
        Simple: lookup table of archetype shapes (3 day types × 12 months × 2 zone types)
        Better: Gaussian mixture or VAE over shape space

Step 3: Sample shapes
        For each bus-day: draw a shape from the conditional distribution
        Add diversity: perturb shapes by ε ~ N(0, σ=0.03 per hour)

Step 4: Scale by known peak constraint
        load_t = daily_peak_MW × shape_t
        This guarantees: max(load) = daily_peak_MW ✓

Step 5: Apply engineering constraints
        load_t >= 0 (non-negativity)
        |load_t - load_{t-1}| <= R (ramp constraint, R = 0.15 × daily_peak per hour)
        Smooth with rolling mean if needed
```

**Where our daily peaks come from** (our partial observability setup):
- National peak anchor: 17,800 MW (BPDB 2024)
- Bus-level peak: national_peak × bus_share (transformer capacity proxy, §3.2)
- Monthly peak: national_peak × seasonal_multiplier × bus_share
- These are "the observations we have" — the thesis says to condition on them faithfully.

**Hierarchical consistency** (the thesis's §7):
```
∑ bus_loads(t) = zone_load(t)          [at every hour]
∑ zone_loads(t) = national_load(t)     [at every hour]
```
Enforce top-down: generate national profile first → disaggregate to zones → disaggregate
to buses. Do not generate bus profiles independently and hope they sum correctly.

**Evaluation framework** (thesis §8) — built into Phase E validation:

| Check | Method | Pass criterion |
|---|---|---|
| Statistical similarity | Mean, variance, quantiles per bus | Within 5% of targets |
| Temporal structure | Autocorrelation at lags 1, 24, 168 | Matches archetype |
| Peak behavior | Daily max distribution | 95th percentile ≈ design peak |
| Cross-series correlation | Buses in same zone | r ≥ 0.85 |
| Hierarchical consistency | Sum buses = zone = national | Error < 0.1% at every hour |
| Diversity | Pairwise cosine distance across 365 daily shapes | σ_distance > 0.05 |
| Constraint satisfaction | load_t ≥ 0, ramp limit obeyed | Zero violations |
| Downstream utility | Run OPF — does dispatch make physical sense? | Converges, no infeasible buses |

**What the thesis warns against** (failure modes to explicitly check):
- Mode collapse: all days look the same (prevented by shape sampling + noise)
- Realistic individuals, unrealistic aggregates (prevented by hierarchical approach)
- Distribution match but wrong temporal structure (prevented by shape-library approach)
- Evaluating only with charts (prevented by the quantitative checklist above)

---

## 2. Synthetic data inventory

Each analysis tier needs specific PyPSA components. Here's what is missing and must be
synthesized.

### 2.1 Generators (`data/synthetic/generators.csv`)

PyPSA fields needed:

| Field | Description | How to get it |
|---|---|---|
| `name` | Plant identifier | From BPDB plant list |
| `bus` | Connection bus in our network | Match plant location → nearest bus |
| `carrier` | `gas`, `coal`, `oil`, `hydro`, `solar`, `wind`, `import` | BPDB fuel type |
| `p_nom` | Installed capacity (MW) | BPDB published capacity |
| `marginal_cost` | Variable cost ($/MWh) | Fuel-type heuristic (see §3) |
| `p_min_pu` | Minimum stable output as fraction | Technology default (see §3) |
| `ramp_limit_up` | Max ramp up per hour as fraction of p_nom | Technology default |
| `committable` | True for unit commitment | Only needed for Tier 3+ |
| `start_up_cost` | $/startup | Only needed for UC |

### 2.2 Loads (`data/synthetic/loads.csv` + time-series)

| Field | Description | How to get it |
|---|---|---|
| `name` | Load identifier | Derived from bus name |
| `bus` | Bus where load is attached | Only 132kV buses (HV buses are generation/transit) |
| `p_set` | Static MW demand | Allocate from system total using transformer capacity proxy |
| `q_set` | Reactive power (MVAR) | `p_set × tan(arccos(0.90))` (assume pf=0.90) |

Time-series (`data/synthetic/loads_timeseries.parquet`):

| Field | Description |
|---|---|
| Index | `DatetimeIndex`, hourly, 1 year (8760 rows) |
| Columns | One per load bus (140-160 buses) |
| Values | MW demand at each bus-hour |

### 2.3 Renewable capacity factor profiles

| File | Content |
|---|---|
| `data/synthetic/cf_solar.parquet` | Hourly solar capacity factor per solar generator, 8760h |
| `data/synthetic/cf_wind.parquet` | Hourly wind capacity factor per wind generator, 8760h |

### 2.4 Snapshots

| Use case | Snapshots needed |
|---|---|
| Static power flow / single-snapshot OPF | 1 row: peak demand scenario |
| 24-hour dispatch | 24 rows: one representative day |
| Annual dispatch (full) | 8760 rows: full year |
| Annual dispatch (sampled) | 8 × 24 = 192 rows: representative weeks |

---

## 3. Baselines, raw materials, and heuristics

### 3.1 System-level demand (the anchor)

Anchor all load synthesis to published BPDB figures:

| Statistic | Value | Source |
|---|---|---|
| Peak demand 2024 | 17,800 MW | BPDB (April 30, 2024 record) |
| Annual generation FY 2023-24 | 95,996 GWh | Bangladesh Economic Review 2024 |
| Implied annual avg load | ~10,960 MW | 95,996 GWh / 8760 h |
| System load factor | ~61.6% | 10,960 / 17,800 |
| Peak-to-trough ratio | ~1.7–1.8 | Daily curve from BPDB data |

Derived daily curve parameters (normalized 0→1, where 1.0 = peak):

```python
DAILY_LOAD_CURVE = {
    # hour: load_pu  (approximate, Bangladesh BPDB pattern)
     0: 0.62,  1: 0.58,  2: 0.56,  3: 0.55,  4: 0.55,
     5: 0.57,  6: 0.62,  7: 0.70,  8: 0.78,  9: 0.84,
    10: 0.87, 11: 0.88, 12: 0.86, 13: 0.84, 14: 0.85,
    15: 0.87, 16: 0.90, 17: 0.93, 18: 0.97, 19: 1.00,
    20: 0.98, 21: 0.92, 22: 0.82, 23: 0.71,
}
```

Three-period structure (aligns with Chattogram dataset):
- **Off-peak**: 22:00–07:59 — avg ~0.60 p.u.
- **Day peak**: 08:00–17:59 — avg ~0.86 p.u.
- **Evening peak**: 18:00–21:59 — avg ~0.97 p.u.

Seasonal multipliers (monthly, relative to annual average):

| Month | Multiplier | Driver |
|---|---|---|
| Jan–Feb | 0.88 | Cool, low cooling load |
| Mar | 0.92 | Warming |
| Apr–Jun | 1.10 | Hot season, AC peak |
| Jul–Sep | 0.97 | Monsoon, less cooling |
| Oct | 0.95 | Transition |
| Nov–Dec | 0.88 | Cool again |

Ramadan offset: shift evening peak 1.5h later, add 8% load spike in final 2h of fast
(Iftar time). Ramadan date varies by year; use a `ramadan_flag` boolean series.

Weekly pattern: Friday load is ~6% below weekday average.

Per-bus noise: add IID Gaussian ε ~ N(0, 0.04) per bus-hour to decorrelate buses.
This keeps the sum close to the target system total while giving each bus realistic
individual variation.

### 3.2 Bus-level load allocation

The fundamental problem: how to split ~17,800 MW system total across ~150 load buses.

**Primary heuristic: transformer capacity proxy**

We already have transformer data with s_nom (MVA) for each 230→132kV and 400→132kV
transformer. A substation's transformer capacity is a strong proxy for its design load —
grid planners size transformers for peak demand.

Algorithm:
1. For each 132kV bus, sum the s_nom of all transformers feeding it from 230kV or 400kV.
2. Normalize: each bus's share = its transformer capacity / total transformer capacity.
3. Multiply by system peak (17,800 MW) to get bus-level peak load.
4. Apply daily curve and seasonal multiplier to get time-series.

Edge cases:
- 132kV buses with no transformer (generator-only substations, e.g. Ghorasal, Ashuganj):
  assign zero load.
- Large industrial clusters (Chittagong port, EPZ): upweight by 20-30% if
  substation name matches known industrial zones.
- Dhaka city cluster (Aminbazar, Tongi, Demra, Siddhirganj area): ~35% of national
  demand, verify total matches.

**Secondary heuristic: zonal cross-check**

Bangladesh has 8 PGCB operational zones with rough demand shares (from BPDB annual report):

| Zone | Approx. demand share |
|---|---|
| Dhaka | ~35% |
| Chittagong | ~18% |
| Cumilla | ~10% |
| Rajshahi | ~9% |
| Khulna | ~8% |
| Sylhet | ~7% |
| Rangpur | ~8% |
| Barishal | ~5% |

Cross-check: after allocating by transformer capacity, verify that buses in each zone
sum to approximately these shares. If not, apply a zone-level correction factor.

### 3.3 Generator placement and matching

**Known plants with bus matches in our network** (directly named or substation-match):

| Plant | Fuel | Capacity (MW) | Likely bus |
|---|---|---|---|
| Ghorasal (units 1-5) | Gas | 950 | `Ghorasal_132kV` |
| Ashuganj (PP + CCPP) | Gas | 1,600 | `Ashuganj_132kV` or `_230kV` |
| Meghnaghat | Gas/LNG | 950 | `Meghnaghat_230kV` or `_400kV` |
| Siddhirganj | Gas | 335 | `Siddhirganj_132kV` |
| Haripur | Gas | 412 | `Haripur_132kV` |
| Sylhet | Gas | 330 | `Sylhet_132kV` |
| Shahjalal (Sylhet) | Gas | 330 | `Shahjalal_132kV` |
| Rampal | Coal | 1,320 | `Rampal_400kV` ← already in network |
| Payra | Coal | 1,320 | `Payra_400kV` ← already in network |
| Barapukuria | Coal | 250 | `Barapukuria_230kV` ← already in network |
| Kaptai | Hydro | 230 | `Kaptai_132kV` |
| Bheramara HVDC | Import | 500 | `Bheramara_400kV` (HVDC bus) |
| Comilla N border | Import | 500 | `ComillaNorth_400kV` (HVDC bus) |
| Rooppur (future) | Nuclear | 2,400 | `Rooppur_400kV` (add as bus) |

Unmatched plants (>100 such entries in BPDB list — many rental/IPP oil plants):
- Most small HFO/HSD plants connect at 11–33kV and aggregate into a 132kV substation.
- Strategy: aggregate by district, assign to the 132kV bus in that district.
- These are the expensive peaker units — critical for LMP spikes.

**Matching script** (`src/synthetic/match_generators.py`):
1. Load BPDB plant list (scraped or manually curated).
2. Normalize names: strip suffixes (`Power Plant`, `Ltd`, `Unit X`).
3. Exact match against `data/canonical/buses.csv` substation names.
4. Fuzzy match (Levenshtein distance ≤ 3) for remainder.
5. Manually review unmatched; assign by district lookup.
6. Output: `data/synthetic/generator_bus_map.csv`.

### 3.4 Generator cost curve heuristics

Use technology-class marginal costs. These are variable (fuel + O&M) costs only —
capacity payments are excluded for dispatch modeling.

| Carrier | Marginal cost (USD/MWh) | Rationale |
|---|---|---|
| `gas_domestic` | 18–28 | Domestic gas at regulated tariff ~$3-4/MMBTU, heat rate 9,000 BTU/kWh |
| `gas_lng` | 70–95 | Import LNG at $10-14/MMBTU, same heat rate |
| `coal` | 38–52 | International coal ~$90-110/tonne, heat rate 9,500 BTU/kWh |
| `oil_hfo` | 150–200 | Heavy fuel oil at ~$400-500/tonne, heat rate 10,500 BTU/kWh |
| `oil_hsd` | 200–250 | High-speed diesel, more expensive per unit |
| `hydro` | 2–5 | Negligible variable cost |
| `solar` | 0 | Zero variable cost |
| `wind` | 0 | Zero variable cost |
| `import_india` | 42–60 | PPA tariff with NVVN/Adani |

For uncertainty analysis, draw from uniform distributions within each range.

**p_min_pu defaults by technology:**

| Carrier | p_min_pu | Ramp limit (p.u./h) |
|---|---|---|
| Coal (steam) | 0.40 | 0.20 |
| Gas CCGT | 0.30 | 0.50 |
| Gas OCGT/ST | 0.20 | 0.80 |
| Oil (HFO rental) | 0.15 | 1.00 (fully flexible) |
| Hydro | 0.05 | 1.00 |
| Nuclear (future) | 0.70 | 0.05 (very inflexible) |
| Solar | 0.00 | 1.00 |

### 3.5 Renewable capacity factor generation

**Solar** (deterministic physics-based model, sufficient for planning studies):

```python
import numpy as np

def solar_cf(hour_of_year: np.ndarray, lat_deg: float = 23.7) -> np.ndarray:
    """
    Simplified clear-sky solar capacity factor.
    lat_deg: latitude (Dhaka=23.7, Payra=21.8, Cox's Bazar=21.4)
    """
    day = hour_of_year // 24
    hour = hour_of_year % 24
    # Solar declination
    decl = np.radians(23.45 * np.sin(np.radians(360 / 365 * (day - 81))))
    lat = np.radians(lat_deg)
    # Hour angle (-180 to +180 degrees, 0 = solar noon)
    ha = np.radians((hour - 12) * 15)
    cos_zenith = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    cf = np.clip(cos_zenith, 0, None)
    # Seasonal cloud cover factor (monsoon reduction July-Sept)
    cloud_factor = np.where((day >= 182) & (day <= 273), 0.55, 0.85)
    return cf * cloud_factor
```

Annual capacity factor ≈ 15–17% (matches Bangladesh ground data; PVGIS gives 14-16%
for Dhaka). For higher fidelity, use PVGIS API (free, no auth needed).

**Wind** (Bangladesh is currently minimal; use placeholder):
- Coastal stations (Cox's Bazar, Mongla, Kutubdia): CF = 0.22–0.28 annual mean
- Model: sine wave with 6-month period (winter = higher, monsoon = gusts but
  curtailed for safety) + daily variation
- Will matter more for future planning scenarios

### 3.6 Reactive power (Q) for AC power flow

For loads: assume power factor 0.90 lagging → q_set = p_set × tan(arccos(0.90)) ≈ 0.484 × p_set

For lines: already have b (susceptance) from conductor data — PyPSA handles reactive
power injection automatically.

For transformers: tap_ratio adjustment may be needed for voltage support. Start with
tap_ratio = 1.0 (nominal); refine if power flow fails to converge.

---

## 4. Phased implementation plan

### Phase A: Generator data (1-2 days)

**Goal**: `data/synthetic/generators.csv` — all generators matched to buses with cost data.

**Steps**:
1. Curate BPDB plant list into `data/raw/bpdb_plants.csv`
   - Columns: name, district, fuel_type, capacity_mw, owner (BPDB/IPP)
   - ~160 entries; many already scraped from Wikipedia/BPDB
2. Write `src/synthetic/match_generators.py`:
   - Fuzzy-match plant names to canonical bus names
   - Output `data/synthetic/generator_bus_map.csv` with match confidence
3. Write `src/synthetic/generators.py`:
   - Join bus map with cost heuristics
   - Output `data/synthetic/generators.csv`
4. Validate: total capacity should sum to ~25,000-28,000 MW matched to network buses

**Output schema** (`data/synthetic/generators.csv`):
```
name, bus, carrier, p_nom, marginal_cost, p_min_pu, ramp_limit_up, committable
Ghorasal_Gas_1, Ghorasal_132kV, gas_domestic, 150, 22, 0.20, 0.80, True
...
```

### Phase B: Static load snapshot (0.5 days)

**Goal**: `data/synthetic/loads_static.csv` — single peak-demand snapshot for power flow.

**Steps**:
1. Write `src/synthetic/loads.py`:
   - Load `data/canonical/transformers.csv` to get transformer s_nom per 132kV bus
   - Compute bus load = (bus_transformer_capacity / total_transformer_capacity) × 17,800 MW
   - Apply zone cross-check against 8-zone shares
   - Apply power factor for Q
2. Output: `data/synthetic/loads_static.csv`

**Output schema**:
```
name, bus, p_set_mw, q_set_mvar
Load_Aminbazar_132kV, Aminbazar_132kV, 142.3, 68.8
...
```

### Phase C: Load time-series — shape library approach (2-3 days)

**Goal**: `data/synthetic/loads_timeseries.parquet` — 8760h × N_buses load matrix that
is hierarchically consistent, statistically realistic, and diverse.

**This phase follows the thesis's 5-step strategy.**

**Step C1: Build the national load profile (top of hierarchy)**

```python
# National daily peak series (365 days):
national_daily_peak = peak_base × seasonal_multiplier(month) × weekly_factor(day_of_week)
# Where peak_base = 17,800 MW, annual total must = 95,996 GWh
# Verify: sum(national_daily_peak × 24 × load_factor) ≈ 95,996,000 MWh
```

**Step C2: Build a shape library** (`data/synthetic/shape_library.json`)

Archetype shapes (normalized 0→1, where 1.0 = daily peak) keyed by:
`(month_group, day_type, zone_type)` where:
- `month_group`: `cool` (Nov-Feb), `hot` (Mar-Jun), `monsoon` (Jul-Oct)
- `day_type`: `weekday`, `friday`, `ramadan_iftar`
- `zone_type`: `residential_urban`, `industrial_mixed`

These are the DAILY_LOAD_CURVE values from §3.1, organized as a lookup table.
This is our "shape distribution" — simple but principled.

**Step C3: Hierarchical disaggregation**

```
national_profile(8760h)
    → zone_profile(8760h) per zone, using zone demand shares (§3.2 table)
        → bus_profile(8760h) per bus, using bus share within zone (transformer capacity proxy)
```

At each level: sample shape from shape_library, scale by that level's daily peak.
This guarantees: sum(bus loads) = zone = national at every hour.

**Step C4: Add diversity (prevent mode collapse)**

Per bus per day: draw ε ~ N(0, σ=0.03) per hour, applied multiplicatively to the shape
before scaling. This means neighboring buses in the same zone have r ≈ 0.90 correlation
(not 1.0), reflecting real substation-level variation.

**Step C5: Enforce engineering constraints**

```python
# Non-negativity
profile = np.clip(profile, 0, None)
# Ramp limit: max 15% of daily peak per hour
ramp_limit = 0.15 * daily_peak
profile = enforce_ramp_limit(profile, ramp_limit)
# Smoothness: apply Gaussian kernel σ=0.5h to remove spiky artifacts
profile = gaussian_filter1d(profile, sigma=0.5)
```

**Output**: `data/synthetic/loads_timeseries.parquet`
- Wide format: rows = DatetimeIndex (8760 rows), columns = bus names
- One companion file: `data/synthetic/loads_daily_peaks.parquet` (365 × N_buses)
  — used for evaluation and for conditioning any future ML models

### Phase D: Renewable capacity factor profiles (0.5-1 day)

**Goal**: `data/synthetic/cf_solar.parquet`, `data/synthetic/cf_wind.parquet`

**Steps**:
1. Apply `solar_cf()` function above for each solar generator's latitude
2. Scale by annual target CF (use 0.16 as default for Bangladesh)
3. Wind: construct seasonal + diurnal pattern with target CF 0.24 for coastal sites
4. Output as Parquet

### Phase E: Network builder integration (1 day)

**Goal**: `src/network_builder_v2.py` — extend existing builder with generators + loads.

**Steps**:
1. After loading buses/lines/transformers (current network_builder.py logic),
   load generators and add to PyPSA network:
   ```python
   gen_df = pd.read_csv("data/synthetic/generators.csv", index_col="name")
   for name, row in gen_df.iterrows():
       n.add("Generator", name, bus=row.bus, carrier=row.carrier,
             p_nom=row.p_nom, marginal_cost=row.marginal_cost,
             p_min_pu=row.p_min_pu)
   ```
2. Load static loads; run single-snapshot DC-OPF as validation
3. If feasible (generators ≥ loads), proceed to multi-period

**Validation criteria — thesis evaluation checklist (single snapshot):**

```
[ ] Statistical: bus-level peak within 5% of transformer-capacity-derived target
[ ] Temporal: autocorrelation at lags 1, 24, 168 matches archetype shapes
[ ] Peak behavior: system daily max = 17,800 MW ± 2%
[ ] Cross-series: buses in same zone have load correlation r ≥ 0.85
[ ] Hierarchical: sum(bus loads) = zone = national at every hour (error < 0.1%)
[ ] Diversity: pairwise cosine distance across 365 national daily shapes has std > 0.05
[ ] Constraints: zero hours with load_t < 0 or ramp > ramp_limit
[ ] Downstream: DC-OPF converges; no bus LMP > 300 $/MWh; no infeasibility
```

These are not optional — a dataset that fails any of these should not proceed to analysis.
The thesis explicitly warns: "Evaluating only with charts" is a failure mode.

### Phase F: Analysis scripts (rolling, add as needed)

| Script | Snapshot horizon | New capability unlocked |
|---|---|---|
| `analysis/01_power_flow.py` | 1 snapshot (peak) | Tier 1: voltage map, line loading |
| `analysis/02_economic_dispatch.py` | 1 snapshot | Tier 2: OPF + LMPs |
| `analysis/03_daily_dispatch.py` | 24h | Tier 3: dispatch stack, unit cycling |
| `analysis/04_annual_dispatch.py` | 8760h | Tier 3: annual cost, curtailment |
| `analysis/05_load_forecasting.py` | 8760h historic | Tier 4: STLF benchmarks |
| `analysis/06_renewable_integration.py` | 8760h | Tier 3/5: solar hosting capacity |
| `analysis/07_contingency.py` | 1 snapshot | Tier 1: N-1 security |

---

## 5. Key open questions (to be resolved by the thesis)

The Lund thesis (once available) may inform:

1. **Load allocation method** — does it propose a better proxy than transformer capacity?
   (Population gravity model? Nighttime lights satellite data?)
2. **Generator cost uncertainty** — does it treat costs as stochastic or deterministic?
3. **Validation methodology** — how do you validate synthetic data against real data
   you don't have? (Structural validation, statistical tests on aggregates)
4. **Snapshot selection** — which representative days / weeks to use for sampling
   the 8760h year efficiently?
5. **Load correlation structure** — does it propose a spatial correlation model
   across buses, or treat bus loads as independent?
6. **Renewable profile quality** — does it use a physics model (like above), PVGIS,
   ERA5 reanalysis, or a purely statistical approach?

---

## 6. Directory layout (after this plan)

```
data/
├── raw/
│   ├── powergridlinedata.csv          # Existing
│   ├── powergridtransformerdata.csv   # Existing
│   └── bpdb_plants.csv                # NEW — curated plant list
├── canonical/                         # From plan.md Phase 1-3
│   ├── buses.csv
│   ├── lines.csv
│   ├── transformers.csv
│   └── conductors.csv
├── pypsa/                             # From plan.md Phase 4
│   ├── buses.csv
│   ├── lines.csv
│   ├── transformers.csv
│   └── links.csv
└── synthetic/                         # NEW — this plan
    ├── generators.csv                 # Phase A
    ├── generator_bus_map.csv          # Phase A (intermediate)
    ├── loads_static.csv               # Phase B
    ├── loads_timeseries.parquet       # Phase C
    ├── cf_solar.parquet               # Phase D
    └── cf_wind.parquet                # Phase D

src/
├── canonical_builder.py               # From plan.md
├── pypsa_translator.py                # From plan.md
├── network_builder.py                 # From plan.md
└── synthetic/
    ├── match_generators.py            # Phase A
    ├── generators.py                  # Phase A
    ├── loads.py                       # Phase B + C
    └── renewables.py                  # Phase D

analysis/
├── 01_power_flow.py                   # Phase F
├── 02_economic_dispatch.py            # Phase F
├── 03_daily_dispatch.py               # Phase F
├── 04_annual_dispatch.py              # Phase F
├── 05_load_forecasting.py             # Phase F
├── 06_renewable_integration.py        # Phase F
└── 07_contingency.py                  # Phase F
```

---

## 7. Upgrade path: from heuristic to learned generation

The plan above uses a **shape library** (deterministic archetypes + noise). This is the
right starting point: it's interpretable, data-efficient, and passes the thesis evaluation
checklist without needing training data.

The thesis surveys a full taxonomy of methods. Here is when to upgrade, in order of effort:

| Upgrade | When to use it | Thesis method |
|---|---|---|
| **SARIMA per bus** | Once you have 1+ year of real BPDB substation data | Statistical (§4) |
| **Block bootstrap** | When you have enough history to resample weeks | Bootstrapping (§4) |
| **Gaussian Mixture on shape space** | When you can cluster buses by customer type | Statistical + shape library |
| **TimeGAN / C-RNN-GAN** | When you have ≥2 years of real bus-level data | Deep generative (§4) |
| **Diffusion model** | State-of-the-art fidelity; needs significant data | Deep generative (§4) |
| **Physics-informed simulator** | If you can model individual industrial loads | Simulator-based (§4) |

The thesis's recommended progression for our situation:
1. Start with shape library (this plan) — covers "partial observability" exactly
2. Add SARIMA per zone once BPDB daily data is scraped (public dataset available)
3. Use "train on synthetic, test on real" (thesis §8 downstream utility) to validate
   that the synthetic data supports OPF and forecasting benchmarks

**The key thesis principle that constrains all upgrades:**
> Shape library or learned model — either way, `load_t = M × shape_t` must hold.
> Scaling by the known daily peak is non-negotiable. It is what makes the generation
> "conditioned on known constraints."

---

## 8. Dependency graph

```
plan.md (network structure)
    └── Phase 1-5 of plan.md (canonical → pypsa → network builder)
            └── Phase A (generators.csv) ──────────────┐
            └── Phase B (loads_static.csv) ─────────────┤
            └── Phase C (loads_timeseries.parquet) ──────┤──► Phase E (network_builder_v2)
            └── Phase D (cf_solar/wind.parquet) ──────────┘          │
                                                                      ▼
                                                            Phase F (analysis scripts)
```

Phases A and B can run in parallel with plan.md Phases 1-5 because they only read
`data/raw/` and `data/canonical/`, not the PyPSA layer.

Phase C requires Phase B (bus-level static shares).
Phase E requires plan.md to be complete AND Phases A-D.
Phase F is incremental — each script only needs the data it uses.

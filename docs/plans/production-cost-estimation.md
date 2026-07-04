# Plan: Daily Electricity Production Cost Estimation from PGCB Daily Report

**Status: not started — this document is the execution plan for a future session.**

Goal: estimate the total daily electricity production cost of the Bangladesh grid from a
PGCB/NLDC daily report workbook, using per-plant hourly generation (GenLog sheet), fuel
efficiency (heat rates) and fuel cost data — and validate the estimate against the actuals
printed in the same report.

This plan is self-contained: all workbook-layout facts below were verified by parsing
`Daily_Report_02072026.xlsx` (report date 02-07-2026; actuals are for **01-07-2026**).
The workbook is NOT committed to the repo — the user supplies it at execution time
(ask for the file or a path if it is not provided).

---

## 1. Ground truth to validate against (P1 sheet)

The report itself states the actuals the estimate must be compared to:

| Metric | Value | Where |
|---|---|---|
| Energy generated | 363.27774707 MkWh | P1 row 8; equals GenLog `Total KWH` national total (cell col 164, row 38 = 363,277,747.07 kWh) to the digit |
| Energy unserved (load shed) | 8.7 MkWh | P1 row 9 |
| Production cost per kWh | **6.331365618555227 Tk/kWh** | P1 row 13 |
| Implied total production cost | ≈ 2,299.9 M Tk/day | 363.28 MkWh × 6.3314 Tk/kWh |
| Total gas supplied to power | 970.83 MMCFD | P1 row 12 |

Success criterion: the bottom-up estimate (Σ plant energy × plant cost rate) should land
within ~±15% of 6.33 Tk/kWh, with the gap explained (see §6 caveats). The gas-fleet fuel
consumption implied by the model should be sanity-checked against 970.83 MMCFD.

## 2. Input data — workbook layout (verified)

### GenLog sheet — hourly generation per plant (primary input)
- Row 11: plant names, columns 2–219 (~165 plants).
- Row 12: rated capacity per plant as strings like `"102.000 MW"`.
- Rows 13–37: hourly MW (`00:00` … `23:00`), **irregular**: extra `19:30` row at row 33.
- Row 38: `Total KWH` — **per-plant daily energy, use this directly** (no integration
  needed). Cross-check: trapezoidal integration of the hourly rows should be close.
- Aggregate/non-plant columns to EXCLUDE from per-plant totals: col 103 `Eastern Total`,
  col 163 `Western Total`, col 164 `National Grid Total`, col 165 `Water Level`.
- Import columns (these are energy purchases, not fuel-burning plants): col 77
  `Import (Tripura)`, col 104 `Bheramara (HVDC)` (India western interconnector),
  col 109 `HVDC(Nepal)`, col 120 `Adani Power Jharkhand`.
- Duplicate plant names disambiguated by the capacity row: e.g. col 23
  `Meghnaghat CCPP(Summit)` 335 MW vs cols 24/25 both `Meghnaghat CCPP(Summit)` 583 MW.

### Forecast sheet — fuel & producer per plant
- Header rows 7–10, data from row 11. Columns: 1 Sl, 2 plant name, 3 **Fuel**
  (Gas/HFO/HSD/Coal/Solar/Wind/Hydro), 4 Producer (PDB/IPP/EGCB/RPCL/...), 5 unit config,
  6 installed MW, 7 **present (derated) capacity MW**, 8–9 actual day/evening peak MW
  (yesterday), 10–13 forecast/effective available MW (today), 14 remarks
  ("Gas shortage", "Under Major Overhauling", ...).
- Use this sheet as the primary fuel-assignment source: match Forecast plant names to
  GenLog column names (same workbook, near-identical naming).

### P2 sheet — per-plant daily energy (cross-check)
- Header row 7, data rows 11+. Columns: 2 Sl, 3 name, 5 producer, 6 unit config,
  7 present capacity MW, 8 evening-peak MW, 9 **Energy Generated kWh**, 10 remarks.
- Contains area subtotal rows (e.g. row 45 `Dhaka Area Total`) — skip when summing,
  but useful for a per-area cost breakdown.

### P3 sheet — substation peak loads (phase 2 only)
- Zone totals rows 8–14 (Eastern 10,814.12 MW: Dhaka 5,799 / Ctg 1,678 / Cumilla 1,542 /
  Mymensingh 1,079 / Sylhet 716; Western 5,075.4 MW: Khulna 1,878 / Barishal 512 /
  Rajshahi 1,574 / Rangpur 1,111; system total demand 15,889.52 MW).
- Rows 17–82: ~200 substations in FOUR side-by-side column groups of
  (Sl, Sub-station, Load MW, Time-of-peak). Some values `N/A`.

### Other sheets (secondary / validation)
- **En-Curve**: half-hourly generation by fuel bucket — columns: TIME, Gas-Public,
  Gas-Pvt, HVDC, Nepal, Tripura, Adani, Hydro, Coal, Solar, HFO-Public, HFO-Pvt,
  HSD-Public, HSD-Pvt, Wind, Shortage (data rows 4+). Use to validate the
  fuel-assignment step: modeled per-fuel energy shares must match this sheet.
- **P4**: hourly Generation / Load-Shed / Demand (rows 9–33).
- **L-Curve**: half-hourly East/West/Total generation.
- **EWIC**: hourly MW+MVAR on the 3 East–West corridors.
- **Voltage**: daily max/min kV per substation by voltage level.

## 3. Method

Per plant *i*: `cost_i = E_i × c_i` where `E_i` = daily kWh (GenLog Total KWH row) and
`c_i` = Tk/kWh cost rate. Two tiers for `c_i`:

**Tier A (primary) — explicit heat rate × fuel price:**
```
c_i [Tk/kWh] = heat_rate(tech_i, size_i) [MJ/kWh] × fuel_price(fuel_i) [Tk/MJ]  + O&M adder
```
- Technology per plant: reuse `TECH_LOOKUP` in `src/generator_builder.py` (its keys are
  the same PGCB plant-name style as GenLog, e.g. `"Kodda 300 MW PP Unit-2 (Summit)"`);
  infer the rest from name patterns (CCPP→CCGT, GTPP/Peaking→OCGT, TPP→Steam Turbine,
  engine-size unit configs like `9*18`→ICE, Solar/Wind/Hydro from fuel).
- Fuel per plant: Forecast sheet Fuel column; fall back to `FUEL_LOOKUP` in
  `generator_builder.py`.
- Imports (Tripura, Bheramara HVDC, Nepal, Adani): no heat rate — use contracted
  purchase tariffs in Tk/kWh directly.
- Solar/Wind/Hydro: variable fuel cost ≈ 0 in the fuel-cost view (see §6 scope note).

**Tier B (fallback / cross-check) — reuse `MC_REF`:** `src/generator_builder.py` already
has all-in marginal-cost anchor points in **USD/MWh** by (tech, fuel-category, size),
interpolated by `log_linear_interp(p_nom, points)`. Convert with an FX assumption.
Compute both tiers and report both.

### Parameter file (create; all values are ASSUMPTIONS to refine with sources)
`data/production-cost/fuel_params.json` — structure and starting values:
```jsonc
{
  "fx_bdt_per_usd": 120,
  "heat_rate_mj_per_kwh": {          // ≈ 3.6 / efficiency
    "CCGT": 7.0,                     // ~51% eff
    "OCGT": 10.6,                    // ~34%
    "Steam Turbine_gas": 10.0,       // ~36%
    "Steam Turbine_coal": 9.8,       // ~37%
    "ICE": 8.4                       // ~43% (HFO engines)
  },
  "fuel_price": {                    // refine against BERC/BPDB published prices
    "gas_tk_per_mj":  ...,           // from gas-for-power tariff (Tk/m3 or Tk/MMBtu)
    "hfo_tk_per_mj":  ...,           // from Tk/litre, LHV ~40.5 MJ/kg, ~0.98 kg/L
    "hsd_tk_per_mj":  ...,           // from Tk/litre, LHV ~43 MJ/kg, ~0.85 kg/L
    "coal_tk_per_mj": ...            // from USD/tonne, ~24 MJ/kg (imported bituminous)
  },
  "import_tariff_tk_per_kwh": {      // refine from BPDB annual report / news
    "adani": ..., "hvdc_india": ..., "nepal": ..., "tripura": ...
  },
  "vom_tk_per_kwh": { "default": 0.2 }   // small variable O&M adder
}
```
The executing session should fill `...` values from public sources (BPDB annual report,
BERC tariff orders, Petrobangla gas tariff for power) and record each source in the JSON
(e.g. a `"_source"` field per entry). Do NOT tune parameters to hit the 6.33 Tk/kWh
target — estimate independently, then explain the residual gap.

## 4. Deliverables (new code)

Follow the existing builder-script conventions in `src/` (standalone scripts, pandas,
header-row detection by known labels rather than fixed indices where feasible).

1. **`src/daily_report_parser.py`** — parse a QF-LDC daily-report workbook (path as CLI
   arg) into canonical CSVs under `data/pipeline/canonical/daily-reports/<data-date>/`
   (date taken from the sheet, ISO format, e.g. `2026-07-01/`):
   - `plant_generation.csv` — one row per plant: name, capacity_mw, hourly MW columns,
     total_kwh (from the Total KWH row), area (Eastern/Western from column position
     relative to the total columns), is_import flag.
   - `plant_attributes.csv` — from Forecast + P2: fuel, producer, installed/present MW,
     remarks, p2_energy_kwh.
   - `hourly_system.csv` (P4), `fuel_curve.csv` (En-Curve), `substation_peaks.csv` (P3),
     `ewic_flows.csv` (EWIC), `summary.csv` (P1 key metrics incl. the 6.331 Tk/kWh).
2. **`data/production-cost/fuel_params.json`** — as in §3.
3. **`src/production_cost_estimator.py`** — reads the canonical CSVs + params:
   - joins GenLog plants to Forecast fuel (exact match first; then normalized-string
     match; write unresolved names to a review file and maintain manual overrides in
     `data/production-cost/plant_name_overrides.json`),
   - assigns tech (TECH_LOOKUP import or name heuristics), computes Tier A and Tier B
     cost per plant, aggregates by fuel, producer type (public/IPP/import), and area,
   - writes `data/production-cost/<data-date>-production-cost.csv` (per-plant) and
     prints a summary: total Tk, Tk/kWh vs P1 target, per-fuel energy share vs En-Curve,
     implied gas consumption (MMCFD) vs P1's 970.83.

## 5. Execution checklist (for the future session)

1. Obtain the daily-report `.xlsx` from the user (not in repo). Parse with openpyxl
   (`data_only=True`) — install deps via `pip install -r requirements.txt`.
2. Write and run `daily_report_parser.py`; verify: Σ plant `total_kwh` (excl. aggregate
   cols, incl. imports) ≈ 363.28 MkWh; GenLog totals match P2 energy column per plant
   (spot-check ≥10 plants); En-Curve half-hourly totals ≈ L-Curve totals.
3. Fill `fuel_params.json` with sourced values (record sources inline).
4. Write and run `production_cost_estimator.py`; resolve plant-name mismatches until
   unmatched energy < 1% of total.
5. Validate per §1; write a short results summary (console/CSV is fine) covering:
   Tk/kWh Tier A vs Tier B vs actual 6.331, per-fuel breakdown vs En-Curve, gas check,
   and the explained residual (§6).
6. Commit scripts + params + canonical CSVs (not the xlsx) per repo conventions.

## 6. Scope notes, caveats, pitfalls

- **What "production cost" means here**: P1's 6.33 Tk/kWh is the day's *generation cost*
  as PGCB reports it. Bangladesh's full supply cost includes IPP capacity payments,
  rentals, and high renewable PPA tariffs; the fuel-cost view will differ from BPDB's
  average *purchase* cost (which is much higher, ~11–12 Tk/kWh in recent years). State
  clearly which view each number represents. If Tier A lands well below 6.33, the gap is
  likely import tariffs + O&M + the public/IPP price distinction (En-Curve's
  Gas-Public vs Gas-Pvt split helps quantify this).
- GenLog hour rows are not uniform (19:30 inserted) — irrelevant when using the
  Total KWH row, but handle it if integrating hourly values.
- Merged header cells: read plant names from row 11 only; capacity row 12 needs the
  `" MW"` suffix stripped and float-parsed.
- Several plants report generation with fuel switching (Khulna/Rupsha CCPPs appear twice
  as `(Gas)` and `(HSD)` columns) — treat each column as its own fuel.
- `N/A` strings appear in P3/Voltage; parse defensively.
- Plant name matching is the main manual effort; the `TECH_LOOKUP`/`FUEL_LOOKUP` keys in
  `generator_builder.py` already use the same naming style — reuse before inventing new
  mappings.
- Do not modify the existing tabular pipeline (`line-bus-processor.py` → …) — this is a
  parallel analysis path; only shared touchpoint is importing lookups from
  `generator_builder.py`.

## 7. Phase 2 (optional, after §5 validates)

- **Cost allocation using P3**: allocate hourly production cost to areas/substations —
  weight each substation by its P3 peak MW within its zone, scale by the P4 hourly
  demand profile, giving a per-substation share of daily cost and a peak-hour vs
  off-peak cost split (marginal plant at each hour from the merit order).
- **Feed the dispatch model**: use the same canonical CSVs to build PyPSA time series
  (`loads-p_set.csv`, generator `p_max_pu` from Forecast present capacity) and compare
  `economic_dispatch.py` results against GenLog actuals — the cost model then prices the
  *modeled* dispatch, closing the loop between the simulated and actual grid cost.
- **Multi-day ingestion**: the parser takes any QF-LDC workbook; a folder of daily
  reports yields cost/fuel-mix trends and better calibration than a single day.

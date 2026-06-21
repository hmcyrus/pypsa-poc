# Generator Data Population — Reasoning & Methodology

Generated file: `pipeline/generator_data_populated.csv`  
Source script:  `pipeline/generate_generator_data.py`  
Reference data: artifact `f62ef837-f13d-49b7-b48c-36213cc180aa`

---

## 1. Data Sources

| Source | Role |
|---|---|
| `generator-data-baseline.xlsx` | Master list of 147 Bangladesh power plants; provides PP Name, partial Technology, and p_nom. |
| `pp-fuel.xlsx` (NLDC Forecast, 16-Apr-2026) | Official National Load Dispatch Centre daily forecast sheet; provides the authoritative **Fuel** value for each plant. |
| Claude artifact `f62ef837` | Reference marginal cost table with anchor points by Technology × Fuel × capacity band. |
| Web research | Technology confirmation for ~108 plants with blank Technology in baseline (BPDB reports, company websites, ADB/AIIB project pages, energytransitionbd.org, Global Energy Monitor). |

---

## 2. Fuel Population

Fuel values were copied **exactly** from the "Fuel" column of the NLDC pp-fuel sheet.  
Name matching used three tiers:

1. **Exact match** — name identical in both sheets.
2. **Normalised match** — stripped whitespace / minor spelling variant (e.g. `Ghorasal` vs `Ghorashal`, `Shajibazar` vs `Shahjibazar`).
3. **Manual lookup** — hand-mapped from verified plant identity (e.g. `Bhola Nutan Biddut BD LTD` = NBBL plant known to appear in pp-fuel).

Fuel strings are preserved verbatim, including dual-fuel notation:

| Fuel string | Meaning |
|---|---|
| `Gas` | Natural gas (piped or RLNG) |
| `HFO` | Heavy Fuel Oil |
| `HSD` | High-Speed Diesel |
| `Coal` | Imported bituminous coal |
| `Solar` | Solar irradiance |
| `Wind` | Wind |
| `Hydro` | Run-of-river hydro |
| `Import` | Cross-border HVDC import; no local fuel |
| `Gas/HSD`, `HSD/Gas` | Dual-fuel: runs on either gas or HSD |
| `HFO/Gas` | Dual-fuel: runs on either HFO or gas |

---

## 3. Technology Population

Plants that already had Technology in the baseline (CCGT, OCGT, or ICE) were kept as-is.  
The remaining ~108 plants were classified using the following evidence hierarchy:

### 3.1 Name-pattern rules (applied first)

| Pattern in name | Technology assigned |
|---|---|
| `CCPP`, `CCGT` | CCGT |
| `GTPP`, `GT`, `Simple Cycle` | OCGT |
| `TPP` (government plant) | Steam Turbine |
| `Solar`, `PV` | Solar PV |
| `Wind` | Wind |
| `Hydro`, `Karnaphuli` | Hydro |
| `Import`, `HVDC` | Import |

### 3.2 Size + fuel rules (applied for unnamed/ambiguous plants)

| Condition | Technology assigned |
|---|---|
| ≤ 300 MW + HFO or HSD, no steam/GT signal | ICE (reciprocating engine — dominant technology for private HFO IPPs in Bangladesh) |
| > 300 MW + HFO, no CCPP/GTPP signal | ICE (large Wärtsilä multi-unit farms, e.g. Kodda 300 MW Summit confirmed) |
| Coal + any capacity | Steam Turbine |

### 3.3 Web-search confirmations (selected key plants)

| Plant | Technology | Evidence |
|---|---|---|
| Unique Meghnaghat Power Limited (UMPL) 584 MW | CCGT | GE 9HA.01 H-class GT + HRSG + ST; AIIB project page; commissioned Jan 2024 |
| JERA Meghnaghat Power Limited 718 MW | CCGT | GE 9F.03 x2 + D11 steam turbine; ADB project documents; COD Jul 2024 |
| Bhola Nutan Biddut BD LTD 220 MW | CCGT | NBBL dual-fuel CCGT (2 GT + HRSG + 1 ST); MIGA guarantee document |
| Bibiyana South 400 MW | CCGT | Mitsubishi M701F GT; BPDB state-owned; COD 2019 |
| Kodda 300 MW Summit (Unit-2) | ICE | 18× Wärtsilä reciprocating engines; Summit Group press release |
| Ashuganj 195 MW APSCL-United | ICE | "combined cycle reciprocating gas engine plant"; energytransitionbd.org |
| Patenga 50 MW Baraka | ICE | 8× Bergen reciprocating engines; Baraka Power company page |
| Sikalbaha 105 MW Baraka | ICE | 6× Wärtsilä W18V50; Baraka Power company page |
| Karnaphuli Power Ltd. 110 MW | ICE | 6× Wärtsilä W18V50; Baraka Power company page |
| Rupsha 105 MW Orion | ICE | 6× Wärtsilä W18V50; Orion Power company page |
| Hathazari 100 MW peaking | ICE | Medium-speed HFO reciprocating diesel; Sunrise Enterprise project page |
| Dohazari 100 MW peaking | ICE | Same technology as Hathazari |
| Chandpur 200 MW Desh Energy | ICE | 12× Wärtsilä W18V50; Global Energy Monitor |
| Confidence Bagura 113 MW (×2) | ICE | Bergen 6-unit reciprocating; Confidence Power Rangpur confirmed same series |
| Confidence Rangpur 113 MW | ICE | Bergen reciprocating; energytransitionbd.org |
| Energypac Thakurgaon 115 MW | ICE | HFO reciprocating; energytransitionbd.org |
| Barisal 307 MW (BEPCL) | Steam Turbine | Ultra-supercritical (USC) coal thermal; Global Energy Monitor |
| Saidpur 150 MW Simple Cycle | OCGT | Siemens SGT5-2000E gas turbine; Siemens Energy press release |
| Shahjibazar 100 MW GTPP | OCGT | GE LMS100 aeroderivative gas turbine; GE Vernova case study |
| Chattogram TPP | Steam Turbine | Old BPDB gas-fired steam turbine plant |
| Siddhirgonj 210 MW TPP | Steam Turbine | Old BPDB gas-fired steam plant (TPP = Thermal Power Plant) |

---

## 4. Marginal Cost Methodology

### 4.1 Reference anchor points

From artifact `f62ef837`:

| Technology | Fuel | Anchor points (MW → USD/MWh) |
|---|---|---|
| CCGT | Gas | 200→24.1, 350→21.6, 450→20.5 |
| CCGT | Liquid | 200→37.6, 350→34.4, 450→31.8 |
| OCGT | Gas | 50→40.6, 100→37.5, 200→35.1 |
| OCGT | Liquid | 50→72.8, 100→64.9, 200→58.4 |
| ICE | Gas | 10→37.2, 50→34.0, 100→31.3 |
| ICE | Liquid | 10→46.9, 50→43.0, 100→40.6 |
| Steam Turbine | Gas | 100→39.9, 300→36.6, 600→33.6 |
| Steam Turbine | Liquid | 100→55.0, 300→50.1, 600→46.2 |
| Steam Turbine | Coal | 100→28.8, 300→26.1, 600→23.3 |
| Hydro | — | constant 1.5 |
| Solar PV / Wind | — | constant 0.0 |

### 4.2 Interpolation / extrapolation formula

**Log-linear interpolation** between anchor points:

```
log_cost(p) = log_cost(p1) + [log(p) - log(p1)] / [log(p2) - log(p1)] × [log_cost(p2) - log_cost(p1)]
```

This reflects the engineering reality that marginal cost declines with capacity due to economies of scale but with **diminishing returns** (concave in linear space, linear in log–log space).

**Extrapolation** (for plants outside the anchor range):
- Below minimum anchor: extrapolate using the slope of the lowest two anchor points.
- Above maximum anchor: extrapolate using the slope of the highest two anchor points.

Examples of extrapolated plants:
- `JERA Meghnaghat 718 MW` (CCGT Gas): above 450 MW anchor → extrapolated to **$18.60/MWh**
- `Unique Meghnaghat 584 MW` (CCGT Gas): above 450 MW anchor → extrapolated to **$19.42/MWh**
- `Payra 1320 MW` (Steam Coal): above 600 MW anchor → extrapolated to **$20.68/MWh**
- `Rampal 1320 MW` (Steam Coal): above 600 MW anchor → extrapolated to **$20.68/MWh**
- `Haripur GTPP 20 MW` (OCGT Gas): below 50 MW anchor → extrapolated to **$45.09/MWh**

### 4.3 Fuel category mapping

| Sheet fuel | Reference category | Notes |
|---|---|---|
| Gas | Gas | Pipeline gas / RLNG |
| HFO | Liquid (as-is) | Heavy fuel oil |
| HSD | Liquid × 1.10 | HSD is more refined; ~10% premium over HFO reference to reflect higher fuel cost per MWh |
| Coal | Coal | |
| Solar | Solar → 0.0 | Zero variable cost |
| Wind | Wind → 0.0 | Zero variable cost |
| Hydro | Hydro → 1.5 | Near-zero O&M only |
| Import | — | No marginal cost assigned |

**HSD premium rationale**: HSD is refined from the same crude as HFO but goes through additional processing, making it approximately $100–150/MT more expensive than HFO at international market prices. Given similar energy densities (~42–43 GJ/MT for HSD vs. ~40–41 GJ/MT for HFO) and similar thermal efficiencies at the turbine, this translates to roughly 8–12% higher fuel cost per MWh generated. A 10% premium is used as a central estimate.

### 4.4 Dual-fuel plants

For plants with dual-fuel designation (e.g. `Gas/HSD`):
- **Both** marginal cost columns are populated independently using the respective fuel category.
- The plant's capacity (p_nom) is used for both calculations.
- This represents the cost of operating the plant under each fuel mode.

Example — `Sirajgonj 225 MW CCPP Unit-1` (CCGT, Gas/HSD, 214 MW):
- `marginal_cost_gas` = CCGT + Gas interpolation at 214 MW = **$23.78/MWh**
- `marginal_cost_hsd` = CCGT + Liquid at 214 MW × 1.10 = **$40.92/MWh**

### 4.5 Zero-capacity plant

`Moulvibazar 10 MW Solar Power Plant` has p_nom = 0 in the baseline. Since p_nom ≤ 0, no marginal cost is calculated. This likely indicates the plant is not yet operational or its capacity is under construction.

---

## 5. Notable Data Observations

1. **Siddhirgonj capacity apparent swap**: In the baseline, `Siddhirgonj 210 MW TPP` shows p_nom = 115 MW while `Siddhirgonj 2*120 MW GTPP` shows p_nom = 210 MW. These appear transposed but were left as-is (p_nom not modified per task instructions). Technology was assigned based on name, not capacity.

2. **United Payra Power Ltd.** (HFO, 150 MW): Listed with a marginal_cost entry of "2.0" in the original baseline — this was not used in the output as it appears to be an erroneous old entry. The calculated value of ~$39.5/MWh (ICE + Liquid at 150 MW) is used instead.

3. **Large ICE extrapolation**: Several HFO ICE plants exceed the 100 MW reference maximum (e.g. Anwara 300 MW, Kodda 300 MW, Desh Energy Chandpur 200 MW). Costs are extrapolated downward using the 50→100 MW slope. The reference acknowledges ICE plants do not scale as efficiently beyond ~100 MW per single engine — at these capacities, plants use multiple parallel engine strings (e.g. Kodda 300 MW uses 18 × Wärtsilä units), so the efficiency is determined per-engine, not aggregate. The extrapolated aggregate cost may be slightly conservative (actual may be marginally higher due to operational overhead).

4. **Import plants**: `Import (Tripura)`, `Bheramara (HVDC)`, `HVDC(Nepal)`, and `Adani Power Jharkhanda Ltd` represent cross-border power imports. Technology = "Import", all marginal cost columns are blank. Actual import costs depend on bilateral power purchase agreements and are not modelled here.

---

## 6. Output Column Definitions

| Column | Description |
|---|---|
| PP Name | Power plant name (from baseline, unchanged) |
| Technology | Generator technology: CCGT, OCGT, ICE, Steam Turbine, Solar PV, Wind, Hydro, Import |
| Fuel | Fuel type(s) from pp-fuel sheet (exact values, dual-fuel separated by `/`) |
| Present Capacity (MW)/p_nom | Installed/derated capacity in MW (from baseline, unchanged) |
| marginal_cost_gas | Variable cost in USD/MWh when running on gas |
| marginal_cost_hfo | Variable cost in USD/MWh when running on HFO |
| marginal_cost_hsd | Variable cost in USD/MWh when running on HSD (includes 10% premium over HFO reference) |
| marginal_cost_coal | Variable cost in USD/MWh when running on coal |
| marginal_cost_solar | Variable cost in USD/MWh for solar (0.0) |
| marginal_cost_wind | Variable cost in USD/MWh for wind (0.0) |
| marginal_cost_hydro | Variable cost in USD/MWh for hydro (1.5) |

Single-fuel plants have exactly one marginal cost column populated.  
Dual-fuel plants have exactly two marginal cost columns populated.  
Import plants and the zero-capacity solar plant have no marginal cost columns populated.

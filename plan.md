# Data Pipeline Restructuring Plan

## Goal

Restructure the data pipeline to achieve a true canonical (backend-agnostic) vs
implementation-dependent (PyPSA) separation, integrate transformer data, and
produce a fully connected Bangladesh grid model across 132/230/400 kV.

**Two raw data sources:**
- Line data: 646 transmission line entries (existing `powergridlinedata.csv`)
- Transformer data: ~120 substation transformer entries (new, pasted from Excel)

---

## Directory Layout (After)

```
data/
├── raw/                              # Source of truth (manual preprocessing)
│   ├── powergridlinedata.csv         # MOVED from data/pipeline/raw/
│   └── powergridtransformerdata.csv  # NEW — transformer data from Excel paste
├── canonical/                        # NEW — physical reality, no derived params
│   ├── buses.csv
│   ├── lines.csv
│   ├── transformers.csv
│   └── conductors.csv               # Reference table (decoupled from code)
├── pypsa/                            # NEW — replaces pipeline/pypsa-components/
│   ├── buses.csv
│   ├── lines.csv
│   ├── transformers.csv
│   └── links.csv
├── pipeline/                         # Deprecated — kept for reference
│   └── (existing files, untouched)
└── grids-substations-data-pgcb/      # Historical — iteration 1, untouched
```

Scripts:
```
src/
├── canonical_builder.py              # NEW — raw → canonical
├── pypsa_translator.py               # NEW — canonical → pypsa
├── network_builder.py                # MODIFIED — add transformers + links
├── line-bus-processor.py             # Deprecated — kept for reference
└── network-builder.py                # Deprecated — kept for reference
```

---

## Phase 1: Save Transformer Raw Data

Save the Excel-pasted transformer data as `data/raw/powergridtransformerdata.csv`.
Same 3-row header convention as the line data:

```
Row 3 contains the names of relevant pypsa variables
Transformer Name,Start Bus,End Bus,Trafo Res (pu),Trafo Reac (pu),Nominal Capacity (MVA)
name,bus0,bus1,r,x,s_nom
Purbasadipur_230by132_T1,Purbasadipur_230kV,Purbasadipur_132kV,,,300
...
```

**Data characteristics (~120 entries):**
- Covers 40+ substations across 400/230, 400/132, and 230/132 kV boundaries
- `s_nom` (MVA) provided for all entries: ranges from 125 to 1000 MVA
- `r` (pu) almost entirely empty — will use standard defaults
- `x` (pu) almost entirely empty (one entry says "typical") — will use defaults
- 1 duplicate: `Kachua_230by132_T1` appears twice (same attributes)
- Naming convention: `{Substation}_{vHV}by{vLV}_T{n}`

**New buses introduced by transformer data:** Some transformer buses may not
appear in the line data (e.g. buses that only connect to transformers, not
transmission lines). These must be added to the canonical bus list.

---

## Phase 2: Canonical Data Schema

### 2.1 `data/canonical/buses.csv`

Physical bus identity only. No derived parameters.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Unique ID, e.g. `Aminbazar_400kV` |
| `v_nom` | float | Nominal voltage in kV |
| `substation` | str | Physical location without voltage suffix, e.g. `Aminbazar` |

**Bus sources:** Union of all unique bus names from:
1. `bus0` and `bus1` columns of line data
2. `bus0` and `bus1` columns of transformer data

`substation` is derived by stripping the `_\d+kV` suffix (including `_\d+kV_DC`
variants). This groups multi-voltage buses at the same physical location.

### 2.2 `data/canonical/lines.csv`

Physical line attributes only. No impedance derivation.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Unique line identifier |
| `bus0` | str | Sending-end bus |
| `bus1` | str | Receiving-end bus |
| `length_km` | float | Physical line length |
| `conductor` | str | Conductor type (FK to conductors.csv) |
| `v_nom` | float | Voltage level in kV (from bus names) |

**Key difference from current `processed/lines.csv`:** no `r`, `x`, `b`, `s_nom`.
These are derived in the PyPSA translation step.

**Handling of cross-voltage lines from line data (15 rows):**
Now that we have actual transformer data, the 15 cross-voltage entries in the line
data fall into two categories:

1. **Inter-area cross-voltage transmission lines** (long, >15 km): These are
   real transmission lines that happen to connect buses at different voltage levels.
   Examples: Rampal_400kV→Gopalganj_132kV (96.7 km), BoguraWest_400kV→Barapukuria_230kV
   (112 km). These are kept in canonical lines but flagged as `cross_voltage` and
   will be modeled as PyPSA Links.

2. **Short cross-voltage connections** (≤15 km): These likely represent the
   same physical connection already captured in the transformer data. Cross-reference
   against transformer entries — if both endpoints share a substation with a
   transformer between those voltage levels, drop the line entry to avoid
   double-counting.

### 2.3 `data/canonical/transformers.csv`

Substation transformers from the dedicated transformer raw data.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Unique identifier, e.g. `Aminbazar_400by230_T1` |
| `bus_hv` | str | High-voltage side bus |
| `bus_lv` | str | Low-voltage side bus |
| `v_hv` | float | HV-side nominal voltage (kV) |
| `v_lv` | float | LV-side nominal voltage (kV) |
| `s_nom_mva` | float | Rated apparent power (MVA) — from source data |
| `r_pu` | float | Resistance in per-unit (if provided, else empty) |
| `x_pu` | float | Reactance in per-unit (if provided, else empty) |

~120 entries. The `r_pu` and `x_pu` columns preserve whatever the source data
provides (mostly empty). The PyPSA translator fills defaults.

**Transformer coverage by voltage transition:**

| Transition | Approx. count | Example substations |
|------------|---------------|---------------------|
| 400/230 kV | ~22 | Aminbazar, Meghnaghat, Bhulta, Kaliakoir, Korerhat |
| 400/132 kV | ~14 | GopalganjNorth, Kaliakoir, Payra, Rahanpur |
| 230/132 kV | ~84 | Most substations — this is the workhorse transition |

### 2.4 `data/canonical/conductors.csv`

Reference table, extracted from the current hardcoded dict in line-bus-processor.py.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Conductor identifier |
| `r_per_km` | float | Resistance per km (ohm/km) |
| `x_per_km` | float | Reactance per km (ohm/km) |
| `b_per_km` | float | Susceptance per km (S/km) |
| `ampacity` | float | Current carrying capacity (A) |

18 rows. Decoupled from code — adding a new conductor requires only a CSV edit.

---

## Phase 3: `src/canonical_builder.py` — Raw to Canonical

Reads both raw CSVs and produces the four canonical files. No impedance calculations.

### 3.1 Bus extraction

Collect unique bus names from BOTH raw files:
- Line data: `bus0` and `bus1` columns (same as current processor)
- Transformer data: `bus0` and `bus1` columns (NEW source)
- Parse `v_nom` from name via `(\d+(?:\.\d+)?)kV` regex
- Derive `substation` by stripping voltage suffix
- Warn on names with unparseable voltage
- Report how many buses are line-only, transformer-only, or both

### 3.2 Line processing

- Skip rows with missing `name`, `bus0`, or `bus1`
- Normalize conductor names (2 alias mappings)
- Skip lines with unknown conductor type
- **Duplicate handling:**
  - Compare bus0, bus1, length, conductor across rows with the same name
  - Truly identical rows → keep one, log as source-data duplicate
  - Different attributes → auto-rename by appending `_dup2`, `_dup3`
- **Cross-voltage line handling:**
  - If length ≤15 km AND a transformer exists between those voltage levels at a
    shared substation → drop (already covered by transformer data), log decision
  - If length >15 km → keep in lines, add a `cross_voltage: true` flag
  - All others → keep in lines, add `cross_voltage: true` flag
- Output: physical attributes only (name, bus0, bus1, length_km, conductor, v_nom)

### 3.3 Transformer processing

- Read transformer raw CSV (skip 3-row header)
- Parse `v_hv` and `v_lv` from bus names
- Orient: ensure bus_hv is the higher voltage side
- Handle the 1 known duplicate (`Kachua_230by132_T1`) — drop identical copy
- Preserve `r_pu` and `x_pu` where provided (almost all empty)
- Output: name, bus_hv, bus_lv, v_hv, v_lv, s_nom_mva, r_pu, x_pu

### 3.4 Conductor reference export

Write the 18-entry conductor table to `data/canonical/conductors.csv`.

### 3.5 Output summary

Print counts and filtering decisions. Write `data/canonical/build_log.json`:
- Timestamp, raw file hashes
- Bus count (total, line-only, transformer-only, both)
- Line count (kept, duplicates handled, cross-voltage routed)
- Transformer count (kept, duplicates dropped)

---

## Phase 4: `src/pypsa_translator.py` — Canonical to PyPSA

Reads canonical CSVs and produces PyPSA-ready component files.

### 4.1 Bus translation

- Set `name` as index, keep `v_nom`
- Drop `substation` (not a PyPSA Bus attribute)
- Exclude buses with unparseable voltage
- Write to `data/pypsa/buses.csv`

### 4.2 Line translation

- Read `data/canonical/lines.csv` and `data/canonical/conductors.csv`
- Join on `conductor` column
- For same-voltage lines: compute derived electrical parameters:
  - `r = r_per_km * length_km`
  - `x = x_per_km * length_km`
  - `b = b_per_km * length_km`
  - `s_nom = sqrt(3) * v_nom * ampacity / 1000`
- Set `name` as index
- Output columns: `bus0, bus1, length, r, x, b, s_nom`
- Write to `data/pypsa/lines.csv`

Cross-voltage lines (flagged in canonical) are handled separately — see 4.4.

### 4.3 Transformer translation

- Read `data/canonical/transformers.csv`
- Apply default electrical parameters where source data is empty:
  - `x`: use 0.1 pu (standard for power transformers at these ratings)
  - `r`: use 0.01 pu (typical copper losses)
- Map to PyPSA Transformer attributes:
  - `bus0` = bus_hv
  - `bus1` = bus_lv
  - `s_nom` = s_nom_mva
  - `x` = x_pu (from data or default)
  - `r` = r_pu (from data or default)
  - `tap_ratio` = 1.0 (nominal, no off-nominal tap initially)
  - `type` = "" (custom parameters, not from PyPSA standard types library)
- Set `name` as index
- Write to `data/pypsa/transformers.csv`

### 4.4 Cross-voltage line translation (Links)

For the 2-3 long cross-voltage transmission lines kept from line data:
- Model as PyPSA `Link` (controllable, direction-agnostic power transfer)
- Parameters:
  - `bus0` = higher-voltage bus
  - `bus1` = lower-voltage bus
  - `p_nom` = estimated from conductor ampacity and lower voltage
  - `efficiency` = 0.98 (2% loss estimate)
  - `length` = length_km
- Write to `data/pypsa/links.csv`

### 4.5 Output

- `data/pypsa/buses.csv` (index=name)
- `data/pypsa/lines.csv` (index=name)
- `data/pypsa/transformers.csv` (index=name)
- `data/pypsa/links.csv` (index=name)

---

## Phase 5: Update `src/network_builder.py`

### 5.1 Point to new directories

Change `PYPSA_DIR` from `data/pipeline/pypsa-components` to `data/pypsa`.

### 5.2 Load new components

Add loading for transformers and links after existing bus/line loading:

```python
trafo_path = PYPSA_DIR / "transformers.csv"
if trafo_path.exists():
    trafos_df = pd.read_csv(trafo_path, index_col="name")
    for name, row in trafos_df.iterrows():
        n.add("Transformer", name, bus0=row["bus0"], bus1=row["bus1"],
              s_nom=row["s_nom"], x=row["x"], r=row["r"],
              tap_ratio=row.get("tap_ratio", 1.0))

links_path = PYPSA_DIR / "links.csv"
if links_path.exists():
    links_df = pd.read_csv(links_path, index_col="name")
    for name, row in links_df.iterrows():
        n.add("Link", name, bus0=row["bus0"], bus1=row["bus1"],
              p_nom=row["p_nom"], efficiency=row["efficiency"])
```

### 5.3 Update connectivity check

The current `check_network_correctness` already handles transformers and links
in its isolated-bus check (lines 79-82) and connected-component analysis.
With ~120 transformers bridging 400/230/132 kV, the network should now report
1 connected sub-network instead of 3 disconnected voltage-level islands.

### 5.4 Enhanced summary

Add to printed output:
- Transformer count and breakdown by voltage transition
- Link count
- Voltage-level connectivity report: which transitions are bridged

---

## Phase 6: Validation

### 6.1 Run the full pipeline

```bash
python src/canonical_builder.py    # raw → canonical
python src/pypsa_translator.py     # canonical → pypsa
python src/network_builder.py      # build + validate
```

### 6.2 Acceptance criteria

1. **Canonical files are backend-agnostic:** `data/canonical/` contains no
   PyPSA-derived impedance values for lines, no PyPSA formatting conventions.
   Transformer r/x are stored as-is from source (mostly empty).
2. **PyPSA files are complete:** `data/pypsa/` has buses, lines, transformers,
   links — all with `name` as index and all electrical parameters filled.
3. **Network is connected:** `check_network_correctness` reports 1 sub-network.
4. **No data loss vs current pipeline:**
   - Line count ≥615 (same or more if duplicates properly resolved)
   - Bus count ≥304 (same or more with transformer-only buses added)
   - Transformer count ≈119 (from dedicated transformer data)
   - Link count ≈2-3 (from long cross-voltage transmission lines)
5. **Conductor table decoupled:** Adding a new conductor = CSV edit only.
6. **Backward compatibility:** `data/pipeline/` and old scripts untouched.

### 6.3 Regression check

Compare `data/pypsa/lines.csv` against `data/pipeline/pypsa-components/lines.csv`
— impedance values must be identical for the 615 lines common to both.

---

## What This Plan Does NOT Cover (Future Work)

- **Generators** — power plants with capacity, fuel type, cost curves
- **Loads** — demand profiles per bus, time-series
- **Snapshots** — hourly/sub-hourly time-series for dispatch and forecasting
- **Storage** — batteries, pumped hydro for renewable integration
- **Geolocation** — bus x/y coordinates (satellite-based detection in task-pipeline)
- **Per-unit conversion** — currently using absolute ohms for lines; may need
  per-unit for power flow convergence

These are prerequisites for economic dispatch and load forecasting use cases.

---

## File-Level Change Summary

| Action | File | Description |
|--------|------|-------------|
| MOVE | `data/pipeline/raw/powergridlinedata.csv` → `data/raw/` | Promote to top-level |
| CREATE | `data/raw/powergridtransformerdata.csv` | Transformer data from Excel |
| CREATE | `data/canonical/buses.csv` | Physical bus data (name, v_nom, substation) |
| CREATE | `data/canonical/lines.csv` | Physical line data (no impedances) |
| CREATE | `data/canonical/transformers.csv` | Transformer data (s_nom, optional r/x pu) |
| CREATE | `data/canonical/conductors.csv` | 18-entry conductor reference table |
| CREATE | `data/canonical/build_log.json` | Pipeline run metadata |
| CREATE | `data/pypsa/buses.csv` | PyPSA-ready buses |
| CREATE | `data/pypsa/lines.csv` | PyPSA-ready lines with computed impedances |
| CREATE | `data/pypsa/transformers.csv` | PyPSA Transformer components |
| CREATE | `data/pypsa/links.csv` | PyPSA Link components (long cross-voltage) |
| CREATE | `src/canonical_builder.py` | Raw → canonical pipeline |
| CREATE | `src/pypsa_translator.py` | Canonical → PyPSA pipeline |
| MODIFY | `src/network_builder.py` | Add transformers, links, new PYPSA_DIR path |
| KEEP | `data/pipeline/*` | Deprecated, preserved for reference |
| KEEP | `src/line-bus-processor.py` | Deprecated, preserved for reference |
| KEEP | `src/network-builder.py` | Deprecated, preserved for reference |

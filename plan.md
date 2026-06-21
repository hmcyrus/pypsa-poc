# Data Pipeline Restructuring Plan

## Goal

Restructure the data pipeline to achieve a true canonical (backend-agnostic) vs
implementation-dependent (PyPSA) separation, integrate transformer and link
data, and produce a fully connected Bangladesh grid model across 132/230/400 kV.

**Raw data source: `pypsa_dataset.xlsx`** (replaces all previous raw CSVs in
the repo — `data/pipeline/raw/powergridlinedata.csv` is no longer used as input).
Relevant sheets:

- `lines` — 639 transmission line entries (line data)
- `gridsubs` — 121 substation transformer entries (transformer data)
- `links` — 4 HVDC / cross-border import links (link data)

All sheets follow the same 3-row header convention: row 1 is a note, row 2 has
human-readable column labels, row 3 has the PyPSA variable names; data starts
at row 4.

---

## Directory Layout (After)

```
data/
├── raw/                              # Source of truth (manual preprocessing)
│   └── pypsa_dataset.xlsx            # NEW — single raw workbook (lines, gridsubs, links sheets)
├── canonical/                        # NEW — physical reality, no derived params
│   ├── buses.csv
│   ├── lines.csv
│   ├── transformers.csv
│   ├── links.csv
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

## Phase 1: Save Raw Workbook

Save the uploaded workbook as `data/raw/pypsa_dataset.xlsx`. The canonical
builder reads the `lines`, `gridsubs`, and `links` sheets directly from it
(`pandas.read_excel`, `skiprows=3`).

### Line data (`lines` sheet, 639 entries)

Columns: `name, bus0, bus1, length (km), conductor, r, x, b, s_nom`.

- `length` and `conductor` provided for all rows
- `r`/`x`/`b`/`s_nom` are filled for ~547 rows but are **not used** (decision:
  derive all electrical parameters from the conductor table — the sheet values
  are per-km figures, not totals, and `s_nom` holds the voltage level rather
  than an MVA rating)
- 17 conductor types referenced
- Contains duplicate names and cross-voltage rows — see
  [Known Data Issues](#known-data-issues-for-manual-review)

### Transformer data (`gridsubs` sheet, 121 entries)

Columns: `name, bus0, bus1, r (pu), x (pu), s_nom (MVA)`.

- Covers substations across 400/230, 400/132, and 230/132 kV boundaries
- `s_nom` (MVA) provided for all entries: ranges from 125 to 1000 MVA
- `r` (pu) entirely empty — will use standard defaults
- `x` (pu) empty except one entry saying "typical" — will use researched
  typical values (see 4.3)
- Naming convention: `{Substation}_{vHV}by{vLV}_T{n}`
- One name collision (`Kachua_230by132_T2` used for a Hathazari row) — see
  [Known Data Issues](#known-data-issues-for-manual-review)

### Link data (`links` sheet, 4 entries)

Columns: `name, bus0, bus1, p_nom (MW), p_min_pu, marginal_cost`.

| name | bus0 | bus1 | p_nom | p_min_pu |
|------|------|------|-------|----------|
| BheramaraHVDC_Link1 | BheramaraHVDC1_400kV_DC | BheramaraHVDC_230kV | 500 | 1 |
| BheramaraHVDC_Link2 | BheramaraHVDC2_400kV_DC | BheramaraHVDC_230kV | 500 | 1 |
| AdaniPP_Link1 | AdaniPPSendBus_400kV | AdaniPPRecvBus_400kV | 1435 | 1 |
| TSECLSuryamaninagar_Link1 | SuryamaninagarSendBus_132kV | SuryamaninagarRecvBus_132kV | 192 | 1 |

**New buses introduced by transformer and link data:** Some buses appear only
in the `gridsubs` or `links` sheets (e.g. HVDC send/receive buses). These must
be added to the canonical bus list.

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
1. `bus0` and `bus1` columns of the `lines` sheet
2. `bus0` and `bus1` columns of the `gridsubs` sheet
3. `bus0` and `bus1` columns of the `links` sheet

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
These are derived in the PyPSA translation step from the conductor table. The
`r`/`x`/`b`/`s_nom` columns present in the raw `lines` sheet are intentionally
ignored.

**Cross-voltage rows:** the 7 rows whose endpoints sit at different voltage
levels are flagged `cross_voltage: true` and reported for manual correction in
the raw workbook (they all look like bus-name typos — the line names indicate
same-voltage connections). They are kept in canonical lines so nothing is
silently lost. See [Known Data Issues](#known-data-issues-for-manual-review).

### 2.3 `data/canonical/transformers.csv`

Substation transformers from the `gridsubs` sheet.

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

121 entries. The `r_pu` and `x_pu` columns preserve whatever the source data
provides (empty; the single "typical" string in `x` is treated as empty). The
PyPSA translator fills typical values (see 4.3).

**Transformer coverage by voltage transition (from `gridsubs`):**

| Transition | Count | s_nom range (MVA) |
|------------|-------|-------------------|
| 400/230 kV | 27 | 325, 520, 750, 1000 |
| 400/132 kV | 11 | 300, 325, 520 |
| 230/132 kV | 83 | 125, 150, 225, 300, 350, 450 |

### 2.4 `data/canonical/links.csv`

Controllable import/HVDC links from the `links` sheet, stored as-is.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Unique link identifier |
| `bus0` | str | Sending bus |
| `bus1` | str | Receiving bus |
| `p_nom_mw` | float | Import limit (MW) |
| `p_min_pu` | float | Minimum dispatch (pu of p_nom) |
| `marginal_cost` | float | USD/MWh (empty in source) |

### 2.5 `data/canonical/conductors.csv`

Reference table, extracted from the current hardcoded dict in line-bus-processor.py.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Conductor identifier |
| `r_per_km` | float | Resistance per km (ohm/km) |
| `x_per_km` | float | Reactance per km (ohm/km) |
| `b_per_km` | float | Susceptance per km (S/km) |
| `ampacity` | float | Current carrying capacity (A) |

Decoupled from code — adding a new conductor requires only a CSV edit. Must
cover all 17 conductor types referenced by the `lines` sheet.

---

## Phase 3: `src/canonical_builder.py` — Raw to Canonical

Reads the three sheets from `data/raw/pypsa_dataset.xlsx` and produces the five
canonical files. No impedance calculations.

### 3.1 Bus extraction

Collect unique bus names from ALL THREE sheets:
- `lines`: `bus0` and `bus1` columns
- `gridsubs`: `bus0` and `bus1` columns
- `links`: `bus0` and `bus1` columns
- Parse `v_nom` from name via `(\d+(?:\.\d+)?)kV` regex
- Derive `substation` by stripping voltage suffix
- Warn on names with unparseable voltage
- Report how many buses are line-only, transformer-only, link-only, or shared

### 3.2 Line processing

- Skip rows with missing `name`, `bus0`, or `bus1`
- Normalize conductor names (alias mappings)
- Skip lines with unknown conductor type
- **Name-uniqueness validation:** duplicate names are NOT auto-resolved.
  The builder prints the complete list of duplicated names (with bus0, bus1,
  length, conductor per occurrence) and records it in `build_log.json` so the
  raw workbook can be checked and corrected manually.
- **Cross-voltage validation:** rows whose endpoints have different parsed
  voltages are flagged `cross_voltage: true`, kept, and reported in full for
  manual correction (no automatic dropping or Link conversion).
- Output: physical attributes only (name, bus0, bus1, length_km, conductor,
  v_nom, cross_voltage)

### 3.3 Transformer processing

- Read `gridsubs` sheet (skip 3-row header)
- Parse `v_hv` and `v_lv` from bus names
- Orient: ensure bus_hv is the higher voltage side (source data already
  oriented HV→LV; verify and warn if not)
- Treat non-numeric `x` values (the "typical" string) as empty
- Name-uniqueness validation: report any duplicated transformer names for
  manual checking (known: `Kachua_230by132_T2` used twice — see Known Data
  Issues)
- Output: name, bus_hv, bus_lv, v_hv, v_lv, s_nom_mva, r_pu, x_pu

### 3.4 Link processing

- Read `links` sheet (skip 3-row header)
- Pass through as-is: name, bus0, bus1, p_nom_mw, p_min_pu, marginal_cost

### 3.5 Conductor reference export

Write the conductor table to `data/canonical/conductors.csv`.

### 3.6 Output summary

Print counts and validation findings. Write `data/canonical/build_log.json`:
- Timestamp, raw file hash
- Bus count (total, by source sheet)
- Line count (kept, duplicate names reported, cross-voltage flagged)
- Transformer count (kept, duplicate names reported)
- Link count

---

## Phase 4: `src/pypsa_translator.py` — Canonical to PyPSA

Reads canonical CSVs and produces PyPSA-ready component files, following the
PyPSA component conventions for
[buses](https://docs.pypsa.org/stable/user-guide/components/buses/),
[lines](https://docs.pypsa.org/stable/user-guide/components/lines/),
[transformers](https://docs.pypsa.org/stable/user-guide/components/transformers/),
and [links](https://docs.pypsa.org/stable/user-guide/components/links/).

### 4.1 Bus translation

- Set `name` as index, keep `v_nom`
- Drop `substation` (not a PyPSA Bus attribute)
- Exclude buses with unparseable voltage
- Write to `data/pypsa/buses.csv`

### 4.2 Line translation

- Read `data/canonical/lines.csv` and `data/canonical/conductors.csv`
- Join on `conductor` column
- Compute ALL derived electrical parameters from the conductor table (the raw
  sheet's r/x/b/s_nom are never used):
  - `r = r_per_km * length_km`
  - `x = x_per_km * length_km`
  - `b = b_per_km * length_km`
  - `s_nom = sqrt(3) * v_nom * ampacity / 1000`
- Set `name` as index
- Output columns: `bus0, bus1, length, r, x, b, s_nom`
- Write to `data/pypsa/lines.csv`

### 4.3 Transformer translation

PyPSA Transformer `x` and `r` are per-unit on the `s_nom` base, so typical
nameplate percent-impedance values can be used directly (12.5% → 0.125 pu).

Source data provides no impedances, so `x` is filled from a lookup of typical
values researched from manufacturer/utility specifications and IEC 60076,
keyed on voltage transformation ratio and capacity:

| Transition | s_nom (MVA) | `x` (pu) | Basis |
|------------|-------------|----------|-------|
| 400/230 kV | 325–1000 | 0.125 | Indian POWERGRID/GETCO 400/220 kV 315–500 MVA autotransformer specs quote 12.5% impedance |
| 400/132 kV | 300–520 | 0.15 | Higher transformation ratio interconnecting transformers typically 14–16% (e.g. 400/132 kV systems quoted at ~12–15% effective reactance); 15% used as midpoint |
| 230/132 kV | 125–450 | 0.125 | IEC 60076-5 Table 1 minimum short-circuit impedance for >100 MVA class is 12.5% |

Fallback for any future unit ≤100 MVA: IEC 60076-5 Table 1 (25–40 MVA: 10%,
40–63 MVA: 11%, 63–100 MVA: 12.5%).

Research sources:
- IEC 60076-5 short-circuit impedance table — https://www.eng-tips.com/threads/maximum-transformer-impedance.519123/
- POWERGRID technical specification, transformers up to 400 kV class — https://apps.powergrid.in/pgciltenders/Files/a91a0030-95f3-4d41-9823-e0fcabd44004/Vol-II_Part_2_of_3-.pdf
- GETCO 400/220 kV 315 MVA autotransformer spec — https://www.yumpu.com/en/document/view/31703216/400-220-kv-315-mva-auto-transformer-gujarat-electricity-
- Transformer impedance typical ranges — https://xbrele.com/transformer-impedance-percentage-guide/

Remaining translation steps:
- Apply `r` default where source data is empty: 0.01 pu (typical copper losses)
- Map to PyPSA Transformer attributes:
  - `bus0` = bus_hv (PyPSA convention: bus0 is the HV side)
  - `bus1` = bus_lv
  - `s_nom` = s_nom_mva
  - `x` = x_pu (from data if present, else lookup above)
  - `r` = r_pu (from data or default)
  - `tap_ratio` = 1.0 (nominal, no off-nominal tap initially)
  - `type` = "" (custom parameters, not from PyPSA standard types library)
- Set `name` as index
- Write to `data/pypsa/transformers.csv`

### 4.4 Link translation

Straight mapping from `data/canonical/links.csv` (raw `links` sheet) to PyPSA
Link attributes:

- `bus0`, `bus1` — as given
- `p_nom` = p_nom_mw
- `p_min_pu` = p_min_pu (source sets 1 — fixed full dispatch)
- `efficiency` = 1.0 (no loss data in source; revisit later)
- `marginal_cost` = value if provided, else omit (PyPSA default 0)
- Set `name` as index
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
              p_nom=row["p_nom"], p_min_pu=row["p_min_pu"],
              efficiency=row["efficiency"])
```

### 5.3 Update connectivity check

The current `check_network_correctness` already handles transformers and links
in its isolated-bus check (lines 79-82) and connected-component analysis.
With 121 transformers bridging 400/230/132 kV, the network should now report
far fewer disconnected sub-networks than the 3 voltage-level islands of the
old pipeline. Note: link-only buses (e.g. `AdaniPPSendBus_400kV`,
`SuryamaninagarSendBus_132kV`) have no AC path to the main grid and will form
small sub-networks by design.

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
   Transformer r/x are stored as-is from source (empty).
2. **PyPSA files are complete:** `data/pypsa/` has buses, lines, transformers,
   links — all with `name` as index and all electrical parameters filled.
3. **Network is connected:** `check_network_correctness` reports 1 main AC
   sub-network (plus the small link-only islands noted in 5.3).
4. **No data loss vs raw workbook:**
   - Line count = 639 (every `lines` sheet row accounted for: kept or
     explicitly reported)
   - Bus count = union of bus names across the three sheets
   - Transformer count = 121 (from `gridsubs`)
   - Link count = 4 (from `links`)
5. **Data issues surfaced:** every duplicate name and cross-voltage row is
   listed in `build_log.json` and on stdout for manual correction.
6. **Conductor table decoupled:** Adding a new conductor = CSV edit only.
7. **Backward compatibility:** `data/pipeline/` and old scripts untouched.

### 6.3 Sanity check

Spot-check `data/pypsa/lines.csv` impedances against hand-computed values
(conductor per-km × length) for a sample of lines at each voltage level, and
against the old `data/pipeline/pypsa-components/lines.csv` where line entries
are common to both raw datasets.

---

## Known Data Issues (for manual review)

Found while profiling `pypsa_dataset.xlsx`. The pipeline reports these but
does not silently fix them; corrections belong in the raw workbook.

### Duplicate line names (`lines` sheet — 12 names, 31 rows)

Excel row numbers refer to the `lines` sheet.

| Excel rows | Name | Difference between occurrences |
|------------|------|--------------------------------|
| 65, 69, 70 | Bhulta_230kVtoRampura_230kV_Line1 | identical (3 copies) |
| 472, 507 | Amnura_132kVtoChapaiNawabganj_132kV_Line1 | identical |
| 309, 564 | Bagerhat_132kVtoMongla_132kV_Line1 | 28 km Hawk vs 28.5 km Grosbeak |
| 322, 389 | Baghabari_132kVtoShahjadpur_132kV_Line1 | 5 km Hawk vs 6 km Grosbeak |
| 323, 390 | Baghabari_132kVtoShahjadpur_132kV_Line2 | 5 km Hawk vs 6 km Grosbeak |
| 358, 560 | Fatullah_132kVtoShyampur_132kV_Line1 | 4 km vs 2 km (both Grosbeak) |
| 267, 460 | Goalpara_132kVtoKhulnaCentral_132kV_Line1 | 1.5 km AAAC 804 vs 2 km Grosbeak |
| 268, 461 | Goalpara_132kVtoKhulnaCentral_132kV_Line2 | 1.5 km AAAC 804 vs 2 km Grosbeak |
| 190, 220 | Haripur_132kVtoSiddhirganj_132kV_Line1 | bus0 Haripur_230kV/2 km vs Haripur_132kV/2.5 km |
| 191, 221 | Haripur_132kVtoSiddhirganj_132kV_Line2 | bus0 Haripur_230kV/2 km vs Haripur_132kV/2.5 km |
| 453, 612 | Naogaon_132kVtoJoypurhat_132kV_Line1 | 46 km vs 47 km (both Grosbeak) |
| 454, 613 | Naogaon_132kVtoJoypurhat_132kV_Line2 | 46 km vs 47 km (both Grosbeak) |
| 320, 417 | Rajshahi_132kVtoNatore_132kV_Line1 | 37 km Hawk vs 40 km Grosbeak |
| 369, 371 | Ullon_132kVtoDhanmondi_132kV_Line1 | Cu 240 sq mm vs XLPE 500 sq mm |
| 370, 372 | Ullon_132kVtoDhanmondi_132kV_Line2 | Cu 240 sq mm vs XLPE 500 sq mm |

### Cross-voltage line rows (`lines` sheet — 7 rows)

All look like bus-name typos: the line name implies a same-voltage connection
but one bus column points at a different voltage level.

| Excel row | Name | bus0 | bus1 | Length |
|-----------|------|------|------|--------|
| 188 | Bhulta_132kVtoHaripur_132kV_Line1 | Bhulta_132kV | Haripur_230kV | 15 km |
| 189 | Bhulta_132kVtoHaripur_132kV_Line2 | Bhulta_132kV | Haripur_230kV | 15 km |
| 190 | Haripur_132kVtoSiddhirganj_132kV_Line1 | Haripur_230kV | Siddhirganj_132kV | 2 km |
| 191 | Haripur_132kVtoSiddhirganj_132kV_Line2 | Haripur_230kV | Siddhirganj_132kV | 2 km |
| 361 | Madanganj_132kVtoHaripur_230kV_Line1 | Madanganj_132kV | Haripur_230kV | 12 km |
| 495 | Kaliakoir_132kVtoMirzapur_132kV_Line1 | Kaliakoir_230kV | Mirzapur_132kV | 13 km |
| 496 | Kaliakoir_132kVtoMirzapur_132kV_Line2 | Kaliakoir_230kV | Mirzapur_132kV | 13 km |

(Rows 190/191 appear in both lists.)

### Transformer name collision (`gridsubs` sheet — 1 name)

| Excel row | Name | bus0 | bus1 | s_nom |
|-----------|------|------|------|-------|
| 106 | Kachua_230by132_T2 | Kachua_230kV | Kachua_132kV | 350 |
| 107 | Kachua_230by132_T2 | Hathazari_230kV | Hathazari_132kV | 150 |

Row 107 connects Hathazari buses — the name is almost certainly a copy-paste
error and should be something like `Hathazari_230by132_T{n}`.

---

## What This Plan Does NOT Cover (Future Work)

- **Generators** — power plants with capacity, fuel type, cost curves
  (a `generators` sheet exists in the workbook but is out of scope here)
- **Loads** — demand profiles per bus, time-series (a `loads` sheet exists
  in the workbook but is out of scope here)
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
| CREATE | `data/raw/pypsa_dataset.xlsx` | Raw workbook (lines, gridsubs, links sheets) |
| CREATE | `data/canonical/buses.csv` | Physical bus data (name, v_nom, substation) |
| CREATE | `data/canonical/lines.csv` | Physical line data (no impedances) |
| CREATE | `data/canonical/transformers.csv` | Transformer data (s_nom, optional r/x pu) |
| CREATE | `data/canonical/links.csv` | Link data (p_nom, p_min_pu) |
| CREATE | `data/canonical/conductors.csv` | Conductor reference table |
| CREATE | `data/canonical/build_log.json` | Pipeline run metadata + data-issue reports |
| CREATE | `data/pypsa/buses.csv` | PyPSA-ready buses |
| CREATE | `data/pypsa/lines.csv` | PyPSA-ready lines with computed impedances |
| CREATE | `data/pypsa/transformers.csv` | PyPSA Transformer components |
| CREATE | `data/pypsa/links.csv` | PyPSA Link components (from links sheet) |
| CREATE | `src/canonical_builder.py` | Raw → canonical pipeline |
| CREATE | `src/pypsa_translator.py` | Canonical → PyPSA pipeline |
| MODIFY | `src/network_builder.py` | Add transformers, links, new PYPSA_DIR path |
| KEEP | `data/pipeline/*` | Deprecated, preserved for reference (no longer used as input) |
| KEEP | `src/line-bus-processor.py` | Deprecated, preserved for reference |
| KEEP | `src/network-builder.py` | Deprecated, preserved for reference |

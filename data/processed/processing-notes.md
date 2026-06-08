# Processing Notes

Documents how `buses.csv` and `lines.csv` in this directory were produced
from the raw source file. The script that implements this pipeline is
`src/line-bus-processor.py`.

---

## 1. Raw Input

**File:** `data/raw/powergridlinedata.csv`  
**Total rows:** 649 (3 header rows + 646 data rows)

### Header structure

The file uses a 3-row header block before data begins:

| Row | Purpose |
|-----|---------|
| 1 | Free-text metadata note: *"Row 3 contains the names of relevant pypsa variables"* |
| 2 | Human-readable column labels: Line Name, Start Bus, End Bus, Length(km), Conductor |
| 3 | PyPSA attribute names: name, bus0, bus1, *(blank)*, *(blank)* |

Data rows start at row 4.

### Columns

| Column | PyPSA attribute | Description |
|--------|-----------------|-------------|
| A | `name` | Unique line identifier |
| B | `bus0` | Sending-end bus name |
| C | `bus1` | Receiving-end bus name |
| D | *(length_km)* | Line length in kilometres |
| E | *(conductor)* | Conductor type string |

### Bus name convention

Bus names encode their voltage level, e.g. `Aminbazar_400kV`,
`Haripur_230kV`, `Madanganj_132kV`. The voltage (kV) is parsed from the
name using the pattern `(\d+)kV`.

### Voltage levels present

| Voltage | Buses | Lines (raw) |
|---------|-------|-------------|
| 400 kV | 28 | — |
| 230 kV | 60 | — |
| 132 kV | 216 | — |

---

## 2. Transformation Pipeline

Processing is applied row by row after the 3-row header is skipped.

### 2.1 Bus extraction

All unique bus names are collected from the `bus0` and `bus1` columns
across every data row. For each unique name the nominal voltage `v_nom`
is parsed; names where no kV value can be extracted are flagged as
warnings and are written to `processed/buses.csv` with a blank `v_nom`.

### 2.2 Line filtering (skip rules, applied in order)

| Rule | Action | Rows affected (this dataset) |
|------|--------|------------------------------|
| Missing `name`, `bus0`, or `bus1` | Skip row | — |
| Duplicate `name` (same line name appears again) | Skip — first occurrence kept | 17 rows |
| Cross-voltage connection (`v_nom` of bus0 ≠ bus1) | Skip | 15 rows |
| Conductor type not in lookup table | Skip | 0 rows |

### 2.3 Conductor normalisation

Two variant spellings in the raw file are mapped to canonical names
before lookup:

| Raw string | Canonical name |
|------------|---------------|
| `Twin 300 sqmm` | `Twin 300 sq mm` |
| `Twin AAAC` | `Twin AAAC 37/4.176 mm` |

### 2.4 Electrical parameter calculation

Per-km resistance (`r_km`), reactance (`x_km`), susceptance (`b_km`),
and ampacity are looked up from an 18-entry conductor table. Line
parameters are then computed as:

| Attribute | Formula |
|-----------|---------|
| `r` (Ω) | `r_km × length` |
| `x` (Ω) | `x_km × length` |
| `b` (S) | `b_km × length` |
| `s_nom` (MVA) | `√3 × v_nom (kV) × ampacity (A) / 1000` |

### 2.5 Output to this directory

| File | Rows | Columns |
|------|------|---------|
| `buses.csv` | 304 | `name, v_nom` |
| `lines.csv` | 615 | `name, bus0, bus1, length, r, x, b, s_nom` |

`name` is stored as a regular column (not the index) in both files.

---

## 3. PyPSA Component Export

A second set of files is written to `data/pypsa-components/` for direct
use by `src/network-builder.py`. These differ from the processed files in
two ways:

1. **`name` is the row index** — matches the index convention PyPSA expects
   when components are added to a network.
2. **Buses with unparseable voltage are excluded** — only the 304 buses
   where `v_nom` was successfully parsed are written.

| File | Location | Notes |
|------|----------|-------|
| `buses.csv` | `data/pypsa-components/` | index=name, column: v_nom |
| `lines.csv` | `data/pypsa-components/` | index=name, columns: bus0, bus1, length, r, x, b, s_nom |

The network built from these files contains **304 buses** and **615 lines**
across the 132 kV, 230 kV, and 400 kV voltage levels.

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

### Sample rows (20 random data rows)

```
BSRM_230kVtoMirsarai_230kV_Line1,BSRM_230kV,Mirsarai_230kV,16.5,Twin Finch
Baghabari_132kVtoShahjadpur_132kV_Line2,Baghabari_132kV,Shahjadpur_132kV,6,Grosbeak
Bakerganj_132kVtoPatuakhali_132kV_Line1,Bakerganj_132kV,Patuakhali_132kV,20,Hawk
BoguraSouth_132kVtoSherpur(B)_132kV_Line1,BoguraSouth_132kV,Sherpur(B)_132kV,24,Grosbeak
BoguraSouth_230kVtoBoguraWest_230kV_Line2,BoguraSouth_230kV,BoguraWest_230kV,11,Twin AAAC
Chandraghona_132kVtoRangamati_132kV_Line1,Chandraghona_132kV,Rangamati_132kV,27.5,Grosbeak
Daudkandi_132kVtoDaudkandiPP_132kV_Line1,Daudkandi_132kV,DaudkandiPP_132kV,1,Grosbeak
Feni_132kVtoDaganbhuiyan_132kV_Line1,Feni_132kV,Daganbhuiyan_132kV,16,Grosbeak
GopalganjNorth_400kVtoAminbazar_400kV_Line1,GopalganjNorth_400kV,Aminbazar_400kV,75.3,Quad Finch
Hasnabad_132kVtoKeraniganj_132kV_Line1,Hasnabad_132kV,Keraniganj_132kV,14,Grosbeak
Hasnabad_230kVtoKeraniganj_230kV_Line2,Hasnabad_230kV,Keraniganj_230kV,10.75,Twin AAAC
Khulshi_132kVtoBakulia_132kV_Line1,Khulshi_132kV,Bakulia_132kV,15,Grosbeak
Maniknagar_132kVtoMatuail_132kV_Line1,Maniknagar_132kV,Matuail_132kV,16,Grosbeak
Patiya_132kVtoDohazari_132kV_Line1,Patiya_132kV,Dohazari_132kV,21,Grosbeak
PayraPP_400kVtoAmtali_400kV_Line1,PayraPP_400kV,Amtali_400kV,17,Quad Finch
Rampal_230kVtoKhulnaSouth_230kV_Line2,Rampal_230kV,KhulnaSouth_230kV,24,Twin Mallard
Rampur_132kVtoAgrabad_132kV_Line1,Rampur_132kV,Agrabad_132kV,4.5,XLPE 800 sq mm
Sherpur(B)_132kVtoSirajganj_132kV_Line1,Sherpur(B)_132kV,Sirajganj_132kV,33,Grosbeak
Sripur_132kVtoBhaluka_132kV_Line1,Sripur_132kV,Bhaluka_132kV,22.5,Grosbeak
Sripur_132kVtoBhaluka_132kV_Line2,Sripur_132kV,Bhaluka_132kV,22.5,Grosbeak
```

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

#### Simplifications applied

Two rules above are deliberate simplifications chosen during planning:

**Cross-voltage connections (15 rows):**
The fuller approach considered was to include these lines using `bus0`'s
voltage level for `s_nom` and log a warning, since they likely represent
transformers modelled as lines in the raw data. This was simplified to a
hard skip to keep the pipeline focused on pure transmission lines only.
Transformer modelling is left for a future step.

**Duplicate line names (17 rows):**
The fuller approach considered was to keep all copies and auto-rename
duplicates by appending `_v2`, `_v3`, etc., since many share a name but
differ in conductor type or bus endpoints (i.e. they are distinct physical
circuits). This was simplified to dropping all but the first occurrence to
avoid ambiguity in the current pipeline. The dropped rows are printed to
console for review.

### 2.3 Conductor normalisation

Two variant spellings in the raw file are mapped to canonical names
before lookup:

| Raw string | Canonical name |
|------------|---------------|
| `Twin 300 sqmm` | `Twin 300 sq mm` |
| `Twin AAAC` | `Twin AAAC 37/4.176 mm` |

### 2.4 Electrical parameter calculation

Per-km resistance (`r_km`), reactance (`x_km`), susceptance (`b_km`),
and ampacity are looked up from the conductor reference table below. Line
parameters are then computed as:

| Attribute | Formula |
|-----------|---------|
| `r` (Ω) | `r_km × length` |
| `x` (Ω) | `x_km × length` |
| `b` (S) | `b_km × length` |
| `s_nom` (MVA) | `√3 × v_nom (kV) × ampacity (A) / 1000` |

#### Conductor reference table

| Conductor Name | r (Ω/km) | x (Ω/km) | b (S/km) | Ampacity (A) |
|----------------|----------:|----------:|----------:|-------------:|
| Finch | 0.0588524 | 0.1968333 | 5.97 × 10⁻⁶ | 1000 |
| Twin Finch | 0.0294262 | 0.1377833 | 1.19 × 10⁻⁵ | 2000 |
| Quad Finch | 0.0147131 | 0.1082583 | 2.72 × 10⁻⁵ | 4000 |
| Quad Egret | 0.025346 | 0.115775 | 2.51 × 10⁻⁵ | 2868 |
| Mallard | 0.0812452 | 0.2034167 | 5.73 × 10⁻⁶ | 824 |
| Twin Mallard | 0.0406226 | 0.1423917 | 1.15 × 10⁻⁵ | 1648 |
| Quad Mallard | 0.0203113 | 0.1118792 | 2.60 × 10⁻⁵ | 3296 |
| Twin 300 sq mm | 0.044528 | 0.1527167 | 1.08 × 10⁻⁵ | 1370 |
| Twin AAAC 37/4.176 mm | 0.0342056 | 0.14315 | 1.15 × 10⁻⁵ | 1806 |
| ACSR 600 sq mm | 0.0552 | 0.1965833 | 6.01 × 10⁻⁶ | 1037 |
| XLPE 2000 sq mm | 0.0184 | 0.06552 | 2.00 × 10⁻⁶ | 3000 |
| Grosbeak | 0.101292 | 0.21325 | 5.48 × 10⁻⁶ | 712 |
| Linnet | 0.190992 | 0.23325 | 4.98 × 10⁻⁶ | 478 |
| AAAC 804 sq mm | 0.0419244 | 0.1856667 | 6.36 × 10⁻⁶ | 1241 |
| Hawk | 0.134872 | 0.2225833 | 5.24 × 10⁻⁶ | 594 |
| XLPE 500 sq mm | 0.0736 | 0.26208 | 8.01 × 10⁻⁶ | 750 |
| Cu 240 sq mm | 0.134872 | 0.2225833 | 5.24 × 10⁻⁶ | 594 |
| XLPE 800 sq mm | 0.0736 | 0.26208 | 8.01 × 10⁻⁶ | 750 |

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

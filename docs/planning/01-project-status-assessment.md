# Project Status Assessment

> **Scope:** Current state of data, code, and pipeline for the Bangladesh power system
> analysis & visualization project.
> **Date:** June 2026 | **Status:** Assessment v1.0
> **Companion docs:** [Vertical A plan](02-vertical-a-pypsa-analysis-plan.md) ·
> [Vertical B plan](03-vertical-b-geo-visualization-plan.md)
> **Builds on:** [Design proposal (May 2026)](../bangladesh-power-system-design-proposal.md)

---

## 1. Executive Summary

The May 2026 design proposal identified **bus-to-bus connectivity** as the Priority 1 gap
that "blocks all analysis" and **substation coordinates** as a Priority 4 polish item.
Both assessments are now obsolete, in a good way:

1. The consolidated dataset (`pypsa_dataset.xlsx`) **closes the connectivity gap** —
   all 638 transmission line records carry `bus0`/`bus1` assignments, and 548 carry
   computed electrical parameters (r, x, b, s_nom).
2. Two KMZ files (**Substation.kmz**, **Transmission_Line.kmz**) **largely close the
   coordinate gap** — 211 georeferenced substation points and 357 transmission line
   paths with real, vertex-by-vertex routed geometry (not straight lines). ~70% of
   dataset substations match KMZ names automatically; ~75–80% after synonym
   normalization; the residual is a bounded manual pass.

The remaining gaps are all on the **analysis input** side (load MW values, generator
bus assignments, marginal costs), none on the **topology or geography** side.

The project splits into two largely independent verticals sharing one canonical data
foundation:

- **Vertical A — Network modeling & analysis (PyPSA):** economic dispatch, DC-OPF,
  LMPs, contingency analysis, renewable integration studies.
- **Vertical B — Geo visualization & analytics (Google Maps stack):** interactive
  grid map, infrastructure inspection, analysis-result overlays.

The single most important near-term build is neither vertical: it is the **canonical
network store + stitching pipeline** that both verticals consume (Section 5).

---

## 2. Data Inventory

### 2.1 Consolidated dataset — `pypsa_dataset.xlsx`

The workbook is designed for machine ingestion: row 3 of every sheet carries PyPSA
attribute names (`name`, `bus0`, `bus1`, `r`, `x`, `s_nom`, …).

| Sheet | Records | Complete | Missing |
|---|---|---|---|
| `lines` | 638 | **All** have `bus0`/`bus1` connectivity; 548 have r, x, b, s_nom | 90 lines missing electrical parameters |
| `gridsubs` (transformers) | 121 | All have bus pairs + MVA rating | Impedances marked "typical" — need standard IEC fallbacks |
| `loads` | 479 | All have transformer MVA rating | No `bus` column populated, no `p_set` (MW). **Bus is recoverable** — load names embed the bus (`AKSPL_230kV_Load1` → bus `AKSPL_230kV`) |
| `generators` | 147 | All have `p_nom`; all have `Area` (9 zones); 30 have technology (CCGT/OCGT/ICE) | No bus assignment, no marginal cost, fuel mostly empty |
| `links` | 4 | Bheramara HVDC ×2, Adani interconnect | Tripura link row empty; setpoints partial |
| `buses` | header only | — | Bus list is implied by lines/transformers (305 unique buses) |
| `linedata` | reference | Bundling factors, GMR constants for impedance derivation | — |

**Implied bus inventory:** 305 unique buses — 29 × 400 kV, 60 × 230 kV, 216 × 132 kV —
consistent with the PGCB national grid. Buses encode voltage in the name
(`Aminbazar_400kV`), so `v_nom` is parseable.

### 2.2 Geographic data — KMZ files

**`Substation.kmz` — 211 placemarks (points).** Folder structure encodes voltage class
and ownership:

| Folder | Count |
|---|---|
| 132/33 kV (PGCB / DPDC / DESCO / BPDB / Private) | 165 |
| 230/132 kV (PGCB / BPDB / NWPGCL / others) | 32 |
| 400/230 kV | 8 |
| HVDC | 2 |
| 230/33 kV | 4 |

**`Transmission_Line.kmz` — 357 placemarks (LineStrings).** Real routed geometry
following actual corridors (including river crossings such as the Padma crossing on
the Aminbazar–Gopalganj 400 kV route). Folder structure:

| Folder | Count |
|---|---|
| 132 kV (overhead / UG cable / power-station connection / single ckt) | 271 |
| 230 kV (incl. PS connections) | 71 |
| 400 kV | 15 |

The overhead vs. underground-cable distinction is a data layer the Excel does not have.

**Match analysis (normalized name matching against the dataset):**

- Excel's 638 circuit lines collapse to **332 unique routes** (Line1/Line2 circuits
  share a corridor) → 357 KML paths vs 332 routes is essentially 1:1 route coverage.
- Substations: **141/249 exact** normalized matches + **~34 fuzzy** → **~70% automatic**;
  a small romanization synonym table (Cumilla/Comilla, Bogura/Bogra, Barishal/Barisal)
  pushes this to ~75–80%.
- The ~74 hard-unmatched names fall into three explainable buckets:
  1. **Romanization variants** — recoverable via synonym table.
  2. **Power plant buses** (`Barishal307MWPP`, `ConfidencePP`, …) — generator
     connection points, correctly absent from a *substation* KMZ; placeable via plant
     geocoding or snapping to nearest line endpoint.
  3. **Pseudo-buses** (`BangladeshBorder1/2`) — HVDC modeling artifacts; crossing
     points are known and can be hand-placed.
- Realistic residual needing manual placement: **20–40 substations**.
- **Vintage caveat:** if the KMZ predates the Excel, recent assets (Adani, Payra) may
  be missing; the unmatched-name analysis surfaces exactly which.

### 2.3 Supporting data in repo (`data/grids-substations-data-pgcb/`)

| Asset | Use |
|---|---|
| `grids-formatted.csv` (354 lines), `substations-formatted.csv` (251 substations) | Earlier-generation cleaned PGCB data; ownership & zone attributes |
| `pgcb-substation-Daily-Report-11-05-2026.xlsx` | Real operational snapshot — model validation |
| `Conductor-sepc-transpower.pdf` | Conductor R/GMR specs — impedance derivation |
| `network-geo-map.pdf`, `grids.pdf`, `substations.pdf` | Source documents; manual georeferencing fallback |
| `pypsa-components/` (pypsa_buses.csv 282, pypsa_lines.csv 703) | Second-generation component extraction with ownership/grid-circle attributes |

### 2.4 External data (identified, not yet integrated)

| Source | Provides | Gap it closes |
|---|---|---|
| UCI PGCB Hourly Generation Dataset | Measured hourly system generation/demand | Load profiles (`p_set` time series) |
| `PyPSA/technology-data` repo | CAPEX/OPEX, heat rates, fuel costs per tech per year | Generator marginal costs |
| powerplantmatching (GEM/WRI/GEO merged DBs) | Plant names, coordinates, fuel, capacity for BD | Generator bus assignment + fuel |
| ERA5 via atlite | Hourly solar/wind capacity factors at any coordinate | Renewable profiles (needs the KMZ coordinates — now available) |
| PyPSA-BD (AIT/IUBAT, 2024) | Published BD scenarios at 30 km resolution | Validation benchmark |
| OSM power data (via Overpass / PyPSA-Earth extraction) | Independent geometry source | Cross-validation + gap-fill for Vertical B |

---

## 3. Code & Pipeline Inventory

### 3.1 Working pipeline (`src/` + `data/pipeline/`)

```
data/pipeline/raw/powergridlinedata.csv   (646 data rows)
        │  src/line-bus-processor.py
        │    · 3-row header handling
        │    · conductor reference table (18 types) → r/x/b per km
        │    · s_nom = √3 · v_nom · ampacity
        │    · skip rules: duplicates (17), cross-voltage (15)
        ▼
data/pipeline/processed/{buses,lines}.csv          (304 buses, 615 lines)
data/pipeline/pypsa-components/{buses,lines}.csv   (PyPSA-indexed)
        │  src/network-builder.py
        ▼
pypsa.Network — 304 buses / 615 lines, with correctness checks:
  isolated-bus detection · island detection (determine_network_topology)
  · pypsa consistency_check()
```

**This is Vertical A working end-to-end at the topology level.** The processing notes
(`data/pipeline/processed/processing-notes.md`) explicitly document two deliberate
simplifications that are now resolvable:

- **Cross-voltage rows skipped (15):** these are transformers modeled as lines in the
  raw data. The xlsx `gridsubs` sheet now provides 121 proper transformer records.
- **Duplicate line names dropped (17):** many are distinct physical circuits. The xlsx
  appears to have already resolved naming.

### 3.2 Earlier-generation scripts

`data/grids-substations-data-pgcb/build_components.py` and `cleanup_csv.py` — the
first-generation extraction from PGCB CSVs. Superseded in function by the pipeline
above and by the xlsx, but their outputs carry attributes (ownership, grid circle)
worth merging into the canonical store.

### 3.3 The data-duplication problem

There are currently **three overlapping copies** of the network data with no declared
master:

1. `data/grids-substations-data-pgcb/pypsa-components/` (gen-1)
2. `data/pipeline/` (gen-2, current code path)
3. `pypsa_dataset.xlsx` (gen-3, most complete — adds transformers, loads, generators, links)

This must be resolved by declaring a single canonical store (Section 5) before either
vertical builds further.

---

## 4. The Two-Vertical Architecture

| | Vertical A | Vertical B |
|---|---|---|
| **Goal** | Power system analysis: dispatch, OPF, LMP, N-1, RE integration | Rich geo visualization & analytics on Google Maps/Earth |
| **Stack** | PyPSA + parts of the PyPSA-Earth ecosystem (atlite, technology-data, powerplantmatching) | Google Maps JS API + deck.gl, GeoJSON/KML artifacts |
| **Output** | Result tables keyed by component name (`buses_t.marginal_price`, `lines_t.p0`, …) | Interactive product keyed by geometry |
| **Users** | Engineers, analysts, researchers | Engineers + non-engineer stakeholders (IPPs, lenders, policy) |
| **Plan** | [02-vertical-a-pypsa-analysis-plan.md](02-vertical-a-pypsa-analysis-plan.md) | [03-vertical-b-geo-visualization-plan.md](03-vertical-b-geo-visualization-plan.md) |

**Coupling contract:** both verticals share one canonical network store, and the join
key is the **component name**. Vertical A writes results as name-keyed tables;
Vertical B joins them onto geometry and renders. Vertical B never imports PyPSA at
runtime; Vertical A never knows Google Maps exists.

**PyPSA-Earth's role:** parts supplier to both verticals, not a framework to adopt.
Its OSM-derived topology is strictly worse than the PGCB ground truth; its Snakemake
workflow is built to bootstrap a country from nothing, which is not this project's
situation. Detailed component-by-component assessment in the Vertical A plan, §3.

---

## 5. The Shared Foundation: Canonical Network Store

The first concrete project — blocking both verticals, ~1 week of work:

```
Sources:  pypsa_dataset.xlsx    Substation.kmz / Transmission_Line.kmz    PGCB reports
              │                            │
              ▼                            ▼
       ingest / validate          KMZ stitching + name matching
              └────────────┬───────────────┘
                           ▼
       CANONICAL NETWORK STORE  (single source of truth)
         network/            ← PyPSA CSV-folder format
           buses.csv         (name, v_nom, x, y, carrier, zone, ownership)
           lines.csv         (name, bus0, bus1, length, r, x, b, s_nom, conductor, circuits)
           transformers.csv  (name, bus0, bus1, s_nom, r, x)
           loads.csv         (name, bus, trafo_mva, p_set)
           generators.csv    (name, bus, p_nom, carrier, marginal_cost, technology, area)
           links.csv         (name, bus0, bus1, p_nom, p_set, p_min_pu)
         geo/                ← sidecars (PyPSA holds bus x/y natively; not LineStrings)
           line_geometries.geojson   (keyed by line name; routed paths)
           substation_coords.csv     (match provenance: exact/fuzzy/manual/geocoded)
           unmatched_review.csv      (manual-review residuals)
```

Validation gates on every build of the store: no isolated buses, single connected
component, impedances present or explicitly defaulted, KML path length vs. Excel
`Length(km)` within tolerance, geometric endpoint-snapping agrees with declared
`bus0`/`bus1`.

---

## 6. Gap Summary & Priorities

| # | Gap | Severity | Closure path | Effort |
|---|---|---|---|---|
| 1 | No canonical store; 3 data copies | **Blocks both verticals** | Build store + stitching pipeline (§5) | ~1 week |
| 2 | Generator marginal costs | Blocks all dispatch | technology-data + BD fuel price benchmarks | Days |
| 3 | Generator bus assignment | Blocks nodal analysis | powerplantmatching coords → snap to nearest bus; Area as fallback | Days |
| 4 | Load `p_set` values | Blocks time-series dispatch | UCI hourly dataset allocated by transformer-MVA share | Days |
| 5 | ~20–40 unplaced substations | Degrades map completeness | Synonym table → geocoding → manual pass | Bounded manual |
| 6 | 90 lines missing r/x/s_nom | Minor — degrades 14% of lines | Conductor-table defaults by voltage class | Hours |
| 7 | Transformer impedances ("typical") | Minor | Standard IEC %Z by MVA rating | Hours |
| 8 | Tripura link parameters | Minor | Public BPDB import data | Hours |

After gap 1, the verticals decouple completely until the "analysis overlays on the
map" milestone — which is also the commercially significant demo.

# pypsa-poc
### Scratchpad for exploring different features of pypsa

<picture align="center">
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/PyPSA/PyPSA/refs/heads/master/docs/assets/logo/logo-primary-dark.svg">
  <img alt="PyPSA Banner" src="https://raw.githubusercontent.com/PyPSA/PyPSA/refs/heads/master/docs/assets/logo/logo-primary-light.svg">
</picture>

## What this is

A proof-of-concept PyPSA model of the Bangladesh power transmission grid (132/230/400 kV), built from raw Google Sheets exports. The repo turns spreadsheet data into a `pypsa.Network` and runs linear economic dispatch on it with HiGHS.

## Setup & commands

Install deps with `pip install -r requirements.txt` — this is the authoritative dependency list (used by `.devcontainer/devcontainer.json`). **Do not use `pyproject.toml`**: it is a stale, narrower poetry manifest that omits `highspy`, `opencv-contrib-python`, `PyMuPDF`, `shapely`, and `folium`, which the map-extraction and dispatch code require. Always treat `requirements.txt` as the source of truth for dependencies.

First, refresh the raw data from the source Google Sheet (needs `src/sheet-mapping.json`, sheet must be link-shared) — this is step 0, run before the data pipeline below:
```
python src/fetch_and_split_sheet.py
```
It downloads the whole workbook (default `data/pipeline/raw/pypsa_dataset.xlsx`) and splits the mapped tabs into the individual `raw/*.xlsx` files the builders consume.

Then run the full data pipeline in one shot:
```
./run-data-pipeline.sh      # or run-data-pipeline.ps1 on Windows
```

Or run the steps individually — **order matters**, see `src/data-script-execution-order.txt`:
```
python src/line-bus-processor.py     # 1. buses + lines — must run first
python src/generator_builder.py      # 2. any order among these four
python src/load_builder.py
python src/transformer_builder.py
python src/link_builder.py
python src/bus_supplement.py         # 3. must run last (augments buses.csv)
```

Then build/inspect the network and run dispatch:
```
python src/network-builder.py        # assembles + validates the pypsa.Network
python src/economic_dispatch.py      # restricts to one sub-network, solves with HiGHS
```

Run the map-extraction CLI (separate concern, see below) as a module from repo root:
```
python -m src.map_extract.main --pdf <path.pdf> --out data/pipeline/raw/pbs-2-lines --dpi 300
```

There is no test suite or linter configured in this repo.

## Architecture

### Data pipeline (raw → canonical → PyPSA)

All data lives under `data/pipeline/`:
- `raw/` — source `.xlsx` workbooks exported from Google Sheets (one per component type: `linedata.xlsx`, `generatordatabaseline.xlsx`, `load-data.xlsx`, `trafo-data.xlsx`, `link-data.xlsx`)
- `canonical/` — backend-agnostic processed tables (human-readable, not PyPSA-shaped)
- `pypsa-components/` — PyPSA-ready CSVs (`name` as index, PyPSA attribute names), consumed directly by `pypsa.Network.import_from_csv_folder`

Each `*_builder.py` script (`line-bus-processor.py`, `generator_builder.py`, `load_builder.py`, `transformer_builder.py`, `link_builder.py`) is independent and follows the same shape: read one raw workbook → detect the header row by scanning for known PyPSA column names (e.g. `name`, `bus0`, `bus1`) rather than a fixed row index, so column insertions/reorderings upstream don't break parsing → write one canonical CSV and one PyPSA CSV.

`bus_supplement.py` must run *last*. `line-bus-processor.py` derives `buses.csv` only from line endpoints, so buses that only appear as transformer LV sides, load points, generator connections, or Link endpoints (e.g. HVDC send/receive buses) are missing until this script unions in every bus referenced by any other component CSV. It also writes `pypsa-components/network.csv` with the current `pypsa_version` so PyPSA's importer doesn't run backward-compat shims. Re-running `line-bus-processor.py` rewrites `buses.csv` from scratch, so `bus_supplement.py` needs to run again afterward.

`transformer_builder.py` reads per-unit reactance values from `data/pipeline/x_pu_search/x_pu_lookup.json` (a lookup keyed on `(v_hv, v_lv, s_nom)`, generated separately by `data/pipeline/x_pu_search/trafo-x_pu-search.py`) since the raw sheet has no impedance data.

`generator_builder.py` derives marginal cost from a hardcoded `MC_REF` table of (capacity, cost) anchor points per (technology, fuel category), log-log interpolated via `log_linear_interp`, plus hardcoded `TECH_LOOKUP`/`FUEL_LOOKUP` tables used as fallbacks when the raw sheet leaves those columns blank. Rows with technology/fuel `"Import"` are excluded from the PyPSA generator output (they belong in `link_builder.py`'s output instead, as controllable Links).

### Network assembly & dispatch

`network-builder.py` loads `data/pipeline/pypsa-components/` via `import_from_csv_folder` and runs `check_network_correctness`: isolated-bus detection, connected-component/island analysis via `determine_network_topology`, and PyPSA's built-in `consistency_check`.

`economic_dispatch.py` operates on one sub-network at a time (the full network currently has multiple disconnected islands across voltage levels — see `n.sub_networks`). It runs structural pre-checks (`structural_checks`) that catch common LP-infeasibility causes before solving (capacity shortfall, forced generation exceeding load, isolated buses, zero/NaN branch ratings or reactance) and solves with HiGHS via `n.optimize()`. On infeasibility, `diagnose_infeasibility()` re-solves a copy of the network with an unlimited slack generator (inject and absorb, heavily penalized) at every bus to localize exactly which buses can't balance and why.

### Map extraction (`src/map_extract/`)

**This is an in-progress proof-of-concept, not a finished or production part of the repo** — treat it as exploratory and subject to change, not as a settled pipeline. A separate, unrelated concern from the tabular data pipeline: it extracts transmission-line geometries from scanned REB/PBS substation-map PDFs into GeoJSON, to explore sourcing line/route data that isn't available as structured spreadsheets. Stages, chained by `main.py`:
1. `render.py` — rasterize a PDF page to an image at a given DPI
2. `georef.py` — fit a pixel→(lon, lat) affine transform from graticule (grid line) labels printed on the map
3. `extract.py` — per conductor type (`conductors.py` defines `ConductorSpec`s with legend colors), HSV color-mask the image, exclude known non-line regions (legend, tables, index map), skeletonize, and trace polylines
4. `export.py` — convert pixel polylines to geo-coordinates via the georef fit, compute haversine lengths, write GeoJSON/CSV and a per-conductor length summary
5. `validate.py` — render an HTML overlay (extracted lines over the source PDF) for manual visual QA

This pipeline is independent of the tabular data pipeline above — it only produces raw inputs (e.g. `data/pipeline/raw/pbs-2-lines/`) that could feed into it later, not PyPSA components directly.

## Economic dispatch

Run dispatch for the complete imported network:

```powershell
python src/economic_dispatch.py
```

To run a specific passive AC sub-network, pass its zero-based position in
PyPSA's `n.sub_networks` list:

```powershell
python src/economic_dispatch.py --subnet 0
```

Subnet mode removes buses and components outside the selected sub-network,
including Links crossing its boundary. The infeasibility diagnostic uses the
same full-network or selected-sub-network scope as the main solve.

# Finalizing Pipeline Plan

Remaining tasks to complete the Bangladesh power grid PyPSA data pipeline.

---

## Task C — Create `src/generator_builder.py`

- Reads `data/raw/powergridgeneratordata.csv` (3-row header, skip rows 0–2, 7 columns)
- Uses `data/raw/generator_metadata.csv` as fallback lookup for technology and fuel when sheet values are blank
- Copy MC_REF, FUEL_CATEGORY, HSD_PREMIUM, log_linear_interp, calc_marginal_cost logic from `task-pipeline/generate_final_generator_data.py`
- Canonical output columns: `name, area, technology, fuel, bus, p_nom_mw, marginal_cost_usd_mwh` → `data/canonical/generators.csv`
- PyPSA output columns: `name` (index), `bus, p_nom, marginal_cost` → `data/pypsa/generators.csv`
- Also create `data/raw/generator_metadata.csv`: columns `name, technology, fuel` for all 143 plants
  - Derive from TECH_LOOKUP + FUEL_LOOKUP in `generate_final_generator_data.py`
  - Handle `Manikganj 162MW PP(MPGL)` manually → technology=ICE, fuel=HFO

---

## Task D — Create `src/load_builder.py`

- Reads `data/raw/powergridloaddata.csv` (3-row header, 7 columns)
- Pass all loads through including zero-load entries
- Canonical output columns: `name, bus, p_set_mw, q_set_mvar` → `data/canonical/loads.csv`
- PyPSA output columns: `name` (index), `bus, p_set, q_set` → `data/pypsa/loads.csv`

---

## Task E — Create `src/transformer_builder.py`

- Reads `data/raw/powergridtransformerdata.csv` (3-row header, 6 columns: name, bus0, bus1, r, x, s_nom)
- Parse v_hv and v_lv from bus names using regex `(\d+(?:\.\d+)?)kV`
- Fill x_pu using voltage-pair lookup:
  - `(400, 230)` → `x = 0.125`
  - `(400, 132)` → `x = 0.15`
  - `(230, 132)` → `x = 0.125`
- r_pu default = 0.01; treat "typical" in x column as blank (use lookup)
- Canonical output columns: `name, bus_hv, bus_lv, v_hv, v_lv, s_nom_mva, r_pu, x_pu` → `data/canonical/transformers.csv`
- PyPSA output columns: `name` (index), `bus0, bus1, s_nom, x, r, tap_ratio=1.0, type=""` → `data/pypsa/transformers.csv`

---

## Task F — Deprecate old scripts

- Add `# DEPRECATED` comment header to:
  - `task-pipeline/generate_generator_data.py`
  - `task-pipeline/generate_final_generator_data.py`
- These are superseded by `src/generator_builder.py`

---

## Task G — Update `data/plan.md`

- Remove generators and loads from the "What This Plan Does NOT Cover" section
- Add generator and load pipeline sections documenting the new scripts

---

## Task H — Update `src/network-builder.py`

- Change `PYPSA_DIR` from `ROOT / "data" / "pipeline" / "pypsa-components"` to `ROOT / "data" / "pypsa"`
- Add loading for transformers from `data/pypsa/transformers.csv`
- Add loading for generators from `data/pypsa/generators.csv`
- Add loading for loads from `data/pypsa/loads.csv`

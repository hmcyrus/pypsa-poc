"""
trafo-x_pu-search.py

Build-time research artifact for transformer_builder.py.

Maps each (v_hv_kV, v_lv_kV, s_nom_MVA) combo present in
data/pipeline/raw/trafo-data.xlsx to a typical per-unit reactance on the
transformer's own MVA base (IEC 60076-5 convention).

Approach: values were sourced via web search by Claude and baked in below
with inline citations (see RESEARCH_LOG). Re-running the queries listed
there reproduces the inputs.

Outputs:
  data/pipeline/x_pu_search/x_pu_lookup.json
  consumed by src/transformer_builder.py. Structure:
      { "r_pu_default": <float>,
        "x_pu_by_combo": { "<v_hv>_<v_lv>_<s_nom>": <float>, ... } }

Convention: x_pu and r_pu are per-unit on the transformer's own s_nom MVA
base and v_nom voltage base, matching PyPSA's Transformer attributes `x`
and `r` exactly. See PyPSA docs:
    https://docs.pypsa.org/latest/user-guide/components/transformers/
("Series reactance (per unit, using s_nom as base power and v_nom as
base voltage)" — same for series resistance.) Leaving Transformer.type
as the default empty string is required so our x, r values are used
rather than being overridden by a standard type.

Run:
    python data/pipeline/x_pu_search/trafo-x_pu-search.py
"""

import json
import re
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────
HERE     = Path(__file__).parent
ROOT     = HERE.parent.parent.parent
RAW_PATH = ROOT / "data" / "pipeline" / "raw" / "trafo-data.xlsx"
OUT_PATH = HERE / "x_pu_lookup.json"

# ── Research log ───────────────────────────────────────────────────────────
# Web queries issued (2026-06):
#   Q1: "230/132 kV power transformer typical per unit reactance impedance
#        percentage IEC 60076"
#   Q2: "400/230 kV autotransformer typical impedance reactance percentage
#        750 MVA 500 MVA"
#   Q3: "400/132 kV power transformer typical impedance reactance percentage
#        MVA"
#   Q4: "IEC 60076-5 minimum short-circuit impedance table MVA rating"
#   Q5: "PGCB Bangladesh 230kV 132kV transformer impedance specification"
#   Q6: '"autotransformer" "400/220" OR "400/230" impedance "13%" ... typical'
#
# Sources consulted:
#   S1: IEC 60076-5:2006 Table 1 — minimum short-circuit impedance:
#         25–40 MVA: 10 % ; 40–63 MVA: 11 % ;
#         63–100 MVA: 12.5 % ; >100 MVA: >12.5 %.
#       https://cdn.standards.iteh.ai/samples/12942/4a1bf912eee042b0969fd9d9e336b7d2/IEC-60076-5-2006.pdf
#
#   S2: xbrele.com — "Transformer Impedance Percentage (Z%): Formula & Typical
#       Range". For units >500 kVA, X% is 85–95 % of total Z%, so r_pu can be
#       neglected vs. x_pu to within ~1 % in pu terms.
#       https://xbrele.com/transformer-impedance-percentage-guide/
#
#   S3: Practical example cited across multiple sources: 250 MVA 400/132 kV
#       transformer specified to IEC 60076-5 → 12 % recommended, 12.5 % chosen
#       to balance fault-level vs. voltage-regulation trade-off.
#
#   S4: theworldofengineers.com — "Autotransformers in EHV Power Systems":
#       EHV autotransformers typically 12–18 % impedance.
#       https://theworldofengineers.com/autotransformer/
#
#   S5: PGCB / BPDB bidding documents indexed but PDFs returned only image
#       streams — no usable numeric extraction. Values below therefore lean
#       on IEC + industry guidance rather than Bangladesh-specific datasheets.
#       https://erp.powergrid.gov.bd/  (PGCB ERP, search "transformer")
#
#   S6: PyPSA Transformer component reference — confirms x, r units and the
#       role of the empty `type` default in keeping our values authoritative.
#       https://docs.pypsa.org/latest/user-guide/components/transformers/

# ── r_pu default ───────────────────────────────────────────────────────────
# Single scalar applied to every transformer, since the raw xlsx provides
# no per-unit resistance data (100 % of the column is NaN). Per S2, X% is
# 85–95 % of total Z% for units >500 kVA, so a small non-zero R is the
# physically correct default rather than R = 0. PyPSA's default for r is 0
# (S6), but using exactly 0 makes the transformer purely reactive, which
# trips DC-load-flow solvers that need a non-singular R+jX and can also
# cause unrealistic zero-damping behaviour in time-domain studies. 0.01 pu
# sits in the low end of the empirically observed X/R ≈ 10–20 range for
# HV power transformers (i.e., R ≈ 0.05–0.10 × X for x_pu ≈ 0.125), which
# is conservative and consistent with the rest of the lookup.
R_PU_DEFAULT: float = 0.01

# ── Lookup ─────────────────────────────────────────────────────────────────
# Key: (v_hv_kV, v_lv_kV, s_nom_MVA)  →  x_pu on s_nom base.
# Voltage pair groups annotated with the dominant source.
X_PU_LOOKUP: dict[tuple[int, int, int], float] = {
    # 230/132 kV — two-winding step-down (ratio ~1.74). IEC 60076-5 >100 MVA
    # minimum 12.5 % (S1); large modern units cluster 12.5–13 %.
    (230, 132,  125): 0.125,   # S1 (just above 100 MVA threshold)
    (230, 132,  150): 0.125,   # S1
    (230, 132,  225): 0.125,   # S1
    (230, 132,  300): 0.125,   # S3 (analog of 250 MVA 400/132 example)
    (230, 132,  350): 0.130,   # S1 + scaling with MVA
    (230, 132,  450): 0.130,   # S1 + scaling

    # 400/132 kV — large step-down (ratio ~3.03). Higher Z to limit 132 kV
    # fault levels. Anchored by S3.
    (400, 132,  300): 0.125,   # S3
    (400, 132,  325): 0.130,   # S3 + small MVA increment
    (400, 132,  520): 0.140,   # S1 + scaling for >500 MVA class

    # 400/230 kV — EHV autotransformer (ratio ~1.74). S4 range 12–18 %.
    (400, 230,  325): 0.130,   # S4 lower end
    (400, 230,  520): 0.130,   # S4 lower end
    (400, 230,  750): 0.140,   # S4 midpoint
    (400, 230, 1000): 0.150,   # S4 mid-upper for largest units
}

# ── Processing ─────────────────────────────────────────────────────────────

def _parse_voltage(bus: str) -> int | None:
    """Extract kV integer from a bus name like 'Barapukuria_230kV' -> 230."""
    m = re.search(r'(\d+(?:\.\d+)?)kV', str(bus))
    if not m:
        return None
    v = float(m.group(1))
    return int(v) if v == int(v) else v  # type: ignore[return-value]


def _enumerate_combos(path: Path) -> list[tuple[int, int, int]]:
    """Distinct (v_hv, v_lv, s_nom_mva) combos in trafo-data.xlsx."""
    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=str)

    # Detect the PyPSA attribute header row (the one with name/bus0/bus1).
    pypsa_row_idx = None
    for i, row in raw.iterrows():
        cells = row.fillna("").astype(str).str.strip().tolist()
        if "name" in cells and "bus0" in cells and "bus1" in cells:
            pypsa_row_idx = i
            break
    if pypsa_row_idx is None:
        raise ValueError(f"Could not find PyPSA header row in {path}")

    cols = raw.iloc[pypsa_row_idx].fillna("").astype(str).str.strip().tolist()
    data = raw.iloc[pypsa_row_idx + 1:].reset_index(drop=True)
    data.columns = cols
    data = data[data["name"].notna() & (data["name"].str.strip() != "name")].copy()

    combos: set[tuple[int, int, int]] = set()
    for _, r in data.iterrows():
        v_hv = _parse_voltage(r["bus0"])
        v_lv = _parse_voltage(r["bus1"])
        s_nom = pd.to_numeric(r["s_nom"], errors="coerce")
        if v_hv is None or v_lv is None or pd.isna(s_nom):
            continue
        combos.add((int(v_hv), int(v_lv), int(s_nom)))
    return sorted(combos)


# ── Output ─────────────────────────────────────────────────────────────────

def main() -> None:
    combos  = _enumerate_combos(RAW_PATH)
    missing = [c for c in combos if c not in X_PU_LOOKUP]
    extra   = [c for c in X_PU_LOOKUP if c not in combos]

    print("=" * 60)
    print("Transformer x_pu coverage report")
    print("=" * 60)
    print(f"\n  Combos in xlsx        : {len(combos)}")
    print(f"  Combos in X_PU_LOOKUP : {len(X_PU_LOOKUP)}")
    print(f"  Missing from lookup   : {len(missing)}")
    print(f"  Extra in lookup       : {len(extra)}")

    if missing:
        print("\n  !!  Missing combos (need research):")
        for v_hv, v_lv, s in missing:
            print(f"       (v_hv={v_hv} kV, v_lv={v_lv} kV, s_nom={s} MVA)")
    if extra:
        print("\n  !!  Stale combos (no longer in xlsx):")
        for v_hv, v_lv, s in extra:
            print(f"       (v_hv={v_hv} kV, v_lv={v_lv} kV, s_nom={s} MVA)")

    if missing:
        raise SystemExit(
            "\nFAIL: missing x_pu values; add them to X_PU_LOOKUP and rerun."
        )

    out = {
        "r_pu_default": R_PU_DEFAULT,
        "x_pu_by_combo": {
            f"{v_hv}_{v_lv}_{s}": x
            for (v_hv, v_lv, s), x in sorted(X_PU_LOOKUP.items())
        },
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))

    print(f"\n  r_pu default          : {R_PU_DEFAULT}")
    print(f"  Written -> {OUT_PATH.relative_to(ROOT)}")
    print(f"  All {len(combos)} combos covered.")
    print("\nDone.")


if __name__ == "__main__":
    main()

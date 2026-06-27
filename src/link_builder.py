"""
link_builder.py

Reads data/pipeline/raw/link-data.xlsx and produces:
  data/pipeline/canonical/links.csv        — canonical link table
  data/pipeline/pypsa-components/links.csv — PyPSA-ready (name as index)

Used for HVDC interconnectors and cross-border NTC-style imports — i.e.
controllable directed flows that should be modelled as PyPSA Links rather
than as Generators or Lines.

PyPSA Link attribute reference:
    https://docs.pypsa.org/latest/user-guide/components/links/

Run:
    python src/link_builder.py
"""

import re
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent
PIPELINE_DIR  = ROOT / "data" / "pipeline"
RAW_PATH      = PIPELINE_DIR / "raw" / "link-data.xlsx"
CANONICAL_DIR = PIPELINE_DIR / "canonical"
PYPSA_DIR     = PIPELINE_DIR / "pypsa-components"


# ── Helpers ────────────────────────────────────────────────────────────────

def _carrier_from_buses(bus0: str, bus1: str) -> str:
    """DC if either endpoint name ends with '_DC' (case-insensitive), else AC."""
    if re.search(r'_DC\b', bus0, re.IGNORECASE) or re.search(r'_DC\b', bus1, re.IGNORECASE):
        return "DC"
    return "AC"


# ── Processing ─────────────────────────────────────────────────────────────

def process_raw_data(path: Path) -> tuple[pd.DataFrame, dict]:
    """
    Returns (data_df, warnings).

    Detects the PyPSA attribute header row by scanning for the row that
    contains 'name', 'bus0', 'bus1'. Same trick as the other builders.
    """
    warnings: dict[str, list[str]] = {
        "zero_p_nom":      [],
        "p_min_above_max": [],
    }

    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=str)

    pypsa_row_idx = None
    for i, row in raw.iterrows():
        cells = row.fillna("").astype(str).str.strip().tolist()
        if "name" in cells and "bus0" in cells and "bus1" in cells:
            pypsa_row_idx = i
            break
    if pypsa_row_idx is None:
        raise ValueError(f"Could not find PyPSA header row in {path}")

    pypsa_names  = raw.iloc[pypsa_row_idx].fillna("").astype(str).str.strip().tolist()
    human_labels = raw.iloc[pypsa_row_idx - 1].fillna("").astype(str).str.strip().tolist()

    def _make_col(pypsa: str, human: str) -> str | None:
        if pypsa:
            return pypsa
        if human:
            return re.sub(r'\W+', '_', human.lower()).strip('_')
        return None

    cols = [_make_col(p, h) for p, h in zip(pypsa_names, human_labels)]

    data = raw.iloc[pypsa_row_idx + 1:].reset_index(drop=True)
    data.columns = cols
    data = data.loc[:, [c for c in cols if c is not None]].copy()

    data = data[data["name"].notna()].copy()
    data = data[data["name"].str.strip() != "name"].copy()
    data["name"] = data["name"].str.strip()
    data["bus0"] = data["bus0"].str.strip()
    data["bus1"] = data["bus1"].str.strip()

    data["p_nom"]    = pd.to_numeric(data["p_nom"], errors="coerce").fillna(0.0)
    data["p_min_pu"] = pd.to_numeric(data["p_min_pu"], errors="coerce").fillna(0.0)

    # marginal_cost column may be entirely absent (header without values) or
    # present-but-empty; coerce to numeric, default 0 (PyPSA default).
    if "marginal_cost" in data.columns:
        data["marginal_cost"] = pd.to_numeric(data["marginal_cost"], errors="coerce").fillna(0.0)
    else:
        data["marginal_cost"] = 0.0

    data["carrier"] = data.apply(lambda r: _carrier_from_buses(r["bus0"], r["bus1"]), axis=1)

    for _, r in data.iterrows():
        if r["p_nom"] <= 0:
            warnings["zero_p_nom"].append(r["name"])
        if r["p_min_pu"] > 1.0:  # PyPSA p_max_pu default is 1.0
            warnings["p_min_above_max"].append(f"{r['name']} (p_min_pu={r['p_min_pu']})")

    return data, warnings


# ── Output ─────────────────────────────────────────────────────────────────

def _print_warnings(warnings: dict) -> None:
    sections = [
        ("zero_p_nom",      "links with zero or negative p_nom"),
        ("p_min_above_max", "links with p_min_pu > p_max_pu default (1.0)"),
    ]
    any_warnings = False
    for key, label in sections:
        items = warnings[key]
        if not items:
            continue
        any_warnings = True
        print(f"\n  !!  {len(items)} {label}:")
        for item in items:
            print(f"       {item}")
    if not any_warnings:
        print("\n  OK  No warnings.")


def main() -> None:
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    PYPSA_DIR.mkdir(parents=True, exist_ok=True)

    data, warnings = process_raw_data(RAW_PATH)

    dups = data["name"][data["name"].duplicated()].tolist()
    if dups:
        raise ValueError(f"Duplicate link names: {dups}")

    # ── Canonical output ──────────────────────────────────────────────────
    canonical = data[[
        "name", "bus0", "bus1", "carrier", "p_nom", "p_min_pu", "marginal_cost",
    ]].rename(columns={
        "p_nom":         "p_nom_mw",
        "marginal_cost": "marginal_cost_usd_mwh",
    })
    canonical.to_csv(CANONICAL_DIR / "links.csv", index=False)

    # ── PyPSA-ready output ────────────────────────────────────────────────
    # `efficiency` and `p_max_pu` omitted — defaults (1.0) apply.
    pypsa_out = data.set_index("name")[[
        "bus0", "bus1", "carrier", "p_nom", "p_min_pu", "marginal_cost",
    ]]
    pypsa_out.to_csv(PYPSA_DIR / "links.csv")

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("Processing summary")
    print("=" * 60)
    print(f"\n  Total links      : {len(data)}")
    print(f"  Total p_nom (MW) : {data['p_nom'].sum():.0f}")

    print("\n  By carrier:")
    for carrier, grp in data.groupby("carrier"):
        print(f"    {carrier:<3}   {len(grp):>2}   ({grp['p_nom'].sum():.0f} MW)")

    _print_warnings(warnings)

    print(f"\n  Written -> data/pipeline/canonical/links.csv")
    print(f"  Written -> data/pipeline/pypsa-components/links.csv")
    print("\nDone.")


if __name__ == "__main__":
    main()

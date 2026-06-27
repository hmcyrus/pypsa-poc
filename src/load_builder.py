"""
load_builder.py

Reads data/pipeline/raw/load-data.xlsx and produces:
  data/pipeline/canonical/loads.csv        — canonical load table
  data/pipeline/pypsa-components/loads.csv — PyPSA-ready (name as index)

Run:
    python src/load_builder.py
"""

import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent
PIPELINE_DIR  = ROOT / "data" / "pipeline"
RAW_PATH      = PIPELINE_DIR / "raw" / "load-data.xlsx"
CANONICAL_DIR = PIPELINE_DIR / "canonical"
PYPSA_DIR     = PIPELINE_DIR / "pypsa-components"


# ── Processing ─────────────────────────────────────────────────────────────

def process_raw_data(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=str)

    # Detect the PyPSA attribute header row (contains 'name', 'bus', 'p_set')
    pypsa_row_idx = None
    for i, row in raw.iterrows():
        cells = row.fillna("").astype(str).str.strip().tolist()
        if "name" in cells and "bus" in cells and "p_set" in cells:
            pypsa_row_idx = i
            break
    if pypsa_row_idx is None:
        raise ValueError(f"Could not find PyPSA attribute header row in {path}")

    pypsa_names  = raw.iloc[pypsa_row_idx].fillna("").astype(str).str.strip().tolist()
    human_labels = raw.iloc[pypsa_row_idx - 1].fillna("").astype(str).str.strip().tolist()

    # Prefer pypsa name; fall back to snake_case human label; drop fully empty
    def _make_col(pypsa: str, human: str) -> str | None:
        if pypsa:
            return pypsa
        if human:
            import re
            return re.sub(r'\W+', '_', human.lower()).strip('_')
        return None

    cols = [_make_col(p, h) for p, h in zip(pypsa_names, human_labels)]

    data = raw.iloc[pypsa_row_idx + 1:].reset_index(drop=True)
    data.columns = cols
    data = data.loc[:, [c for c in cols if c is not None]].copy()

    # Drop rows without a name or that are header echoes
    data = data[data["name"].notna()].copy()
    data = data[data["name"].str.strip() != "name"].copy()
    data["name"] = data["name"].str.strip()

    data["p_set"] = pd.to_numeric(data["p_set"], errors="coerce").fillna(0.0)
    data["q_set"] = pd.to_numeric(data["q_set"], errors="coerce").fillna(0.0)

    data["bus"] = data["bus"].apply(
        lambda v: str(v).strip() if pd.notna(v) and str(v).strip().lower() not in ("nan", "none", "") else ""
    )

    return data


# ── Output ─────────────────────────────────────────────────────────────────

def main() -> None:
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    PYPSA_DIR.mkdir(parents=True, exist_ok=True)

    data = process_raw_data(RAW_PATH)

    # ── Canonical output ──────────────────────────────────────────────────
    canonical = data[["name", "bus", "p_set", "q_set"]].copy()
    canonical = canonical.rename(columns={"p_set": "p_set_mw", "q_set": "q_set_mvar"})
    canonical.to_csv(CANONICAL_DIR / "loads.csv", index=False)

    # ── PyPSA-ready output ────────────────────────────────────────────────
    pypsa_out = data.set_index("name")[["bus", "p_set", "q_set"]]
    pypsa_out.to_csv(PYPSA_DIR / "loads.csv")

    # ── Summary ───────────────────────────────────────────────────────────
    n_zero = (data["p_set"] == 0).sum()
    missing_bus = (data["bus"] == "").sum()

    print("=" * 60)
    print("Processing summary")
    print("=" * 60)
    print(f"\n  Total loads      : {len(data)}")
    print(f"  Zero-load entries: {n_zero}")
    print(f"  Missing bus      : {missing_bus}")
    print(f"\n  Written -> data/pipeline/canonical/loads.csv")
    print(f"  Written -> data/pipeline/pypsa-components/loads.csv")
    print("\nDone.")


if __name__ == "__main__":
    main()

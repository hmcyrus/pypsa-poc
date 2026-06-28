#!/usr/bin/env python3
"""
line-bus-processor.py

Reads data/pipeline/raw/linedata.xlsx and produces:
  data/pipeline/canonical/buses.csv        — canonical bus table
  data/pipeline/canonical/lines.csv        — canonical line table
  data/pipeline/pypsa-components/buses.csv — PyPSA-ready (name as index)
  data/pipeline/pypsa-components/lines.csv — PyPSA-ready (name as index)
"""

import math
import re
import sys
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent
PIPELINE_DIR  = ROOT / "data" / "pipeline"
RAW_XLSX      = PIPELINE_DIR / "raw" / "linedata.xlsx"
CANONICAL_DIR = PIPELINE_DIR / "canonical"
PYPSA_DIR     = PIPELINE_DIR / "pypsa-components"

# ── Conductor lookup (per-km values) ──────────────────────────────────────
CONDUCTOR_PARAMS: dict[str, dict] = {
    "Finch":                 {"r_km": 0.0588524,  "x_km": 0.1968333, "b_km": 5.97e-6,  "ampacity": 1000},
    "Twin Finch":            {"r_km": 0.0294262,  "x_km": 0.1377833, "b_km": 1.19e-5,  "ampacity": 2000},
    "Quad Finch":            {"r_km": 0.0147131,  "x_km": 0.1082583, "b_km": 2.72e-5,  "ampacity": 4000},
    "Quad Egret":            {"r_km": 0.025346,   "x_km": 0.115775,  "b_km": 2.51e-5,  "ampacity": 2868},
    "Mallard":               {"r_km": 0.0812452,  "x_km": 0.2034167, "b_km": 5.73e-6,  "ampacity":  824},
    "Twin Mallard":          {"r_km": 0.0406226,  "x_km": 0.1423917, "b_km": 1.15e-5,  "ampacity": 1648},
    "Quad Mallard":          {"r_km": 0.0203113,  "x_km": 0.1118792, "b_km": 2.60e-5,  "ampacity": 3296},
    "Twin 300 sq mm":        {"r_km": 0.044528,   "x_km": 0.1527167, "b_km": 1.08e-5,  "ampacity": 1370},
    "Twin AAAC 37/4.176 mm": {"r_km": 0.0342056,  "x_km": 0.14315,   "b_km": 1.15e-5,  "ampacity": 1806},
    "ACSR 600 sq mm":        {"r_km": 0.0552,     "x_km": 0.1965833, "b_km": 6.01e-6,  "ampacity": 1037},
    "XLPE 2000 sq mm":       {"r_km": 0.0184,     "x_km": 0.06552,   "b_km": 2.00e-6,  "ampacity": 3000},
    "Grosbeak":              {"r_km": 0.101292,   "x_km": 0.21325,   "b_km": 5.48e-6,  "ampacity":  712},
    "Linnet":                {"r_km": 0.190992,   "x_km": 0.23325,   "b_km": 4.98e-6,  "ampacity":  478},
    "AAAC 804 sq mm":        {"r_km": 0.0419244,  "x_km": 0.1856667, "b_km": 6.36e-6,  "ampacity": 1241},
    "Hawk":                  {"r_km": 0.134872,   "x_km": 0.2225833, "b_km": 5.24e-6,  "ampacity":  594},
    "XLPE 500 sq mm":        {"r_km": 0.0736,     "x_km": 0.26208,   "b_km": 8.01e-6,  "ampacity":  750},
    "Cu 240 sq mm":          {"r_km": 0.134872,   "x_km": 0.2225833, "b_km": 5.24e-6,  "ampacity":  594},
    "XLPE 800 sq mm":        {"r_km": 0.0736,     "x_km": 0.26208,   "b_km": 8.01e-6,  "ampacity":  750},
}

CONDUCTOR_NORMALIZE: dict[str, str] = {
    "Twin 300 sqmm": "Twin 300 sq mm",
    "Twin AAAC":     "Twin AAAC 37/4.176 mm",
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _normalize_conductor(raw: str) -> str:
    raw = raw.strip()
    return CONDUCTOR_NORMALIZE.get(raw, raw)


def _parse_v_nom(bus_name: str) -> float | None:
    m = re.search(r'(\d+(?:\.\d+)?)kV', bus_name, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _line_params(conductor: str, length_km: float, v_nom_kv: float) -> dict:
    c = CONDUCTOR_PARAMS[conductor]
    return {
        "r":     round(c["r_km"] * length_km, 6),
        "x":     round(c["x_km"] * length_km, 6),
        "b":     round(c["b_km"] * length_km, 9),
        "s_nom": round((math.sqrt(3) * v_nom_kv * c["ampacity"]) / 1000, 3),
    }


# ── Processing pipeline ────────────────────────────────────────────────────

def process_raw_data(raw_xlsx: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Returns (buses_df, lines_df, warnings).

    XLSX layout (1-indexed rows, first/only sheet):
      Row 1 — metadata note
      Row 2 — human-readable column names
      Row 3 — pypsa attribute names (used as column headers)
      Row 4+ — data
    Expected column names: name, bus0, bus1, length_km, conductor, r, x, b, s_nom
    """
    warnings: dict[str, list[str]] = {
        "typo_buses":            [],
        "skipped_cross_voltage": [],
        "skipped_duplicates":    [],
        "unknown_conductor":     [],
    }

    data = pd.read_excel(raw_xlsx, sheet_name=0, header=2, dtype=str)
    # Columns D & E lack PyPSA attribute names in row 3 (they are inputs,
    # not PyPSA attributes); assign their canonical names explicitly.
    data.rename(columns={data.columns[3]: "length_km", data.columns[4]: "conductor"}, inplace=True)

    # Buses
    all_bus_names: set[str] = set()
    for col in ("bus0", "bus1"):
        for val in data[col].dropna():
            v = str(val).strip()
            if v:
                all_bus_names.add(v)

    bus_rows = []
    for bus_name in sorted(all_bus_names):
        v_nom = _parse_v_nom(bus_name)
        if v_nom is None:
            warnings["typo_buses"].append(bus_name)
        bus_rows.append({"name": bus_name, "v_nom": v_nom})

    buses_df = pd.DataFrame(bus_rows)

    # Lines
    seen_names: set[str] = set()
    line_rows = []

    for idx, row in data.iterrows():
        name       = str(row["name"]).strip()       if pd.notna(row["name"])       else ""
        bus0       = str(row["bus0"]).strip()       if pd.notna(row["bus0"])       else ""
        bus1       = str(row["bus1"]).strip()       if pd.notna(row["bus1"])       else ""
        length_str = str(row["length_km"]).strip()  if pd.notna(row["length_km"])  else ""
        cond_raw   = str(row["conductor"]).strip()  if pd.notna(row["conductor"])  else ""

        if not name or not bus0 or not bus1:
            continue

        csv_row_num = idx + 4

        if name in seen_names:
            warnings["skipped_duplicates"].append(f"row {csv_row_num}: {name}")
            continue

        v0 = _parse_v_nom(bus0)
        v1 = _parse_v_nom(bus1)
        if v0 is None or v1 is None or v0 != v1:
            warnings["skipped_cross_voltage"].append(
                f"row {csv_row_num}: {name}  [{bus0} → {bus1}]  ({v0}kV vs {v1}kV)"
            )
            continue

        try:
            length_km = float(length_str)
        except ValueError:
            continue

        conductor = _normalize_conductor(cond_raw)
        if conductor not in CONDUCTOR_PARAMS:
            warnings["unknown_conductor"].append(f"row {csv_row_num}: '{cond_raw}'")
            continue

        params = _line_params(conductor, length_km, v0)
        seen_names.add(name)
        line_rows.append({"name": name, "bus0": bus0, "bus1": bus1, "length": length_km, **params})

    lines_df = pd.DataFrame(line_rows)
    return buses_df, lines_df, warnings


# ── Output ─────────────────────────────────────────────────────────────────

def _print_warnings(warnings: dict) -> None:
    sections = [
        ("typo_buses",            "buses with unparseable voltage (excluded from network)"),
        ("skipped_cross_voltage", "lines skipped — mismatched bus voltages"),
        ("skipped_duplicates",    "lines skipped — duplicate name (first kept)"),
        ("unknown_conductor",     "lines skipped — conductor not in lookup table"),
    ]
    any_warnings = False
    for key, label in sections:
        items = warnings[key]
        if not items:
            continue
        any_warnings = True
        print(f"\n  ⚠  {len(items)} {label}:")
        for item in items:
            print(f"       {item}")
    if not any_warnings:
        print("\n  ✓  No warnings.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    PYPSA_DIR.mkdir(parents=True, exist_ok=True)

    buses_df, lines_df, warnings = process_raw_data(RAW_XLSX)

    pypsa_buses = buses_df.dropna(subset=["v_nom"]).set_index("name")
    pypsa_lines = lines_df.set_index("name")

    # ── Canonical output ──────────────────────────────────────────────────
    buses_df.to_csv(CANONICAL_DIR / "buses.csv", index=False)
    lines_df.to_csv(CANONICAL_DIR / "lines.csv", index=False)

    # ── PyPSA-ready output ────────────────────────────────────────────────
    pypsa_buses.to_csv(PYPSA_DIR / "buses.csv")
    pypsa_lines.to_csv(PYPSA_DIR / "lines.csv")

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("Processing summary")
    print("=" * 60)
    print(f"\n  Unique buses : {len(buses_df)}")
    print(f"  Lines        : {len(lines_df)}")

    print("\n  Buses by voltage level:")
    for v, grp in buses_df.dropna(subset=["v_nom"]).groupby("v_nom"):
        print(f"    {int(v):>4} kV — {len(grp):>3} buses")

    def _v(name):
        m = re.search(r'(\d+(?:\.\d+)?)kV', name, re.IGNORECASE)
        return float(m.group(1)) if m else None

    print("\n  Lines by voltage level:")
    lines_df["_v"] = lines_df["bus0"].apply(_v)
    for v, grp in lines_df.groupby("_v"):
        print(f"    {int(v):>4} kV — {len(grp):>3} lines")
    lines_df.drop(columns=["_v"], inplace=True)

    _print_warnings(warnings)

    print(f"\n  Written → data/pipeline/canonical/buses.csv")
    print(f"  Written → data/pipeline/canonical/lines.csv")
    print(f"  Written → data/pipeline/pypsa-components/buses.csv")
    print(f"  Written → data/pipeline/pypsa-components/lines.csv")
    print("\nDone.")


if __name__ == "__main__":
    main()

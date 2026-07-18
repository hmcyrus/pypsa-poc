"""
production_cost_estimator.py — estimate the grid's daily electricity production
cost from a parsed PGCB daily report (run src/daily_report_parser.py first).

Two independent cost tiers per plant:
  Tier A: heat rate (by technology) x fuel price (Tk/MJ) + variable O&M
  Tier B: MC_REF all-in marginal-cost anchors from generator_builder.py
          (USD/MWh, log-log interpolated on capacity) x FX
Imports (Adani, Bheramara HVDC, Nepal, Tripura) are priced at assumed purchase
tariffs in both tiers. Parameters live in data/production-cost/fuel_params.json.

The estimate is validated against the actuals printed in the report itself
(summary.csv): production cost Tk/kWh, energy generated, gas supplied MMCFD,
and the per-fuel energy split from En-Curve (fuel_curve.csv).

Usage:
    python src/production_cost_estimator.py [data-date]     # e.g. 2026-07-01
    (defaults to the latest folder under data/pipeline/canonical/daily-reports/)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
REPORTS_DIR = ROOT / "data" / "pipeline" / "canonical" / "daily-reports"
PARAMS_DIR = ROOT / "data" / "production-cost"

sys.path.insert(0, str(Path(__file__).parent))
from generator_builder import HSD_PREMIUM, MC_REF, log_linear_interp  # noqa: E402

FUEL_SUFFIX_RE = re.compile(r"\s*\((Gas|HSD|HFO)\)\s*$")

# MC_REF fuel-category key per report fuel string
MC_CATEGORY = {"Gas": "gas", "HFO": "liquid", "HSD": "liquid", "Coal": "coal",
               "Hydro": "hydro", "Solar": "solar", "Wind": "wind"}

IMPORT_TARIFF_KEY = [
    (re.compile(r"adani", re.I), "adani"),
    (re.compile(r"bheramara\s*\(\s*hvdc", re.I), "hvdc_india"),
    (re.compile(r"nepal", re.I), "nepal"),
    (re.compile(r"tripura", re.I), "tripura"),
]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def assign_tech(name: str, fuel: str) -> str:
    """Technology class for heat-rate / MC_REF lookup, from fuel + name pattern."""
    if fuel == "Solar":
        return "Solar PV"
    if fuel == "Wind":
        return "Wind"
    if fuel == "Hydro":
        return "Hydro"
    if fuel == "Coal":
        return "Steam Turbine"
    n = name.lower()
    if "ccpp" in n or "ccp" in n or "combined" in n:
        return "CCGT"
    if "tpp" in n:
        return "Steam Turbine"
    if "gtpp" in n or "peaking gt" in n or re.search(r"\bgt\b", n) or "simple cy" in n:
        return "OCGT"
    return "ICE"


def tier_a_rate(tech: str, fuel: str, params: dict) -> float:
    """Tk/kWh from heat rate x fuel price + VOM (0 fuel for renewables/hydro)."""
    vom = params["vom_tk_per_kwh"].get(fuel, params["vom_tk_per_kwh"]["default"])
    if fuel in ("Solar", "Wind", "Hydro"):
        return vom
    hr_key = f"Steam Turbine_{ {'Gas': 'gas', 'Coal': 'coal'}.get(fuel, 'liquid') }" \
        if tech == "Steam Turbine" else tech
    hr = params["heat_rate_mj_per_kwh"][hr_key]
    price = params["fuel_price_tk_per_mj"][fuel]
    return hr * price + vom


def tier_b_rate(tech: str, fuel: str, capacity_mw: float, params: dict) -> float | None:
    """Tk/kWh from generator_builder's MC_REF (USD/MWh) at this plant's size."""
    cat = MC_CATEGORY.get(fuel)
    points = MC_REF.get(tech, {}).get(cat)
    if points is None:
        return None
    p = capacity_mw if capacity_mw and capacity_mw > 0 else points[0][0]
    usd_mwh = log_linear_interp(p, points)
    if fuel == "HSD":
        usd_mwh *= HSD_PREMIUM
    return usd_mwh * params["fx_bdt_per_usd"] / 1000.0


def import_rate(name: str, params: dict) -> float | None:
    for pat, key in IMPORT_TARIFF_KEY:
        if pat.search(name):
            return params["import_tariff_tk_per_kwh"][key]
    return None


def main() -> None:
    if len(sys.argv) > 2:
        sys.exit("Usage: python src/production_cost_estimator.py [YYYY-MM-DD]")
    if len(sys.argv) == 2:
        day_dir = REPORTS_DIR / sys.argv[1]
    else:
        candidates = sorted(d for d in REPORTS_DIR.iterdir() if d.is_dir())
        if not candidates:
            sys.exit(f"No parsed reports under {REPORTS_DIR}")
        day_dir = candidates[-1]
    if not day_dir.exists():
        sys.exit(f"Not found: {day_dir} (run src/daily_report_parser.py first)")
    date = day_dir.name
    print(f"Estimating production cost for {date}\n")

    params = json.loads((PARAMS_DIR / "fuel_params.json").read_text())
    overrides = {k: v for k, v in
                 json.loads((PARAMS_DIR / "plant_name_overrides.json").read_text()).items()
                 if not k.startswith("_")}

    gen = pd.read_csv(day_dir / "plant_generation.csv")
    attrs = pd.read_csv(day_dir / "plant_attributes.csv")
    summary = pd.read_csv(day_dir / "summary.csv").set_index("metric")["value"]
    fuel_curve = pd.read_csv(day_dir / "fuel_curve.csv")

    # ── fuel assignment ───────────────────────────────────────────────────
    attrs_by_norm = {norm(n): r for n, r in
                     attrs.dropna(subset=["fuel"]).set_index("name").iterrows()}

    rows = []
    unmatched = []
    for _, g in gen.iterrows():
        name = g["name"]
        rec = {"name": name, "capacity_mw": g["capacity_mw"], "area": g["area"],
               "energy_kwh": g["total_kwh"] or 0.0, "is_import": g["is_import"]}

        if g["is_import"]:
            rec.update(fuel="Import", tech="Import", producer="Import",
                       match="import")
            rows.append(rec)
            continue

        suffix = FUEL_SUFFIX_RE.search(name)
        base = FUEL_SUFFIX_RE.sub("", overrides.get(name, name))
        attr = attrs_by_norm.get(norm(base))
        if attr is not None:
            fuel = suffix.group(1) if suffix else attr["fuel"]
            rec.update(fuel=fuel, producer=attr["producer"],
                       match="suffix" if suffix else "exact")
        elif suffix:  # no attribute row, but fuel is in the column name
            rec.update(fuel=suffix.group(1), producer=None, match="suffix-only")
        else:
            rec.update(fuel=None, producer=None, match="UNMATCHED")
            unmatched.append(name)
        if rec["fuel"]:
            rec["tech"] = assign_tech(base, rec["fuel"])
        rows.append(rec)

    df = pd.DataFrame(rows)

    # ── cost rates ────────────────────────────────────────────────────────
    def rates(r):
        if r["is_import"]:
            t = import_rate(r["name"], params)
            return pd.Series({"tier_a_tk_per_kwh": t, "tier_b_tk_per_kwh": t})
        if not r["fuel"]:
            return pd.Series({"tier_a_tk_per_kwh": None, "tier_b_tk_per_kwh": None})
        return pd.Series({
            "tier_a_tk_per_kwh": tier_a_rate(r["tech"], r["fuel"], params),
            "tier_b_tk_per_kwh": tier_b_rate(r["tech"], r["fuel"], r["capacity_mw"], params),
        })

    df = pd.concat([df, df.apply(rates, axis=1)], axis=1)
    df["tier_a_cost_tk"] = df["energy_kwh"] * df["tier_a_tk_per_kwh"]
    df["tier_b_cost_tk"] = df["energy_kwh"] * df["tier_b_tk_per_kwh"]

    out_csv = PARAMS_DIR / f"{date}-production-cost.csv"
    df.sort_values("energy_kwh", ascending=False).to_csv(out_csv, index=False)

    # ── summary ───────────────────────────────────────────────────────────
    total_kwh = df["energy_kwh"].sum()
    unmatched_kwh = df.loc[df["match"] == "UNMATCHED", "energy_kwh"].sum()
    a_total = df["tier_a_cost_tk"].sum()
    b_total = df["tier_b_cost_tk"].sum()
    actual_rate = summary.get("production_cost_tk_per_kwh")
    actual_mkwh = summary.get("energy_generated_mkwh")

    print(f"Energy accounted      : {total_kwh / 1e6:10.2f} MkWh"
          f"   (P1 actual: {actual_mkwh:.2f} MkWh)")
    print(f"Unmatched energy      : {unmatched_kwh / 1e6:10.4f} MkWh"
          f"   ({100 * unmatched_kwh / total_kwh:.2f} % — target < 1 %)")
    if unmatched:
        print(f"   unmatched plants   : {unmatched}")

    print(f"\nTier A (heat rate x fuel price):")
    print(f"   total cost         : {a_total / 1e6:10.1f} M Tk")
    print(f"   average rate       : {a_total / total_kwh:10.3f} Tk/kWh")
    print(f"Tier B (MC_REF anchors):")
    print(f"   total cost         : {b_total / 1e6:10.1f} M Tk")
    print(f"   average rate       : {b_total / total_kwh:10.3f} Tk/kWh")
    if actual_rate is not None:
        print(f"P1 actual             : {actual_rate:10.3f} Tk/kWh"
              f"   (Tier A deviation {100 * (a_total / total_kwh - actual_rate) / actual_rate:+.1f} %,"
              f" Tier B {100 * (b_total / total_kwh - actual_rate) / actual_rate:+.1f} %)")

    # per-fuel breakdown vs En-Curve
    print(f"\nPer-fuel energy and cost (Tier A):")
    by_fuel = (df.groupby("fuel", dropna=False)
                 .agg(energy_mkwh=("energy_kwh", lambda s: s.sum() / 1e6),
                      cost_mtk=("tier_a_cost_tk", lambda s: s.sum() / 1e6),
                      plants=("name", "size")))
    by_fuel["avg_tk_per_kwh"] = by_fuel["cost_mtk"] / by_fuel["energy_mkwh"] * 1e0
    print(by_fuel.round(2).to_string())

    # En-Curve cross-check: half-hourly MW buckets -> MkWh shares
    bucket_map = {
        "Gas": ["gas_public", "gas_pvt"], "Coal": ["coal"], "Hydro": ["hydro"],
        "Solar": ["solar"], "Wind": ["wind"],
        "HFO": ["hfo_public", "hfo_pvt"], "HSD": ["hsd_public", "hsd_pvt"],
        "Import": ["hvdc", "nepal", "tripura", "adani"],
    }
    steps = len(fuel_curve)
    print(f"\nEn-Curve cross-check (report's own fuel split, {steps} half-hour points):")
    print(f"   {'fuel':<8} {'En-Curve MkWh':>14} {'model MkWh':>12}")
    for fuel, cols in bucket_map.items():
        present = [c for c in cols if c in fuel_curve.columns]
        encurve_mkwh = fuel_curve[present].sum().sum() * 0.5 / 1e3  # MW * 0.5h -> MWh -> GWh==MkWh
        model = by_fuel["energy_mkwh"].get(fuel, 0.0)
        print(f"   {fuel:<8} {encurve_mkwh:>14.2f} {model:>12.2f}")

    # implied gas consumption vs P1
    gas = df[df["fuel"] == "Gas"]
    gas_mj = sum(
        r["energy_kwh"] * params["heat_rate_mj_per_kwh"][
            "Steam Turbine_gas" if r["tech"] == "Steam Turbine" else r["tech"]]
        for _, r in gas.iterrows())
    gas_mmcf = gas_mj / params["gas_lhv_mj_per_m3"] / 28316.8 / 1e3
    actual_gas = summary.get("gas_supplied_mmcfd")
    print(f"\nImplied gas burn      : {gas_mmcf * 1e3:10.1f} MMCF"
          f"   (P1 actual supplied: {actual_gas:.2f} MMCFD)"
          if actual_gas is not None else "")

    print(f"\nWritten -> {out_csv.relative_to(ROOT)}")
    print("Done.")


if __name__ == "__main__":
    main()

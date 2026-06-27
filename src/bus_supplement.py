"""
bus_supplement.py

Finalises the data/pipeline/pypsa-components/ folder so it can be loaded by
PyPSA's import_from_csv_folder cleanly. Two responsibilities:

1. Augments buses.csv with any bus name referenced by another PyPSA
   component (generator, load, transformer, line, link) that the line-
   derived buses.csv does not already contain. v_nom is parsed from the
   '_<N>kV' suffix in the bus name.

2. Writes network.csv with the current pypsa_version, matching what
   n.export_to_csv_folder would produce. Without this file, PyPSA's
   importer defaults to version "0.0.0" and runs backward-compat shims
   on every load — see assessment in conversation history.

Why (1) is needed: line-bus-processor.py derives buses only from line
endpoints, so buses that exist only as transformer LV sides, load points,
generator connections, or synthetic import boundaries (the *SendBus
endpoints of HVDC/cross-border Links) are otherwise missing — which
breaks PyPSA's consistency_check at network-build time.

Build order — must run LAST in the pipeline:

    python src/line-bus-processor.py
    python src/generator_builder.py
    python src/load_builder.py
    python src/transformer_builder.py
    python src/link_builder.py
    python src/bus_supplement.py        ← this script

Re-running line-bus-processor.py rewrites buses.csv from scratch and
discards supplements; re-run this script afterwards. Idempotent: a
second run with no source changes adds nothing.

Run:
    python src/bus_supplement.py
"""

import re
from pathlib import Path

import pandas as pd
import pypsa

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
PYPSA_DIR    = ROOT / "data" / "pipeline" / "pypsa-components"
BUSES_PATH   = PYPSA_DIR / "buses.csv"
NETWORK_PATH = PYPSA_DIR / "network.csv"
NETWORK_NAME = "pypsa-poc"

# Per-component bus-reference columns to scan.
REF_SOURCES: list[tuple[str, list[str]]] = [
    ("generators.csv",   ["bus"]),
    ("loads.csv",        ["bus"]),
    ("lines.csv",        ["bus0", "bus1"]),
    ("transformers.csv", ["bus0", "bus1"]),
    ("links.csv",        ["bus0", "bus1"]),
]


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_v_nom(bus: str) -> float | None:
    """Extract kV from a bus name like 'Agargaon_132kV' -> 132.0."""
    m = re.search(r'(\d+(?:\.\d+)?)kV', str(bus), re.IGNORECASE)
    return float(m.group(1)) if m else None


def _collect_refs() -> dict[str, set[str]]:
    """Map of source-file -> set of bus refs it contributes."""
    refs: dict[str, set[str]] = {}
    for fname, cols in REF_SOURCES:
        path = PYPSA_DIR / fname
        if not path.exists():
            refs[fname] = set()
            continue
        df = pd.read_csv(path)
        seen: set[str] = set()
        for c in cols:
            if c in df.columns:
                seen |= set(df[c].dropna().astype(str).str.strip())
        refs[fname] = {b for b in seen if b}
    return refs


# ── Output ─────────────────────────────────────────────────────────────────

def main() -> None:
    if not BUSES_PATH.exists():
        raise FileNotFoundError(
            f"{BUSES_PATH} not found — run line-bus-processor.py first."
        )

    buses    = pd.read_csv(BUSES_PATH)
    existing = set(buses["name"].astype(str).str.strip())
    refs_by_src = _collect_refs()
    all_refs    = set().union(*refs_by_src.values())

    missing  = sorted(all_refs - existing)
    added: list[tuple[str, float]] = []
    skipped: list[str]             = []
    for bus in missing:
        v_nom = _parse_v_nom(bus)
        if v_nom is None:
            skipped.append(bus)
            continue
        added.append((bus, v_nom))

    if added:
        supplement = pd.DataFrame(added, columns=["name", "v_nom"])
        out = pd.concat([buses, supplement], ignore_index=True)
        out.to_csv(BUSES_PATH, index=False)

    # ── network.csv metadata ──────────────────────────────────────────────
    # Matches the format PyPSA's export_to_csv_folder produces, so importers
    # see the right pypsa_version and skip backward-compat conversions.
    pd.DataFrame(
        {"pypsa_version": [pypsa.__version__]},
        index=pd.Index([NETWORK_NAME], name="name"),
    ).to_csv(NETWORK_PATH)

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("Bus supplement summary")
    print("=" * 60)
    print(f"\n  Existing buses     : {len(existing)}")
    print(f"  Unique refs        : {len(all_refs)}")
    print(f"  Already covered    : {len(all_refs & existing)}")
    print(f"  Newly added        : {len(added)}")
    print(f"  Skipped (no _kV)   : {len(skipped)}")

    print("\n  Refs by source file:")
    for fname, s in refs_by_src.items():
        not_in_buses = len(s - existing - {b for b, _ in added})
        print(f"    {fname:<20} {len(s):>4} refs   ({not_in_buses} still uncovered)")

    if skipped:
        print("\n  !!  Skipped buses (could not parse voltage):")
        for b in skipped:
            print(f"       {b}")

    if added:
        print("\n  Added buses (first 20):")
        for name, v in added[:20]:
            print(f"       {name:<42}  v_nom={v:.0f} kV")
        if len(added) > 20:
            print(f"       ... and {len(added) - 20} more")
        print(f"\n  Written -> data/pipeline/pypsa-components/buses.csv")
    else:
        print("\n  No new buses needed — buses.csv already covers all refs.")

    print(f"  Written -> data/pipeline/pypsa-components/network.csv  "
          f"(pypsa_version={pypsa.__version__})")
    print("\nDone.")


if __name__ == "__main__":
    main()

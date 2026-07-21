"""Topology-constrained OSM re-match for places the Phase-B sweep reopened or
Phase A left provisional/unresolved.

Candidates are restricted to the feasible region from Phase B (inside every
disc drawn around located neighbors). Because the constraint adds strong
independent evidence, the name-score acceptance bar is lower than Phase A's.

Run alternately with validate_locations.py until the counts stop moving:
    .venv\\Scripts\\python.exe src\\geo\\rematch_constrained.py
    .venv\\Scripts\\python.exe src\\geo\\validate_locations.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from osm_match import (  # noqa: E402
    CACHE_FILE,
    GEO_DIR,
    build_features,
    build_places,
    compatible,
    haversine_km,
    norm_text,
    score_pair,
)

ACCEPT_CONSTRAINED = 72.0
PROVISIONAL_CONSTRAINED = 55.0


def main() -> int:
    locs = pd.read_csv(GEO_DIR / "bus_locations.csv")
    regions = json.loads((GEO_DIR / "feasible_regions.json").read_text(encoding="utf-8"))
    osm = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    feats = build_features(osm)
    places = build_places().set_index("place")

    open_mask = locs["status"].isin(["reopened", "provisional", "unresolved"])
    changed = 0
    for idx, row in locs[open_mask].iterrows():
        region = regions.get(row["place"])
        if not region:
            continue
        discs = region["discs"]

        def in_region(lat, lon):
            return all(
                haversine_km(lat, lon, d["lat"], d["lon"]) <= d["radius_km"]
                for d in discs
            )

        p = places.loc[row["place"]]
        search_texts = [p["search_text"]]
        if p["generator_names"]:
            search_texts += [norm_text(g) for g in p["generator_names"].split("|")]
        search_texts = [s for s in dict.fromkeys(search_texts) if s]

        best_score, best_f = 0.0, None
        for _, f in feats.iterrows():
            if not compatible(p["class"], f["power"]):
                continue
            if not in_region(f["lat"], f["lon"]):
                continue
            s = max(
                (
                    score_pair(st, cand)
                    for st in search_texts
                    for cand in f["norm_names"]
                ),
                default=0.0,
            )
            if s > best_score:
                best_score, best_f = s, f

        if best_f is None or best_score < PROVISIONAL_CONSTRAINED:
            continue
        status = (
            "accepted" if best_score >= ACCEPT_CONSTRAINED else "provisional"
        )
        confidence = "high" if status == "accepted" else "medium"
        locs.loc[idx, ["lat", "lon", "matched_name", "osm_id", "feature_power",
                       "score", "confidence", "status", "note"]] = [
            best_f["lat"], best_f["lon"], best_f["display_name"], best_f["osm_id"],
            best_f["power"], round(best_score, 1), confidence, status,
            f"constrained re-match ({len(discs)} discs)",
        ]
        changed += 1

    locs.to_csv(GEO_DIR / "bus_locations.csv", index=False)
    print(f"re-matched {changed} places under feasible-region constraints")
    print(locs["status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

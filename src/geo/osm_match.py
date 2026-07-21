"""Phase A of the geocoding plan: normalize places, fetch OSM power features,
fuzzy-match, and emit an interim bus_locations.csv plus a leftover list.

Usage:
    .venv\\Scripts\\python.exe src\\geo\\osm_match.py [--refresh]

--refresh forces a new Overpass download instead of using the disk cache.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from rapidfuzz import fuzz

REPO = Path(__file__).resolve().parents[2]
CANONICAL = REPO / "data" / "pipeline" / "canonical"
GEO_DIR = REPO / "data" / "pipeline" / "geo"
CACHE_FILE = GEO_DIR / "cache" / "overpass_power.json"

# Bangladesh bbox, padded so nearby India-side endpoints (Berhampore,
# Suryamaninagar) are still inside it. south,west,north,east
BBOX = "(20.5,88.0,26.75,92.75)"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Spelling aliases, canonicalized token -> canonical form. Applied per token in
# both the grid names and the OSM names.
ALIASES = {
    "bogra": "bogura",
    "jessore": "jashore",
    "comilla": "cumilla",
    "chittagong": "chattogram",
    "barisal": "barishal",
    "syedpur": "saidpur",
    "ishurdi": "ishwardi",
    "eshwardi": "ishwardi",
    "narayangonj": "narayanganj",
    "brahmanbaria": "brahmanbaria",
    "coxs": "cox",
    "berhampur": "berhampore",
    "baharampur": "berhampore",
    "sreepur": "sripur",
    "keraniganj": "keraniganj",
    "maowa": "mawa",
}

# Tokens that carry no locating signal in either dataset.
STOPWORDS = {
    "substation", "sub", "station", "grid", "power", "electric", "electricity",
    "supply", "kv", "ais", "gis", "pgcb", "bpdb", "desco", "dpdc", "nesco",
    "wzpdcl", "bd", "ltd", "limited", "co", "company", "pp", "tpp", "ccpp",
    "gtpp", "spp", "pspp", "mw", "plant", "unit", "new", "old",
}

DIRECTIONAL = {"north", "south", "east", "west", "central"}

PLANT_NAME_HINTS = re.compile(r"(PP|CCPP|TPP|GTPP|SPP|PSPP|MW|HVDC)", re.ASCII)


def camel_split(name: str) -> list[str]:
    """AshuganjNorth -> [Ashuganj, North]; AESHaripur -> [AES, Haripur]."""
    name = re.sub(r"[^A-Za-z0-9]+", " ", name)
    parts = []
    for chunk in name.split():
        parts.extend(
            re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[A-Z]+|[a-z]+|\d+", chunk)
        )
    return parts


def norm_tokens(raw: str) -> list[str]:
    toks = [t.lower() for t in camel_split(raw)]
    toks = [ALIASES.get(t, t) for t in toks]
    return [t for t in toks if t and t not in STOPWORDS and not t.isdigit()]


def norm_text(raw: str) -> str:
    return " ".join(norm_tokens(raw))


# --------------------------------------------------------------------------
# A1: normalize & classify places
# --------------------------------------------------------------------------

def build_places() -> pd.DataFrame:
    buses = pd.read_csv(CANONICAL / "buses.csv")
    gens = pd.read_csv(CANONICAL / "generators.csv")

    buses["place"] = buses["name"].str.replace(r"_\d+(?:\.\d+)?kV$", "", regex=True)
    gens["place"] = gens["bus"].str.replace(r"_\d+(?:\.\d+)?kV$", "", regex=True)
    gen_names = gens.groupby("place")["name"].apply(list).to_dict()

    rows = []
    for place, grp in buses.groupby("place"):
        toks = camel_split(place)
        upper_acronym = any(t.isupper() and len(t) >= 3 for t in toks)
        has_gens = place in gen_names
        cross_border = (
            "RecvBus" in place
            or "SendBus" in place
            or "HVDC" in place
            or place in {"Berhampore", "Suryamaninagar"}
        )
        if cross_border:
            klass = "cross_border"
        elif has_gens or PLANT_NAME_HINTS.search(place):
            klass = "plant"
        elif upper_acronym:
            klass = "industrial"
        else:
            klass = "town"
        rows.append(
            {
                "place": place,
                "class": klass,
                "voltages": "|".join(
                    str(int(v)) for v in sorted(grp["v_nom"].unique())
                ),
                "bus_names": "|".join(sorted(grp["name"])),
                "search_text": norm_text(place),
                "generator_names": "|".join(gen_names.get(place, [])),
            }
        )
    return pd.DataFrame(rows).sort_values("place").reset_index(drop=True)


# --------------------------------------------------------------------------
# A2: Overpass fetch (cached)
# --------------------------------------------------------------------------

QUERY = f"""
[out:json][timeout:300];
(
  nwr["power"="substation"]{BBOX};
  nwr["power"="plant"]{BBOX};
  nwr["power"="generator"]["name"]{BBOX};
);
out center tags;
"""


def fetch_osm(refresh: bool) -> dict:
    if CACHE_FILE.exists() and not refresh:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    last_err = None
    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"Querying Overpass: {url}")
            resp = requests.post(
                url,
                data={"data": QUERY},
                timeout=360,
                headers={"User-Agent": "pypsa-poc-geocoder/0.1"},
            )
            resp.raise_for_status()
            data = resp.json()
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            return data
        except Exception as exc:  # noqa: BLE001 - want to try next mirror
            last_err = exc
            print(f"  failed ({exc}); trying next endpoint")
            time.sleep(5)
    raise RuntimeError(f"all Overpass endpoints failed: {last_err}")


NAME_TAGS = ["name", "name:en", "alt_name", "official_name", "operator"]


def build_features(osm: dict) -> pd.DataFrame:
    rows = []
    for el in osm.get("elements", []):
        tags = el.get("tags", {})
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center") or {}
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        names = []
        for tag in NAME_TAGS:
            val = tags.get(tag)
            if val:
                names.extend(re.split(r"[;/]", val))
        names = [n.strip() for n in names if n.strip() and n.strip() != "?"]
        if not names:
            continue
        norm_names = sorted({norm_text(n) for n in names} - {""})
        if not norm_names:
            continue
        rows.append(
            {
                "osm_id": f"{el['type']}/{el['id']}",
                "power": tags.get("power", ""),
                "display_name": names[0],
                "norm_names": norm_names,
                "voltage": tags.get("voltage", ""),
                "lat": lat,
                "lon": lon,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# A3: fuzzy match
# --------------------------------------------------------------------------

ACCEPT = 88.0
PROVISIONAL = 75.0
AMBIGUITY_MARGIN = 5.0
AMBIGUITY_KM = 15.0


def score_pair(place_text: str, cand_text: str) -> float:
    if not place_text or not cand_text:
        return 0.0
    # token_set alone scores "barishal" == "barishal north" at 100, hiding
    # directional mismatches; blending token_sort keeps them distinguishable.
    return 0.6 * fuzz.token_set_ratio(place_text, cand_text) + 0.4 * fuzz.token_sort_ratio(
        place_text, cand_text
    )


def haversine_km(lat1, lon1, lat2, lon2):
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compatible(klass: str, power: str) -> bool:
    if klass in ("town", "industrial", "cross_border"):
        return power in ("substation", "plant")
    if klass == "plant":
        return power in ("plant", "generator", "substation")
    return True


def match_places(places: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    results = []
    for _, p in places.iterrows():
        search_texts = [p["search_text"]]
        # plant buses inherit their generator names as extra search strings
        if p["generator_names"]:
            search_texts += [
                norm_text(g) for g in p["generator_names"].split("|")
            ]
        search_texts = [s for s in dict.fromkeys(search_texts) if s]

        scored = []
        for _, f in feats.iterrows():
            if not compatible(p["class"], f["power"]):
                continue
            best = max(
                (
                    score_pair(s, cand)
                    for s in search_texts
                    for cand in f["norm_names"]
                ),
                default=0.0,
            )
            if best >= PROVISIONAL - 10:
                scored.append((best, f))
        scored.sort(key=lambda t: -t[0])

        row = {
            **{k: p[k] for k in ["place", "class", "voltages", "bus_names"]},
            "lat": None,
            "lon": None,
            "matched_name": None,
            "osm_id": None,
            "feature_power": None,
            "score": None,
            "confidence": "none",
            "status": "unresolved",
            "source": "osm",
            "note": "",
        }
        if scored:
            best_score, best_f = scored[0]
            ambiguous = any(
                best_score - s <= AMBIGUITY_MARGIN
                and haversine_km(best_f["lat"], best_f["lon"], f["lat"], f["lon"])
                > AMBIGUITY_KM
                for s, f in scored[1:4]
            )
            row.update(
                lat=best_f["lat"],
                lon=best_f["lon"],
                matched_name=best_f["display_name"],
                osm_id=best_f["osm_id"],
                feature_power=best_f["power"],
                score=round(best_score, 1),
            )
            if best_score >= ACCEPT and not ambiguous:
                row.update(status="accepted", confidence="high")
            elif best_score >= PROVISIONAL:
                row.update(
                    status="provisional",
                    confidence="medium",
                    note="ambiguous: near-tied candidates far apart" if ambiguous else "",
                )
            else:
                row.update(status="unresolved", confidence="low")
        results.append(row)
    return pd.DataFrame(results)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore Overpass cache")
    args = ap.parse_args()

    places = build_places()
    print(f"A1: {len(places)} unique places "
          f"({places['class'].value_counts().to_dict()})")

    osm = fetch_osm(args.refresh)
    feats = build_features(osm)
    print(f"A2: {len(osm.get('elements', []))} OSM elements, "
          f"{len(feats)} named features "
          f"({feats['power'].value_counts().to_dict()})")

    out = match_places(places, feats)
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GEO_DIR / "bus_locations.csv"
    out.to_csv(out_path, index=False)

    leftovers = out[out["status"] != "accepted"]
    leftover_path = GEO_DIR / "leftovers.csv"
    leftovers.to_csv(leftover_path, index=False)

    print("A3 results:")
    print(out["status"].value_counts().to_string())
    print(f"\nWrote {out_path} ({len(out)} places)")
    print(f"Wrote {leftover_path} ({len(leftovers)} leftovers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

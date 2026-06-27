"""Convert pixel-space polylines to GeoJSON / CSV outputs."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import numpy as np

from .georef import Georef

_EARTH_R_KM = 6371.0088


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_R_KM * asin(sqrt(a))


def _polyline_length_km(coords: np.ndarray) -> float:
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords[:-1], coords[1:]):
        total += _haversine_km(float(lon1), float(lat1), float(lon2), float(lat2))
    return total


@dataclass
class GeoExportResult:
    features: list[dict]
    total_length_km: float
    geojson_path: Path
    csv_path: Path


@dataclass
class SubstationExportResult:
    features: list[dict]
    geojson_path: Path
    csv_path: Path


def export_polylines(
    polylines_px: list[np.ndarray],
    georef: Georef,
    out_dir: str | Path,
    *,
    conductor_label: str = "477 MCM",
    min_vertices: int = 2,
) -> GeoExportResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = out_dir / "red_lines.geojson"
    csv_path = out_dir / "red_lines_vertices.csv"

    features: list[dict] = []
    csv_rows: list[tuple[int, int, float, float]] = []
    total = 0.0

    for line_idx, poly in enumerate(polylines_px):
        if len(poly) < min_vertices:
            continue
        px = poly[:, 0].astype(float)
        py = poly[:, 1].astype(float)
        lonlat = georef.pixels_to_lonlat(px, py)
        length_km = _polyline_length_km(lonlat)
        total += length_km
        features.append({
            "type": "Feature",
            "properties": {
                "id": line_idx,
                "conductor": conductor_label,
                "length_km": round(length_km, 4),
                "n_vertices": int(len(lonlat)),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[float(lon), float(lat)] for lon, lat in lonlat],
            },
        })
        for vertex_idx, (lon, lat) in enumerate(lonlat):
            csv_rows.append((line_idx, vertex_idx, float(lon), float(lat)))

    geojson = {
        "type": "FeatureCollection",
        "name": f"reb_pbs_{conductor_label.lower().replace(' ', '_')}_lines",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    geojson_path.write_text(json.dumps(geojson, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["line_id", "vertex_idx", "lon", "lat"])
        writer.writerows(csv_rows)

    return GeoExportResult(
        features=features,
        total_length_km=total,
        geojson_path=geojson_path,
        csv_path=csv_path,
    )


def export_substations(
    centroids_px: list[tuple[int, int]],
    georef: Georef,
    out_dir: str | Path,
    *,
    label: str = "33/11 KV S/S (auto-detected)",
) -> SubstationExportResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = out_dir / "substations.geojson"
    csv_path = out_dir / "substations.csv"

    if centroids_px:
        px = np.array([c[0] for c in centroids_px], dtype=float)
        py = np.array([c[1] for c in centroids_px], dtype=float)
        lonlat = georef.pixels_to_lonlat(px, py)
    else:
        lonlat = np.zeros((0, 2), dtype=float)

    features: list[dict] = []
    csv_rows: list[tuple[int, float, float]] = []
    for idx, (lon, lat) in enumerate(lonlat):
        lon_f, lat_f = float(lon), float(lat)
        features.append({
            "type": "Feature",
            "properties": {"id": idx, "kind": label},
            "geometry": {"type": "Point", "coordinates": [lon_f, lat_f]},
        })
        csv_rows.append((idx, lon_f, lat_f))

    geojson = {
        "type": "FeatureCollection",
        "name": "reb_pbs_substations_auto",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    geojson_path.write_text(json.dumps(geojson, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "lon", "lat"])
        writer.writerows(csv_rows)

    return SubstationExportResult(features=features, geojson_path=geojson_path, csv_path=csv_path)

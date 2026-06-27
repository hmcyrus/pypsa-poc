"""Build a Folium HTML overlay for manual visual verification.

The HTML report stacks:

* OSM / Esri satellite / CartoDB basemaps (switchable via LayerControl).
* A cropped, partially-transparent rendering of the source PDF, placed at the
  graticule corners so red lines on the PDF sit directly over OSM.
* The extracted polylines (green, hover for length / vertex count).
* The extracted substation centroids (green circles).

Run after the main pipeline produced ``red_lines.geojson`` /
``substations.geojson``::

    python -m src.map_extract.validate --out data/pipeline/raw/pbs-2-lines
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import folium
import numpy as np

from .georef import Georef, fit_georef
from .main import DEFAULT_EXCLUSIONS_PDF_PTS
from .render import render_pdf

# Cap on the long edge of the PDF underlay PNG so the resulting HTML stays
# small enough to open quickly (folium base64-encodes it inline).
_OVERLAY_MAX_DIM_PX = 2400


def _graticule_bounds(georef: Georef) -> tuple[float, float, float, float]:
    lons = [g.value for g in georef.gcps if g.axis == "lon"]
    lats = [g.value for g in georef.gcps if g.axis == "lat"]
    return min(lons), min(lats), max(lons), max(lats)


def _build_pdf_underlay(
    image_bgr: np.ndarray,
    georef: Georef,
    dpi: float,
    exclusions_pdf_pts: tuple[tuple[float, float, float, float], ...],
) -> tuple[np.ndarray, list[list[float]]]:
    h, w = image_bgr.shape[:2]
    s = dpi / 72.0

    masked = image_bgr.copy()
    for x0, y0, x1, y1 in exclusions_pdf_pts:
        sx0 = max(0, int(round(x0 * s)))
        sy0 = max(0, int(round(y0 * s)))
        sx1 = min(w, int(round(x1 * s)))
        sy1 = min(h, int(round(y1 * s)))
        if sx1 > sx0 and sy1 > sy0:
            masked[sy0:sy1, sx0:sx1] = (255, 255, 255)

    lon_min, lat_min, lon_max, lat_max = _graticule_bounds(georef)
    px_west = (lon_min - georef.lon_fit.intercept) / georef.lon_fit.slope
    px_east = (lon_max - georef.lon_fit.intercept) / georef.lon_fit.slope
    py_north = (lat_max - georef.lat_fit.intercept) / georef.lat_fit.slope
    py_south = (lat_min - georef.lat_fit.intercept) / georef.lat_fit.slope

    x0 = max(0, int(round(min(px_west, px_east))))
    x1 = min(w, int(round(max(px_west, px_east))))
    y0 = max(0, int(round(min(py_north, py_south))))
    y1 = min(h, int(round(max(py_north, py_south))))
    cropped = masked[y0:y1, x0:x1]

    long_edge = max(cropped.shape[:2])
    if long_edge > _OVERLAY_MAX_DIM_PX:
        scale = _OVERLAY_MAX_DIM_PX / long_edge
        new_w = int(round(cropped.shape[1] * scale))
        new_h = int(round(cropped.shape[0] * scale))
        cropped = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_AREA)

    bounds = [[lat_min, lon_min], [lat_max, lon_max]]
    return cropped, bounds


def build_validation_map(
    pdf_path: Path,
    out_dir: Path,
    *,
    dpi: int = 200,
    opacity: float = 0.55,
    page_index: int = 0,
) -> Path:
    validation_dir = out_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    print("  rendering PDF for underlay ...")
    rendered = render_pdf(pdf_path, dpi=dpi, page_index=page_index)
    georef = fit_georef(pdf_path, dpi=dpi, page_index=page_index)

    print("  preparing cropped underlay ...")
    underlay_img, bounds = _build_pdf_underlay(
        rendered.image_bgr, georef, dpi, DEFAULT_EXCLUSIONS_PDF_PTS,
    )
    underlay_png = validation_dir / "pdf_underlay.png"
    cv2.imwrite(str(underlay_png), underlay_img)

    lines_path = out_dir / "red_lines.geojson"
    subs_path = out_dir / "substations.geojson"
    if not lines_path.exists():
        raise FileNotFoundError(
            f"missing {lines_path}; run `python -m src.map_extract.main` first"
        )
    lines_geojson = json.loads(lines_path.read_text(encoding="utf-8"))
    subs_geojson = (
        json.loads(subs_path.read_text(encoding="utf-8"))
        if subs_path.exists() else {"features": []}
    )

    center_lat = (bounds[0][0] + bounds[1][0]) / 2.0
    center_lon = (bounds[0][1] + bounds[1][1]) / 2.0
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=None, control_scale=True)

    folium.TileLayer("OpenStreetMap", name="OSM standard").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics",
        name="Esri World Imagery",
    ).add_to(m)
    folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(m)

    folium.raster_layers.ImageOverlay(
        image=str(underlay_png),
        bounds=bounds,
        opacity=opacity,
        interactive=False,
        cross_origin=False,
        name="PDF underlay (toggle to fade)",
    ).add_to(m)

    n_lines = len(lines_geojson.get("features", []))
    line_layer = folium.FeatureGroup(name=f"Extracted lines (n={n_lines})")
    folium.GeoJson(
        lines_geojson,
        style_function=lambda _f: {"color": "#00d000", "weight": 3, "opacity": 0.95},
        highlight_function=lambda _f: {"color": "#ffea00", "weight": 5},
        tooltip=folium.GeoJsonTooltip(
            fields=["id", "length_km", "n_vertices"],
            aliases=["line id", "length (km)", "vertices"],
            sticky=True,
        ),
    ).add_to(line_layer)
    line_layer.add_to(m)

    n_subs = len(subs_geojson.get("features", []))
    sub_layer = folium.FeatureGroup(name=f"Extracted substations (n={n_subs})")
    for feat in subs_geojson.get("features", []):
        lon, lat = feat["geometry"]["coordinates"]
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="#008c00",
            weight=2,
            fill=True,
            fill_color="#7dff7d",
            fill_opacity=0.65,
            tooltip=f"id={feat['properties']['id']}  lat={lat:.5f} lon={lon:.5f}",
        ).add_to(sub_layer)
    sub_layer.add_to(m)

    m.fit_bounds(bounds)
    folium.LayerControl(collapsed=False).add_to(m)

    html_path = validation_dir / "overlay.html"
    m.save(str(html_path))
    return html_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, default=Path("data/reb-dhaka-pbs-2.pdf"))
    p.add_argument("--out", type=Path, default=Path("data/pipeline/raw/pbs-2-lines"))
    p.add_argument("--dpi", type=int, default=200,
                   help="DPI for the underlay (lower = smaller HTML)")
    p.add_argument("--opacity", type=float, default=0.55)
    p.add_argument("--page", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    html = build_validation_map(
        pdf_path=args.pdf,
        out_dir=args.out,
        dpi=args.dpi,
        opacity=args.opacity,
        page_index=args.page,
    )
    print(f"wrote {html}")
    print("Open it in a browser. Use LayerControl (top-right) to toggle layers,")
    print("'PDF underlay' to fade the source map, and click polylines for length info.")


if __name__ == "__main__":
    main()

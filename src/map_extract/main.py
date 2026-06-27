"""End-to-end CLI: PDF -> red-line GeoJSON.

Run as a module from the repo root:

    python -m src.map_extract.main \
        --pdf data/reb-dhaka-pbs-2.pdf \
        --out data/pipeline/raw/pbs-2 \
        --dpi 300
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from .export import export_polylines, export_substations
from .extract import extract_red_polylines
from .georef import fit_georef
from .render import render_pdf, save_png

# Regions of the page that contain red but are NOT the 33 kV conductor lines.
# Defined in PDF-point space (72 pts = 1 inch) and scaled to the chosen DPI at
# runtime so they work at any render resolution.  Tailored to the REB PBS layout.
DEFAULT_EXCLUSIONS_PDF_PTS: tuple[tuple[float, float, float, float], ...] = (
    (2360.0, 0.0, 2880.0, 2160.0),       # right-side LEGEND column (with red swatches)
    (170.0, 1580.0, 850.0, 2160.0),      # bottom-left INDEX MAP inset
    (850.0, 1525.0, 2360.0, 2160.0),     # office / capacity tables
    (0.0, 0.0, 2880.0, 130.0),           # top title / 1:scale / km scale bar
)


def _scale_exclusions(boxes_pts, dpi: float, img_w: int, img_h: int):
    s = dpi / 72.0
    scaled = []
    for x0, y0, x1, y1 in boxes_pts:
        sx0 = max(0, int(round(x0 * s)))
        sy0 = max(0, int(round(y0 * s)))
        sx1 = min(img_w, int(round(x1 * s)))
        sy1 = min(img_h, int(round(y1 * s)))
        if sx1 > sx0 and sy1 > sy0:
            scaled.append((sx0, sy0, sx1, sy1))
    return tuple(scaled)


def _write_debug_overlays(image_bgr, extract_result, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if extract_result.debug.raw_mask is not None:
        cv2.imwrite(str(out_dir / "mask_raw.png"), extract_result.debug.raw_mask)
    if extract_result.debug.cleaned_mask is not None:
        cv2.imwrite(str(out_dir / "mask_lines_only.png"), extract_result.debug.cleaned_mask)
    if extract_result.debug.skeleton is not None:
        cv2.imwrite(str(out_dir / "skeleton.png"), extract_result.debug.skeleton)

    overlay = image_bgr.copy()
    for poly in extract_result.polylines_px:
        if len(poly) < 2:
            continue
        cv2.polylines(overlay, [poly.astype("int32")], isClosed=False, color=(0, 255, 0), thickness=3)
    for cx, cy in extract_result.substation_centroids_px:
        cv2.circle(overlay, (int(cx), int(cy)), 8, (255, 0, 255), 2)
    cv2.imwrite(str(out_dir / "overlay.png"), overlay)


def run(pdf_path: Path, out_dir: Path, dpi: int, page_index: int, keep_debug: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] rendering {pdf_path} @ {dpi} dpi ...")
    rendered = render_pdf(pdf_path, dpi=dpi, page_index=page_index)
    h, w = rendered.image_bgr.shape[:2]
    print(f"      image: {w}x{h}")
    if keep_debug:
        save_png(rendered.image_bgr, out_dir / "render.png")

    print("[2/4] fitting georef from graticule labels ...")
    georef = fit_georef(pdf_path, dpi=dpi, page_index=page_index)
    print(
        f"      lon = {georef.lon_fit.slope:.3e}*px + {georef.lon_fit.intercept:.5f}\n"
        f"      lat = {georef.lat_fit.slope:.3e}*py + {georef.lat_fit.intercept:.5f}\n"
        f"      GCPs: {len(georef.gcps)}"
    )

    print("[3/4] extracting red polylines ...")
    exclusions = _scale_exclusions(DEFAULT_EXCLUSIONS_PDF_PTS, dpi=dpi, img_w=w, img_h=h)
    extract_result = extract_red_polylines(
        rendered.image_bgr,
        exclude_regions=exclusions,
        keep_debug=keep_debug,
    )
    print(
        f"      polylines: {len(extract_result.polylines_px)}, "
        f"sub-station markers: {len(extract_result.substation_centroids_px)}"
    )
    if keep_debug:
        _write_debug_overlays(rendered.image_bgr, extract_result, out_dir / "debug")

    print("[4/4] exporting GeoJSON + CSV ...")
    export = export_polylines(extract_result.polylines_px, georef, out_dir)
    substations = export_substations(extract_result.substation_centroids_px, georef, out_dir)
    print(
        f"      total extracted length: {export.total_length_km:.2f} km\n"
        f"      lines:       {export.geojson_path}\n"
        f"      substations: {substations.geojson_path} ({len(substations.features)})"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=Path("data/reb-dhaka-pbs-2.pdf"))
    parser.add_argument("--out", type=Path, default=Path("data/pipeline/raw/pbs-2-lines"))
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--no-debug", action="store_true",
                        help="skip writing render / mask / overlay debug artifacts")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        pdf_path=args.pdf,
        out_dir=args.out,
        dpi=args.dpi,
        page_index=args.page,
        keep_debug=not args.no_debug,
    )


if __name__ == "__main__":
    main()

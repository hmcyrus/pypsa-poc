"""Georeference the rendered map.

We rely on the lat/lon graticule labels embedded as PDF text. PyMuPDF gives us
their PDF-point bounding boxes; we pair the broken "(DD)°(MM)'" and "(SS)\"(NSEW)"
spans, average the two opposite-side labels for each value (they're consistently
offset from the true tick), then fit two 1-D linear transforms (the map is axis
aligned, so longitude depends on px only and latitude on py only).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz
import numpy as np

_DM_PATTERN = re.compile(r"^(\d{1,3})°(\d{1,2})['′]$")
_SEC_PATTERN = re.compile(r"^(\d+)[\"″]([EWNS])$")


@dataclass
class GraticuleLabel:
    axis: str  # 'lon' or 'lat'
    value: float  # decimal degrees
    pdf_x_center: float
    pdf_y_center: float


@dataclass
class Affine1D:
    slope: float
    intercept: float

    def __call__(self, x: np.ndarray | float) -> np.ndarray | float:
        return self.slope * np.asarray(x) + self.intercept


@dataclass
class Georef:
    """Pixel-to-lon/lat transform for an axis-aligned map render."""

    lon_fit: Affine1D  # lon = lon_fit(px)
    lat_fit: Affine1D  # lat = lat_fit(py)
    px_per_pdf_pt: float
    gcps: list[GraticuleLabel]

    def pixels_to_lonlat(self, px: np.ndarray, py: np.ndarray) -> np.ndarray:
        px = np.asarray(px, dtype=float)
        py = np.asarray(py, dtype=float)
        return np.stack([self.lon_fit(px), self.lat_fit(py)], axis=-1)


def _iter_graticule_labels(page: fitz.Page) -> list[GraticuleLabel]:
    words = page.get_text("words")
    by_position = sorted(words, key=lambda w: (w[5], w[6], w[7]))
    labels: list[GraticuleLabel] = []
    for i in range(len(by_position) - 1):
        a, b = by_position[i], by_position[i + 1]
        # the two halves of a graticule label live in the same PDF block but on
        # adjacent lines (degree-minute above, second-NSEW below)
        if a[5] != b[5]:
            continue
        m1 = _DM_PATTERN.match(a[4])
        m2 = _SEC_PATTERN.match(b[4])
        if not (m1 and m2):
            continue
        deg = int(m1.group(1))
        minutes = int(m1.group(2))
        unit = m2.group(2)
        value = deg + minutes / 60.0
        axis = "lon" if unit in ("E", "W") else "lat"
        if unit in ("W", "S"):
            value = -value
        x0 = min(a[0], b[0])
        x1 = max(a[2], b[2])
        y0 = min(a[1], b[1])
        y1 = max(a[3], b[3])
        labels.append(
            GraticuleLabel(
                axis=axis,
                value=value,
                pdf_x_center=(x0 + x1) / 2.0,
                pdf_y_center=(y0 + y1) / 2.0,
            )
        )
    return labels


def _average_by_value(labels: list[GraticuleLabel], axis: str) -> list[tuple[float, float]]:
    bucket: dict[float, list[float]] = {}
    for lab in labels:
        if lab.axis != axis:
            continue
        key = round(lab.value, 6)
        pos = lab.pdf_x_center if axis == "lon" else lab.pdf_y_center
        bucket.setdefault(key, []).append(pos)
    return [(val, float(np.mean(positions))) for val, positions in sorted(bucket.items())]


def _fit_linear(pixel_positions: list[float], values: list[float]) -> Affine1D:
    px = np.asarray(pixel_positions, dtype=float)
    vals = np.asarray(values, dtype=float)
    if len(px) < 2:
        raise ValueError("need at least two distinct ticks to fit an axis")
    slope, intercept = np.polyfit(px, vals, 1)
    return Affine1D(slope=float(slope), intercept=float(intercept))


def fit_georef(pdf_path: str | Path, dpi: float, page_index: int = 0) -> Georef:
    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        labels = _iter_graticule_labels(page)
    if not labels:
        raise RuntimeError("no graticule labels found in PDF text layer")

    scale = dpi / 72.0
    lon_pairs = _average_by_value(labels, "lon")
    lat_pairs = _average_by_value(labels, "lat")
    if len(lon_pairs) < 2 or len(lat_pairs) < 2:
        raise RuntimeError(
            f"insufficient ticks: {len(lon_pairs)} lon, {len(lat_pairs)} lat"
        )

    lon_px = [pos * scale for _, pos in lon_pairs]
    lon_vals = [val for val, _ in lon_pairs]
    lat_py = [pos * scale for _, pos in lat_pairs]
    lat_vals = [val for val, _ in lat_pairs]

    return Georef(
        lon_fit=_fit_linear(lon_px, lon_vals),
        lat_fit=_fit_linear(lat_py, lat_vals),
        px_per_pdf_pt=scale,
        gcps=labels,
    )

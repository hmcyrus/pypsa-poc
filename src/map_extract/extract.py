"""Detect red 33 kV line geometry in a rendered map.

The pipeline:

1. HSV thresholding (two ranges for the red hue wrap-around).
2. Mask out non-map regions (legend / index map / tables / scale bar) so legend
   swatches and the inset map don't leak in.
3. Morphological close to bridge the small dot markers stamped along each line.
4. Drop components that are not line-like - mostly the small filled triangles
   used for 33/11 kV sub-stations and any glyph noise.  Their centroids are
   returned so the line tracer can snap segment ends to them.
5. Skeletonise to 1 px, cut the graph at junctions, walk each remaining simple
   chain to produce an ordered polyline.
6. Simplify each polyline with Ramer-Douglas-Peucker.

All masking decisions return the intermediate arrays so the caller can dump
them for debugging.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import cv2
import numpy as np

# HSV ranges tuned for the saturated REB-PBS map red.  Saturation floor is high
# to reject the dashed magenta/pink PBS boundary, which is visibly less
# saturated than the conductor red.
_RED_HSV_RANGES = (
    ((0, 120, 80), (10, 255, 255)),
    ((170, 120, 80), (180, 255, 255)),
)


@dataclass
class ExtractDebug:
    raw_mask: np.ndarray | None = None
    cleaned_mask: np.ndarray | None = None
    skeleton: np.ndarray | None = None
    dropped_centroids: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class ExtractResult:
    polylines_px: list[np.ndarray]
    substation_centroids_px: list[tuple[int, int]]
    debug: ExtractDebug


def _red_mask(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    masks = [cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
             for lo, hi in _RED_HSV_RANGES]
    return cv2.bitwise_or(*masks)


def _apply_exclusions(mask: np.ndarray, exclusions: Iterable[tuple[int, int, int, int]]) -> np.ndarray:
    if not exclusions:
        return mask
    out = mask.copy()
    for x0, y0, x1, y1 in exclusions:
        out[y0:y1, x0:x1] = 0
    return out


def _split_line_vs_shape_components(
    mask: np.ndarray,
    min_line_area: int,
    max_shape_area: int,
    shape_extent_thresh: float,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Separate thin-line components from filled-shape components.

    Returns (lines_mask, shape_centroids).
    """
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    lines_mask = np.zeros_like(mask)
    shape_centroids: list[tuple[int, int]] = []
    for lbl in range(1, num):
        x, y, w, h, area = stats[lbl]
        if area < 4:
            continue
        bbox_area = max(1, w * h)
        extent = area / bbox_area
        if area <= max_shape_area and extent >= shape_extent_thresh:
            cx, cy = centroids[lbl]
            shape_centroids.append((int(round(cx)), int(round(cy))))
            continue
        if area < min_line_area:
            continue
        lines_mask[labels == lbl] = 255
    return lines_mask, shape_centroids


_NEIGHBORS = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if not (dx == 0 and dy == 0)]


def _trace_skeleton(skel: np.ndarray, min_pixels: int) -> list[np.ndarray]:
    """Trace the skeleton by walking each pixel-to-pixel adjacency (edge)
    exactly once.  At a junction we continue in whichever direction is most
    aligned with the incoming step, so each output polyline follows a
    locally-straight path through T/Y intersections instead of stopping.
    """
    bin01 = (skel > 0).astype(np.uint8)
    H, W = bin01.shape

    # Per-pixel neighbor list (only foreground pixels matter).
    pixel_neighbors: dict[tuple[int, int], list[tuple[int, int]]] = {}
    ys, xs = np.where(bin01 > 0)
    for y, x in zip(ys.tolist(), xs.tolist()):
        nbrs = []
        for dx, dy in _NEIGHBORS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and bin01[ny, nx]:
                nbrs.append((nx, ny))
        pixel_neighbors[(x, y)] = nbrs

    used_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    def _edge_key(a: tuple[int, int], b: tuple[int, int]):
        return (a, b) if a <= b else (b, a)

    def _walk(start: tuple[int, int], first_step: tuple[int, int]) -> list[tuple[int, int]]:
        path = [start, first_step]
        used_edges.add(_edge_key(start, first_step))
        prev, cur = start, first_step
        while True:
            best: tuple[int, int] | None = None
            best_score = -1e9
            in_dx, in_dy = cur[0] - prev[0], cur[1] - prev[1]
            for nbr in pixel_neighbors[cur]:
                if nbr == prev:
                    continue
                if _edge_key(cur, nbr) in used_edges:
                    continue
                d_dx, d_dy = nbr[0] - cur[0], nbr[1] - cur[1]
                # dot product, preferring the most-aligned (straightest) branch
                score = in_dx * d_dx + in_dy * d_dy
                if score > best_score:
                    best_score = score
                    best = nbr
            if best is None:
                return path
            used_edges.add(_edge_key(cur, best))
            path.append(best)
            prev, cur = cur, best

    # Order start points: real endpoints (degree 1) first, then junctions
    # (degree 3+), then everything else.  Starting from endpoints yields the
    # cleanest polylines; junction starts cover any leftover branches.
    by_priority: list[tuple[int, tuple[int, int]]] = []
    for pt, nbrs in pixel_neighbors.items():
        deg = len(nbrs)
        if deg == 1:
            by_priority.append((0, pt))
        elif deg >= 3:
            by_priority.append((1, pt))
        else:
            by_priority.append((2, pt))
    by_priority.sort(key=lambda x: x[0])

    polylines: list[np.ndarray] = []
    for _, pt in by_priority:
        for nbr in pixel_neighbors[pt]:
            if _edge_key(pt, nbr) in used_edges:
                continue
            path = _walk(pt, nbr)
            if len(path) >= min_pixels:
                polylines.append(np.array(path, dtype=np.int32))
    return polylines


def extract_red_polylines(
    image_bgr: np.ndarray,
    exclude_regions: Iterable[tuple[int, int, int, int]] = (),
    *,
    morph_close_iter: int = 2,
    min_line_area: int = 200,
    max_shape_area: int = 4000,
    shape_extent_thresh: float = 0.45,
    min_skeleton_pixels: int = 8,
    rdp_epsilon_px: float = 1.5,
    keep_debug: bool = True,
) -> ExtractResult:
    raw = _red_mask(image_bgr)
    raw = _apply_exclusions(raw, exclude_regions)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, kernel, iterations=morph_close_iter)

    lines_mask, shape_centroids = _split_line_vs_shape_components(
        closed,
        min_line_area=min_line_area,
        max_shape_area=max_shape_area,
        shape_extent_thresh=shape_extent_thresh,
    )

    skel = cv2.ximgproc.thinning(lines_mask, thinningType=cv2.ximgproc.THINNING_ZHANGSUEN)
    raw_polylines = _trace_skeleton(skel, min_pixels=min_skeleton_pixels)

    simplified: list[np.ndarray] = []
    for poly in raw_polylines:
        approx = cv2.approxPolyDP(poly.reshape(-1, 1, 2), epsilon=rdp_epsilon_px, closed=False)
        simplified.append(approx.reshape(-1, 2))

    debug = ExtractDebug(
        raw_mask=raw if keep_debug else None,
        cleaned_mask=lines_mask if keep_debug else None,
        skeleton=skel if keep_debug else None,
        dropped_centroids=shape_centroids if keep_debug else [],
    )
    return ExtractResult(
        polylines_px=simplified,
        substation_centroids_px=shape_centroids,
        debug=debug,
    )

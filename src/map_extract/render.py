"""Render a PDF page to a high-resolution raster usable by OpenCV."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import fitz
import numpy as np


@dataclass
class RenderedPage:
    image_bgr: np.ndarray
    dpi: float
    pdf_width_pts: float
    pdf_height_pts: float

    @property
    def scale(self) -> float:
        return self.dpi / 72.0

    def pdf_to_px(self, x_pdf: float, y_pdf: float) -> tuple[float, float]:
        return x_pdf * self.scale, y_pdf * self.scale


def render_pdf(pdf_path: str | Path, dpi: int = 300, page_index: int = 0) -> RenderedPage:
    pdf_path = Path(pdf_path)
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        scale = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        buf = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        bgr = cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)
        return RenderedPage(
            image_bgr=bgr,
            dpi=float(dpi),
            pdf_width_pts=page.rect.width,
            pdf_height_pts=page.rect.height,
        )


def save_png(image_bgr: np.ndarray, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), image_bgr)
    return out_path

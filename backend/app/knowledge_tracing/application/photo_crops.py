"""Cuts one picture per question block out of a straightened page. Pure image arithmetic.

A block's position is stored as fractions of the marker frame, so the crop is found by
multiplying with the canonical size. Two rules came out of the grading experiment on real photos:

* The crop runs to the RIGHT EDGE of the frame. Children write past the end of the printed
  dotted line, and a crop that stops at the printed image width cuts their answer off.
* Padding is SMALL (8 pt above, 10 pt below). The photo and homography are never perfect, but a
  large margin pulls the neighbouring question into the crop. The 12 mm gap between blocks keeps
  a padded crop clear of its neighbours.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.knowledge_tracing.application.photo_alignment import CANONICAL_H, CANONICAL_W, PX_PER_MM

PT_TO_MM = 25.4 / 72
PAD_ABOVE_MM = 8 * PT_TO_MM
PAD_BELOW_MM = 10 * PT_TO_MM


@dataclass(frozen=True, slots=True)
class CropBox:
    """A rectangle in canonical pixels (x1 and y1 exclusive)."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def block_crop_box(
    block_x: float,
    block_y: float,
    block_w: float,
    block_h: float,
    *,
    pad_above_mm: float = PAD_ABOVE_MM,
    pad_below_mm: float = PAD_BELOW_MM,
) -> CropBox:
    """The crop rectangle of a stored block (fractions of the frame)."""
    x0 = round(block_x * CANONICAL_W)
    y0 = round(block_y * CANONICAL_H - pad_above_mm * PX_PER_MM)
    y1 = round((block_y + block_h) * CANONICAL_H + pad_below_mm * PX_PER_MM)
    return CropBox(
        x0=max(0, min(CANONICAL_W - 1, x0)),
        y0=max(0, y0),
        x1=CANONICAL_W,  # to the right edge of the frame
        y1=min(CANONICAL_H, y1),
    )


def crop(canonical: np.ndarray, box: CropBox) -> np.ndarray:
    return canonical[box.y0 : box.y1, box.x0 : box.x1].copy()


def encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("could not encode the image")
    return buffer.tobytes()


def encode_jpeg(image: np.ndarray, quality: int = 90) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("could not encode the image")
    return buffer.tobytes()


def draw_overlay(
    canonical: np.ndarray, boxes: list[tuple[int, CropBox]], colour: tuple[int, int, int] = (0, 140, 0)
) -> np.ndarray:
    """The straightened page with every crop outlined and numbered (for checking by eye)."""
    out = canonical.copy()
    for position, box in boxes:
        cv2.rectangle(out, (box.x0, box.y0), (box.x1 - 1, box.y1 - 1), colour, 3)
        cv2.putText(
            out, str(position), (box.x0 + 8, box.y0 + 34), cv2.FONT_HERSHEY_SIMPLEX, 1.1, colour, 3
        )
    return out

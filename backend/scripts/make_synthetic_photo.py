"""Makes a fake phone photo of a printed page, with a known geometry.

Used by the alignment tests and for tuning thresholds when no real photos exist yet. A rendered
PDF page is placed on a dark background with a random rotation and perspective, uneven lighting,
noise and blur, and fake pencil marks in the answer areas.

    python -m scripts.make_synthetic_photo paper.pdf --page 1 --out photo.jpg
    python -m scripts.make_synthetic_photo paper.pdf --page 1 --hide-markers --blur 4 --out blurry.jpg

The true mapping from the page (millimetres) to the photo (pixels) is returned by
`synthesize_photo`, so a test can measure how far the alignment is from the truth.
"""

import argparse
import math
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.knowledge_tracing.application.paper_layout import MARKER_CENTRE, PAGE_H, PAGE_W
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import render_pages


@dataclass(frozen=True, slots=True)
class SyntheticPhoto:
    image: np.ndarray  # BGR
    page_mm_to_photo: np.ndarray  # 3x3: page millimetres -> photo pixels (the truth)


def page_to_bgr(gray: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def synthesize_photo(
    page_gray: np.ndarray,
    px_per_mm: float,
    rng: random.Random,
    *,
    size: tuple[int, int] = (1800, 2400),  # photo width, height
    rotate_deg: float | None = None,
    perspective: float = 0.04,  # corner jitter as a fraction of the page size
    hide_markers: bool = False,
    blur_sigma: float = 0.8,
    noise_sigma: float = 4.0,
    marks: Sequence[tuple[float, float, float, float]] = (),  # (x, y, w, h) rectangles in mm
) -> SyntheticPhoto:
    page = page_to_bgr(page_gray)

    # pencil-like scribbles in the answer areas
    for x, y, w, h in marks:
        for _ in range(3):
            pts = [
                (int((x + w * rng.uniform(0.35, 0.95)) * px_per_mm),
                 int((y + h * rng.uniform(0.15, 0.85)) * px_per_mm))
                for _ in range(rng.randint(4, 7))
            ]
            cv2.polylines(page, [np.array(pts, np.int32)], False, (90, 90, 90), 3, cv2.LINE_AA)

    width, height = size
    background = np.full((height, width, 3), rng.choice([(55, 60, 70), (40, 55, 85), (70, 75, 80)]), np.uint8)
    background = cv2.add(background, np.random.default_rng(rng.randrange(2**31)).integers(
        0, 12, background.shape, dtype=np.uint8))

    # where the page lands: centred, rotated, perspective-jittered
    page_h_px, page_w_px = page.shape[:2]
    fill = rng.uniform(0.72, 0.88)
    scale = fill * min(width / page_w_px, height / page_h_px)
    theta = math.radians(rng.uniform(-14, 14) if rotate_deg is None else rotate_deg)
    # a rotated page needs more room: shrink it until the whole page stays inside the picture
    extent_w = abs(page_w_px * math.cos(theta)) + abs(page_h_px * math.sin(theta))
    extent_h = abs(page_w_px * math.sin(theta)) + abs(page_h_px * math.cos(theta))
    scale = min(scale, 0.94 * min(width / extent_w, height / extent_h))
    cx, cy = width / 2, height / 2
    corners = np.array(
        [[-page_w_px / 2, -page_h_px / 2], [page_w_px / 2, -page_h_px / 2],
         [page_w_px / 2, page_h_px / 2], [-page_w_px / 2, page_h_px / 2]], np.float32) * scale
    rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    destination = corners @ rotation.T + np.array([cx, cy])
    jitter = perspective * min(page_w_px, page_h_px) * scale
    destination = (destination + np.array(
        [[rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)] for _ in range(4)]
    )).astype(np.float32)

    source = np.array([[0, 0], [page_w_px, 0], [page_w_px, page_h_px], [0, page_h_px]], np.float32)
    homography_px = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(page, homography_px, (width, height), borderValue=(0, 0, 0))
    mask = cv2.warpPerspective(np.full(page.shape[:2], 255, np.uint8), homography_px, (width, height))
    photo = np.where(mask[..., None] > 127, warped, background)

    page_mm_to_photo = homography_px @ np.diag([px_per_mm, px_per_mm, 1.0])

    if hide_markers:  # a thumb, a shadow or a torn corner over every marker
        for x_mm, y_mm in (
            (MARKER_CENTRE, MARKER_CENTRE),
            (PAGE_W - MARKER_CENTRE, MARKER_CENTRE),
            (PAGE_W - MARKER_CENTRE, PAGE_H - MARKER_CENTRE),
            (MARKER_CENTRE, PAGE_H - MARKER_CENTRE),
        ):
            point = page_mm_to_photo @ np.array([x_mm, y_mm, 1.0])
            centre = (int(point[0] / point[2]), int(point[1] / point[2]))
            radius = int(11 * px_per_mm * scale)
            cv2.circle(photo, centre, radius, (215, 215, 215), -1, cv2.LINE_AA)

    # uneven light: a brightness ramp in a random direction
    angle = rng.uniform(0, 2 * math.pi)
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    ramp = (xs * math.cos(angle) + ys * math.sin(angle))
    ramp = (ramp - ramp.min()) / (ramp.max() - ramp.min() + 1e-6)
    shade = (rng.uniform(0.62, 0.85) + ramp * rng.uniform(0.1, 0.35))[..., None]
    photo = np.clip(photo.astype(np.float32) * shade, 0, 255)

    if noise_sigma > 0:
        photo += np.random.default_rng(rng.randrange(2**31)).normal(0, noise_sigma, photo.shape)
    photo = np.clip(photo, 0, 255).astype(np.uint8)
    if blur_sigma > 0:
        photo = cv2.GaussianBlur(photo, (0, 0), blur_sigma)
    return SyntheticPhoto(photo, page_mm_to_photo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--rotate", type=float, help="degrees; default random within +-14")
    parser.add_argument("--hide-markers", action="store_true")
    parser.add_argument("--blur", type=float, default=0.8, help="gaussian sigma in pixels")
    args = parser.parse_args()

    grays, px_per_mm = render_pages(args.pdf.read_bytes())
    photo = synthesize_photo(
        grays[args.page - 1], px_per_mm, random.Random(args.seed),
        rotate_deg=args.rotate, hide_markers=args.hide_markers, blur_sigma=args.blur,
    )
    cv2.imwrite(str(args.out), photo.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

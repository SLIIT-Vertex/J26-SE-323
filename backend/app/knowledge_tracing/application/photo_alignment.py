"""Straightens a phone photo of one printed paper page into a fixed, known layout.

Pure given image arrays: no database, no network, no vision model.

The canonical page
------------------
Every photo is warped to the same picture of the FRAME: the rectangle between the four marker
centres (184 x 271 mm, see paper_layout). It is CANONICAL_W x CANONICAL_H pixels, so the stored
block positions (fractions of the frame) map straight to pixels, whatever phone, angle or
distance the photo was taken at.

Two ways to get there
---------------------
A. Markers (primary): the four ArUco corner markers give four known points, hence a homography.
   The marker ids tell the corners apart, so a photo taken upside down or sideways still works.
B. Feature registration (fallback, for photos where a marker is hidden, torn or in shadow):
   SIFT features of the photo are matched against the stored PDF page and a homography is fitted
   with RANSAC. It also tells which page of the paper the photo shows.

Anything uncertain fails with a plain reason (never a guess): the parent is asked to retake the
photo.
"""

import io
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.knowledge_tracing.application.paper_layout import (
    CONTENT_X0,
    CONTENT_X1,
    CONTENT_Y0,
    CONTENT_Y1,
    FRAME_H,
    FRAME_W,
    FRAME_X0,
    FRAME_Y0,
    QR_SIZE,
    QR_X,
    QR_Y,
)
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import (
    ARUCO_DICTIONARY,
    MARKER_IDS,
    QR_PREFIX,
    decode_qr_texts,
)

CANONICAL_W = 1500  # about 207 dpi across the frame: enough for pencil handwriting
CANONICAL_H = round(CANONICAL_W * FRAME_H / FRAME_W)
PX_PER_MM = CANONICAL_W / FRAME_W

MAX_PHOTO_SIDE = 3000  # larger photos are scaled down on load
FEATURE_PHOTO_SIDE = 1600  # photos are made this size for feature matching (speed)
SIFT_FEATURES = 4000
RATIO_TEST = 0.78
RANSAC_PX = 6.0
MIN_INLIERS = 25  # in the experiment the right page had 199-274 and wrong pages under 20
BEST_TO_SECOND = 3.0
# Sharpness of the straightened page (see `blur_score`). On synthetic photos 1800 px wide a sharp
# one scores 3.5 to 6 and the score falls to about 1.4 as the blur grows; 2.0 sits where text
# becomes hard to read. This is a starting value: tune it on real phone photos.
BLUR_MIN = 2.0
BLUR_PROBE_SIGMA = 1.5
# The same score taken on the whole photo (shrunk to RAW_BLUR_SIDE px). The dark background
# makes it larger than the page score, so it has its own limit: on synthetic photos it was 16 to
# 22 for sharp ones, 7 at a blur of 1.8 px and 2.7 at 3.5 px. It is only used to say "blurry"
# instead of "low_match" when a photo is too blurred for markers and features to be found.
RAW_BLUR_MAX = 6.0
RAW_BLUR_SIDE = 1200

FailureReason = Literal[
    "unreadable_image", "markers_missing", "low_match", "blurry", "wrong_paper", "wrong_page"
]
Method = Literal["markers", "features"]

_QR_PATTERN = re.compile(rf"{QR_PREFIX}:([A-Z0-9]{{12}}):(\d+)")


class AlignmentFailure(Exception):
    """The photo cannot be used. `reason` is one of FailureReason; `detail` helps debugging."""

    def __init__(self, reason: FailureReason, detail: dict | None = None) -> None:
        super().__init__(reason)
        self.reason: FailureReason = reason
        self.detail = detail or {}


@dataclass(frozen=True, slots=True)
class Alignment:
    canonical: np.ndarray  # BGR, CANONICAL_H x CANONICAL_W
    method: Method
    page: int | None  # the page the photo shows, when it could be established
    blur_score: float
    homography: np.ndarray  # photo pixels (as loaded) -> canonical pixels
    detail: dict = field(default_factory=dict)


# A callable that renders the stored PDF pages: (gray page images, pixels per mm of those images).
PageRenders = Callable[[], tuple[Sequence[np.ndarray], float]]


def load_photo(data: bytes, max_side: int = MAX_PHOTO_SIDE) -> np.ndarray:
    """Decode an uploaded photo: apply the camera's rotation, make it BGR, limit its size."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise AlignmentFailure("unreadable_image") from error
    longest = max(image.size)
    if longest > max_side:
        scale = max_side / longest
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS
        )
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def blur_score(gray: np.ndarray) -> float:
    """How sharp a straightened page is: high for a sharp photo, close to 1 for a blurred one.

    It is the ratio between the fine detail (variance of the Laplacian) of the page and of the
    same page after a further small blur. Blurring a sharp page removes a lot of detail; blurring
    an already blurred page removes almost none. Unlike the raw Laplacian variance the ratio does
    not depend on how much print is on the page or how bright the light is, and a 3x3 median
    first keeps camera noise from passing a blurred photo as sharp.
    """
    smooth = cv2.medianBlur(gray, 3)
    detail = float(cv2.Laplacian(smooth, cv2.CV_64F).var())
    softer = cv2.GaussianBlur(smooth, (0, 0), BLUR_PROBE_SIGMA)
    remaining = float(cv2.Laplacian(softer, cv2.CV_64F).var())
    if remaining < 1e-6:
        return 0.0  # nothing on the page at all
    return detail / remaining


def photo_sharpness(gray: np.ndarray, side: int = RAW_BLUR_SIDE) -> float:
    """`blur_score` of the whole photo, shrunk to a standard size so photos are comparable."""
    shrink = side / max(gray.shape)
    if shrink < 1.0:
        gray = cv2.resize(gray, None, fx=shrink, fy=shrink, interpolation=cv2.INTER_AREA)
    return blur_score(gray)


# ---- method A: markers -----------------------------------------------------------------------


def _marker_detector() -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY), params)


def find_marker_centres(gray: np.ndarray) -> dict[int, np.ndarray]:
    """Centres of the page markers that were found, by marker id (0..3)."""
    detector = _marker_detector()
    for candidate in (gray, cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)):
        corners, ids, _ = detector.detectMarkers(candidate)
        if ids is None:
            continue
        found = {
            int(i): c.reshape(-1, 2).mean(axis=0)
            for i, c in zip(ids.flatten(), corners, strict=True)
            if int(i) in MARKER_IDS
        }
        if set(found) == set(MARKER_IDS):
            return found
    return {}


def _frame_corners() -> np.ndarray:
    """Where marker ids 0..3 (top-left, top-right, bottom-right, bottom-left) land."""
    return np.array(
        [[0, 0], [CANONICAL_W - 1, 0], [CANONICAL_W - 1, CANONICAL_H - 1], [0, CANONICAL_H - 1]],
        dtype=np.float32,
    )


def _homography_from_markers(centres: dict[int, np.ndarray]) -> np.ndarray:
    src = np.array([centres[i] for i in MARKER_IDS], dtype=np.float32)
    return cv2.getPerspectiveTransform(src, _frame_corners())


# ---- reading the QR ---------------------------------------------------------------------------


def parse_qr(text: str) -> tuple[str, int] | None:
    match = _QR_PATTERN.fullmatch(text.strip())
    return (match.group(1), int(match.group(2))) if match else None


def _read_qr(photo_gray: np.ndarray, canonical: np.ndarray) -> tuple[str, int] | None:
    """The paper code and page, read from the photo, or else from the straightened page."""
    for text in decode_qr_texts(photo_gray):
        parsed = parse_qr(text)
        if parsed:
            return parsed
    margin = 6.0  # mm around the printed QR
    x0 = int((QR_X - margin - FRAME_X0) * PX_PER_MM)
    x1 = int((QR_X + QR_SIZE + margin - FRAME_X0) * PX_PER_MM)
    y0 = int((QR_Y - margin - FRAME_Y0) * PX_PER_MM)
    y1 = int((QR_Y + QR_SIZE + margin - FRAME_Y0) * PX_PER_MM)
    region = cv2.cvtColor(canonical[max(0, y0) : y1, max(0, x0) : x1], cv2.COLOR_BGR2GRAY)
    if region.size == 0:
        return None
    for scale in (2.0, 1.0, 3.0):
        enlarged = cv2.resize(region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        for text in decode_qr_texts(enlarged):
            parsed = parse_qr(text)
            if parsed:
                return parsed
    return None


# ---- method B: feature registration -----------------------------------------------------------


def _content_mask(shape: tuple[int, int], px_per_mm: float, origin_mm: tuple[float, float]) -> np.ndarray:
    """255 inside the question area of a page picture, 0 over the header, markers and footer.

    The header, QR, corner markers and footer are the same on every page of a paper, so matching
    on them would make a photo of page 2 look a little like page 1. Only the questions tell the
    pages apart.
    """
    mask = np.zeros(shape, np.uint8)
    x0 = max(0, round((CONTENT_X0 - origin_mm[0]) * px_per_mm))
    x1 = max(0, round((CONTENT_X1 - origin_mm[0]) * px_per_mm))
    y0 = max(0, round((CONTENT_Y0 - origin_mm[1]) * px_per_mm))
    y1 = max(0, round((CONTENT_Y1 - origin_mm[1]) * px_per_mm))
    mask[y0:y1, x0:x1] = 255
    return mask


def _sift_features(gray: np.ndarray, mask: np.ndarray | None = None) -> tuple[list, np.ndarray | None]:
    sift = cv2.SIFT_create(nfeatures=SIFT_FEATURES)
    return sift.detectAndCompute(gray, mask)


def _register(
    photo_small_gray: np.ndarray,
    page_grays: Sequence[np.ndarray],
    page_masks: Sequence[np.ndarray | None] | None = None,
) -> list[tuple[int, np.ndarray | None]]:
    """For each page: (inlier count, homography photo -> page picture pixels)."""
    photo_kp, photo_desc = _sift_features(photo_small_gray)
    results: list[tuple[int, np.ndarray | None]] = []
    if photo_desc is None or len(photo_kp) < 8:
        return [(0, None) for _ in page_grays]
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    for index, page in enumerate(page_grays):
        mask = None if page_masks is None else page_masks[index]
        page_kp, page_desc = _sift_features(page, mask)
        if page_desc is None or len(page_kp) < 8:
            results.append((0, None))
            continue
        pairs = matcher.knnMatch(photo_desc, page_desc, k=2)
        good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < RATIO_TEST * n.distance]
        if len(good) < 8:
            results.append((0, None))
            continue
        src = np.float32([photo_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([page_kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, RANSAC_PX)
        inliers = 0 if mask is None else int(mask.sum())
        results.append((inliers, homography if homography is not None else None))
    return results


def _page_px_to_canonical(px_per_mm: float) -> np.ndarray:
    k = PX_PER_MM
    return np.array(
        [
            [k / px_per_mm, 0.0, -FRAME_X0 * k],
            [0.0, k / px_per_mm, -FRAME_Y0 * k],
            [0.0, 0.0, 1.0],
        ]
    )


def pdf_page_to_canonical(page_render: np.ndarray, px_per_mm: float) -> np.ndarray:
    """A stored PDF page (a render) as a canonical, BGR picture of the blank frame."""
    matrix = _page_px_to_canonical(px_per_mm)
    source = page_render if page_render.ndim == 3 else cv2.cvtColor(page_render, cv2.COLOR_GRAY2BGR)
    return cv2.warpPerspective(
        source, matrix, (CANONICAL_W, CANONICAL_H), flags=cv2.INTER_AREA, borderValue=(255, 255, 255)
    )


# ---- the whole alignment ----------------------------------------------------------------------


def align_photo(
    photo: np.ndarray,
    *,
    token: str,
    expected_page: int,
    page_count: int,
    page_renders: PageRenders | None = None,
    blur_min: float = BLUR_MIN,
) -> Alignment:
    """Straighten `photo` (BGR) into the canonical page, or raise AlignmentFailure.

    `token` and `page_count` describe the paper the photo was uploaded for; `expected_page` is
    the page the parent said it is. `page_renders` lets method B (and the page check when the QR
    is unreadable) compare the photo with the stored PDF; without it only markers are used.
    """
    if not 1 <= expected_page <= page_count:
        raise AlignmentFailure("wrong_page", {"expected_page": expected_page, "pages": page_count})
    if photo is None or photo.size == 0:
        raise AlignmentFailure("unreadable_image")

    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    centres = find_marker_centres(gray)

    try:
        if centres:
            alignment = _align_with_markers(photo, gray, centres, token, expected_page, page_renders)
        else:
            alignment = _align_with_features(photo, gray, expected_page, page_count, page_renders)
    except AlignmentFailure as failure:
        # A photo too blurred to find the markers or match features is best reported as blurry.
        if failure.reason in ("markers_missing", "low_match"):
            score = photo_sharpness(gray)
            if 0.0 < score < RAW_BLUR_MAX:
                raise AlignmentFailure(
                    "blurry",
                    {**failure.detail, "blur_score": score, "minimum": RAW_BLUR_MAX,
                     "found_instead": failure.reason},
                ) from failure
        raise

    if alignment.blur_score < blur_min:
        raise AlignmentFailure(
            "blurry", {"blur_score": alignment.blur_score, "minimum": blur_min, "method": alignment.method}
        )
    return alignment


def _align_with_markers(
    photo: np.ndarray,
    gray: np.ndarray,
    centres: dict[int, np.ndarray],
    token: str,
    expected_page: int,
    page_renders: PageRenders | None,
) -> Alignment:
    homography = _homography_from_markers(centres)
    canonical = cv2.warpPerspective(photo, homography, (CANONICAL_W, CANONICAL_H))
    detail: dict = {"markers": sorted(centres)}

    parsed = _read_qr(gray, canonical)
    page: int | None = None
    if parsed is not None:
        found_token, page = parsed
        if found_token != token:
            raise AlignmentFailure("wrong_paper", {"method": "markers"})
        if page != expected_page:
            raise AlignmentFailure("wrong_page", {"found_page": page, "expected_page": expected_page})
        detail["page_from"] = "qr"
    elif page_renders is not None:
        # The QR is unreadable: confirm the page by comparing with the stored PDF instead.
        page = _page_by_features(canonical, page_renders)
        if page is None:
            raise AlignmentFailure("low_match", {"qr": "unreadable"})
        if page != expected_page:
            raise AlignmentFailure("wrong_page", {"found_page": page, "expected_page": expected_page})
        detail["page_from"] = "features"
    else:
        raise AlignmentFailure("low_match", {"qr": "unreadable"})

    score = blur_score(cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY))
    return Alignment(canonical, "markers", page, score, homography, detail)


def _page_by_features(canonical: np.ndarray, page_renders: PageRenders) -> int | None:
    """Which stored page the straightened picture is (1-based), or None if no page matches."""
    grays, px_per_mm = page_renders()
    blank_pages = [
        cv2.cvtColor(pdf_page_to_canonical(g, px_per_mm), cv2.COLOR_BGR2GRAY) for g in grays
    ]
    masks = [
        _content_mask(g.shape, PX_PER_MM, (FRAME_X0, FRAME_Y0)) for g in blank_pages
    ]
    results = _register(cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY), blank_pages, masks)
    return _choose_page([inliers for inliers, _ in results])


def _choose_page(inliers: Sequence[int]) -> int | None:
    if not inliers:
        return None
    order = sorted(range(len(inliers)), key=lambda i: inliers[i], reverse=True)
    best = inliers[order[0]]
    if best < MIN_INLIERS:
        return None
    if len(order) > 1 and best < BEST_TO_SECOND * max(1, inliers[order[1]]):
        return None
    return order[0] + 1


def _align_with_features(
    photo: np.ndarray,
    gray: np.ndarray,
    expected_page: int,
    page_count: int,
    page_renders: PageRenders | None,
) -> Alignment:
    if page_renders is None:
        raise AlignmentFailure("markers_missing")
    grays, px_per_mm = page_renders()
    if len(grays) != page_count:
        raise AlignmentFailure("low_match", {"pages_rendered": len(grays), "pages": page_count})

    scale = min(1.0, FEATURE_PHOTO_SIDE / max(gray.shape))
    small = gray if scale == 1.0 else cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    masks = [_content_mask(g.shape, px_per_mm, (0.0, 0.0)) for g in grays]
    results = _register(small, grays, masks)
    inliers = [count for count, _ in results]
    page = _choose_page(inliers)
    if page is None:
        raise AlignmentFailure("low_match", {"inliers": inliers})
    if page != expected_page:
        raise AlignmentFailure("wrong_page", {"found_page": page, "expected_page": expected_page, "inliers": inliers})

    homography_small = results[page - 1][1]
    assert homography_small is not None
    shrink = np.diag([scale, scale, 1.0])  # photo pixels -> the small image the features came from
    photo_to_page = homography_small @ shrink
    photo_to_canonical = _page_px_to_canonical(px_per_mm) @ photo_to_page
    canonical = cv2.warpPerspective(photo, photo_to_canonical, (CANONICAL_W, CANONICAL_H))
    score = blur_score(cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY))
    return Alignment(
        canonical, "features", page, score, photo_to_canonical, {"inliers": inliers, "page_from": "features"}
    )

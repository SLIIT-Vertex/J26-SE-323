"""Alignment, page checks and question crops, on synthetic phone photos of generated papers.

The photos are fakes (see scripts/make_synthetic_photo.py): the real thresholds still have to be
tuned on photos taken with real phones. What is proven here is the geometry and the failure
reasons.
"""

import io
import itertools
import random
from functools import lru_cache

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.knowledge_tracing.application.paper_layout import (
    FRAME_H,
    FRAME_W,
    FRAME_X0,
    FRAME_Y0,
    LayoutQuestion,
    layout_paper,
)
from app.knowledge_tracing.application.photo_alignment import (
    BLUR_MIN,
    CANONICAL_H,
    CANONICAL_W,
    AlignmentFailure,
    align_photo,
    blur_score,
    load_photo,
    parse_qr,
)
from app.knowledge_tracing.application.photo_crops import (
    PAD_ABOVE_MM,
    PAD_BELOW_MM,
    block_crop_box,
    crop,
    draw_overlay,
    encode_png,
)
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import (
    build_paper_pdf,
    new_token,
    render_pages,
)
from scripts.make_synthetic_photo import synthesize_photo


def textured(seed: int, width: int = 945, height: int = 420) -> bytes:
    """A fake question picture with text-like detail, so feature matching has something to use."""
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 14), f"Question {seed}", fill="black")
    for row in range(5):
        y = 50 + row * 62
        x = 20
        while x < width - 90:
            w = rng.randint(30, 140)
            draw.rectangle([x, y, x + w, y + rng.randint(14, 24)], fill=(rng.randint(0, 70),) * 3)
            x += w + rng.randint(10, 28)
    for _ in range(6):
        cx, cy, r = rng.randint(60, width - 60), rng.randint(80, height - 40), rng.randint(14, 34)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline="black", width=3)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class Paper:
    def __init__(self, seed: int, questions: int = 9) -> None:
        qs = [LayoutQuestion(f"q{i}", 945, 420) for i in range(questions)]
        self.layout = layout_paper(qs, max_pages=4)
        self.token = new_token()
        images = {q.key: textured(seed * 100 + i) for i, q in enumerate(qs)}
        self.pdf = build_paper_pdf(self.token, self.layout.blocks, images, self.layout.page_count)
        self.grays, self.px_per_mm = render_pages(self.pdf)
        self.pages = self.layout.page_count

    def renders(self):
        return self.grays, self.px_per_mm

    def marks(self, page: int) -> list[tuple[float, float, float, float]]:
        return [
            (b.block_x, b.block_y, b.block_w, b.block_h)
            for b in self.layout.blocks
            if b.page == page
        ]

    def photo(self, page: int, seed: int, **options):
        return synthesize_photo(
            self.grays[page - 1],
            self.px_per_mm,
            random.Random(seed),
            size=(1800, 2400),
            marks=self.marks(page),
            **options,
        )

    def align(self, image: np.ndarray, page: int, **kwargs):
        return align_photo(
            image,
            token=self.token,
            expected_page=page,
            page_count=self.pages,
            page_renders=self.renders,
            **kwargs,
        )


@lru_cache(maxsize=2)
def paper(seed: int = 1) -> Paper:
    return Paper(seed)


def corner_error_mm(p: Paper, photo, alignment, page: int) -> float:
    """How far, in millimetres on the page, the estimate is from the truth at the block corners."""
    to_canonical = alignment.homography  # photo px -> canonical px
    back = np.linalg.inv(to_canonical)
    worst = 0.0
    for block in p.layout.blocks:
        if block.page != page:
            continue
        for x_mm, y_mm in (
            (block.block_x, block.block_y),
            (block.block_x + block.block_w, block.block_y + block.block_h),
        ):
            truth = photo.page_mm_to_photo @ np.array([x_mm, y_mm, 1.0])
            truth = truth[:2] / truth[2]
            # the canonical pixel of this point, from the block's frame position
            u = (x_mm - FRAME_X0) / FRAME_W * CANONICAL_W
            v = (y_mm - FRAME_Y0) / FRAME_H * CANONICAL_H
            estimate = back @ np.array([u, v, 1.0])
            estimate = estimate[:2] / estimate[2]
            pixels = float(np.linalg.norm(truth - estimate))
            # photo pixels per page millimetre near this point
            probe = photo.page_mm_to_photo @ np.array([x_mm + 1.0, y_mm, 1.0])
            probe = probe[:2] / probe[2]
            worst = max(worst, pixels / float(np.linalg.norm(probe - truth)))
    return worst


# ---- method A: markers -----------------------------------------------------------------------


def test_markers_align_most_photos_with_small_error() -> None:
    p = paper()
    rng = random.Random(21)
    total = ok = 0
    worst = 0.0
    for i in range(16):
        page = rng.randint(1, p.pages)
        photo = p.photo(page, seed=i)
        total += 1
        try:
            a = p.align(photo.image, page)
        except AlignmentFailure:
            continue
        ok += a.method == "markers" and a.page == page
        worst = max(worst, corner_error_mm(p, photo, a, page))

    assert ok / total >= 0.95
    assert worst < 1.5  # millimetres on the printed page


@pytest.mark.parametrize("angle", [90, 180, -90, 35])
def test_a_photo_taken_sideways_or_upside_down_still_aligns(angle: int) -> None:
    p = paper()
    photo = p.photo(1, seed=5, rotate_deg=angle, perspective=0.02)

    a = p.align(photo.image, 1)

    # At 35 degrees the page corners can leave the picture; the features then take over.
    assert a.method == ("markers" if angle % 90 == 0 else a.method)
    assert corner_error_mm(p, photo, a, 1) < (1.5 if a.method == "markers" else 3.0)


def test_the_straightened_page_has_the_fixed_size() -> None:
    p = paper()
    a = p.align(p.photo(1, seed=2).image, 1)

    assert a.canonical.shape == (CANONICAL_H, CANONICAL_W, 3)
    assert 0 < blur_score(cv2.cvtColor(a.canonical, cv2.COLOR_BGR2GRAY))


def test_the_qr_text_is_parsed() -> None:
    assert parse_qr("MB1:K7QX4M2PD9TB:2") == ("K7QX4M2PD9TB", 2)
    assert parse_qr("MB1:short:2") is None
    assert parse_qr("something else") is None


# ---- method B: features ----------------------------------------------------------------------


def test_features_align_photos_with_the_markers_hidden() -> None:
    p = paper()
    rng = random.Random(8)
    total = ok = 0
    worst = 0.0
    for i in range(8):
        page = rng.randint(1, p.pages)
        photo = p.photo(page, seed=100 + i, hide_markers=True)
        total += 1
        try:
            a = p.align(photo.image, page)
        except AlignmentFailure:
            continue
        ok += a.method == "features" and a.page == page
        worst = max(worst, corner_error_mm(p, photo, a, page))

    assert ok / total >= 0.9
    assert worst < 3.0  # feature registration is a little less exact than four markers


def test_without_the_pdf_renders_a_photo_with_no_markers_is_markers_missing() -> None:
    p = paper()
    photo = p.photo(1, seed=3, hide_markers=True)

    with pytest.raises(AlignmentFailure) as caught:
        align_photo(photo.image, token=p.token, expected_page=1, page_count=p.pages)

    assert caught.value.reason == "markers_missing"


# ---- failures: always a clear reason ---------------------------------------------------------


def test_a_photo_of_another_page_is_wrong_page() -> None:
    p = paper()
    photo = p.photo(2, seed=4)

    with pytest.raises(AlignmentFailure) as caught:
        p.align(photo.image, 1)  # the parent said page 1

    assert caught.value.reason == "wrong_page"
    assert caught.value.detail["found_page"] == 2


def test_a_wrong_page_is_also_found_when_markers_are_hidden() -> None:
    p = paper()
    photo = p.photo(2, seed=6, hide_markers=True)

    with pytest.raises(AlignmentFailure) as caught:
        p.align(photo.image, 1)

    assert caught.value.reason == "wrong_page"


def test_a_photo_of_another_paper_is_wrong_paper() -> None:
    mine, other = paper(1), paper(2)
    photo = other.photo(1, seed=7)

    with pytest.raises(AlignmentFailure) as caught:
        mine.align(photo.image, 1)

    assert caught.value.reason == "wrong_paper"


def test_another_paper_with_hidden_markers_does_not_match() -> None:
    mine, other = paper(1), paper(2)
    photo = other.photo(1, seed=9, hide_markers=True)

    with pytest.raises(AlignmentFailure) as caught:
        mine.align(photo.image, 1)

    assert caught.value.reason in {"low_match", "wrong_page"}
    assert caught.value.reason != "wrong_paper"  # without the QR it can only fail to match


def test_a_blurry_photo_is_rejected_as_blurry() -> None:
    p = paper()
    sharp = p.photo(1, seed=11, blur_sigma=0.8)
    blurry = p.photo(1, seed=11, blur_sigma=3.5)

    assert p.align(sharp.image, 1).blur_score >= BLUR_MIN
    with pytest.raises(AlignmentFailure) as caught:
        p.align(blurry.image, 1)
    assert caught.value.reason == "blurry"
    assert caught.value.detail["blur_score"] < BLUR_MIN


def test_the_blur_score_falls_as_the_photo_gets_blurrier() -> None:
    p = paper()
    scores = []
    for sigma in (0.5, 1.2, 2.5):
        photo = p.photo(1, seed=12, blur_sigma=sigma, noise_sigma=0)
        scores.append(p.align(photo.image, 1, blur_min=0.0).blur_score)

    assert scores[0] > scores[1] > scores[2]


def test_a_blank_photo_fails_without_a_guess() -> None:
    p = paper()
    nothing = np.full((1200, 900, 3), 120, np.uint8)

    with pytest.raises(AlignmentFailure) as caught:
        p.align(nothing, 1)

    assert caught.value.reason == "low_match"


def test_a_page_number_outside_the_paper_is_wrong_page() -> None:
    p = paper()

    with pytest.raises(AlignmentFailure) as caught:
        p.align(p.photo(1, seed=1).image, 7)

    assert caught.value.reason == "wrong_page"


def test_bytes_that_are_not_an_image_are_unreadable() -> None:
    with pytest.raises(AlignmentFailure) as caught:
        load_photo(b"this is not a photo")

    assert caught.value.reason == "unreadable_image"


def test_a_large_photo_is_scaled_down_on_load() -> None:
    big = np.zeros((4000, 3000, 3), np.uint8)
    ok, data = cv2.imencode(".jpg", big)
    assert ok

    loaded = load_photo(data.tobytes())

    assert max(loaded.shape[:2]) <= 3000


# ---- crops -----------------------------------------------------------------------------------


def test_a_crop_runs_to_the_right_edge_with_small_vertical_padding() -> None:
    p = paper()
    block = p.layout.blocks[0]
    x, y, w, h = block.frame_fractions()

    box = block_crop_box(x, y, w, h)

    assert box.x1 == CANONICAL_W  # to the right edge: answers are written past the dotted line
    assert box.x0 == round(x * CANONICAL_W)
    px_per_mm = CANONICAL_W / FRAME_W
    above = (y * CANONICAL_H) - box.y0
    below = box.y1 - ((y + h) * CANONICAL_H)
    assert above == pytest.approx(PAD_ABOVE_MM * px_per_mm, abs=1.5) or box.y0 == 0
    assert below == pytest.approx(PAD_BELOW_MM * px_per_mm, abs=1.5)


def test_crops_do_not_reach_into_the_next_question() -> None:
    p = paper()
    boxes = []
    for block in p.layout.blocks:
        if block.page == 1:
            boxes.append(block_crop_box(*block.frame_fractions()))
    assert len(boxes) >= 2

    for upper, lower in itertools.pairwise(boxes):
        assert upper.y1 <= lower.y0  # the 12 mm gap keeps padded crops apart


def test_a_crop_holds_the_answer_marks_and_the_blank_is_clean() -> None:
    p = paper()
    page = 1
    photo = p.photo(page, seed=14, blur_sigma=0.6)
    a = p.align(photo.image, page)
    block = next(b for b in p.layout.blocks if b.page == page)
    box = block_crop_box(*block.frame_fractions())

    cropped = crop(a.canonical, box)

    assert cropped.shape[0] == box.height and cropped.shape[1] == box.width
    assert cropped.shape[0] > 100 and cropped.shape[1] > 500
    # the blank page and the photographed page show the same printed area (high correlation)
    from app.knowledge_tracing.application.photo_alignment import pdf_page_to_canonical

    blank = crop(pdf_page_to_canonical(p.grays[page - 1], p.px_per_mm), box)
    a_gray = cv2.GaussianBlur(cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY), (0, 0), 2).astype(np.float32)
    b_gray = cv2.GaussianBlur(cv2.cvtColor(blank, cv2.COLOR_BGR2GRAY), (0, 0), 2).astype(np.float32)
    corr = np.corrcoef(a_gray.ravel(), b_gray.ravel())[0, 1]
    assert corr > 0.6  # same picture, different light and a few pencil marks


def test_the_overlay_outlines_every_question() -> None:
    p = paper()
    a = p.align(p.photo(1, seed=15).image, 1)
    boxes = [
        (b.position, block_crop_box(*b.frame_fractions())) for b in p.layout.blocks if b.page == 1
    ]

    overlay = draw_overlay(a.canonical, boxes)

    assert overlay.shape == a.canonical.shape
    assert not np.array_equal(overlay, a.canonical)
    assert encode_png(overlay).startswith(b"\x89PNG")


def test_a_crop_includes_a_line_drawn_below_the_options() -> None:
    """Found on a real paper: children underline their answer a few millimetres BELOW the printed
    options, outside the block. That line must be inside the crop, or the question reads blank."""
    p = paper()
    block = p.layout.blocks[0]
    x, y, w, h = block.frame_fractions()
    box = block_crop_box(x, y, w, h)
    px_per_mm = CANONICAL_W / FRAME_W
    block_bottom = (y + h) * CANONICAL_H

    for mm_below in (3.0, 6.0, 7.5):  # an underline drawn this far under the block
        assert box.y1 >= block_bottom + mm_below * px_per_mm
    assert PAD_BELOW_MM >= 7.5


def test_the_lower_padding_leaves_a_gap_before_the_next_crop() -> None:
    from app.knowledge_tracing.application.paper_layout import GAP

    assert PAD_BELOW_MM + PAD_ABOVE_MM < GAP  # the next question's crop starts after this one ends

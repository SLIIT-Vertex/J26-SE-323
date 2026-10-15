import io
import itertools
import re

import numpy as np
import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageDraw

from app.knowledge_tracing.application.paper_layout import (
    CONTENT_X0,
    CONTENT_X1,
    CONTENT_Y0,
    CONTENT_Y1,
    GAP,
    LayoutError,
    LayoutQuestion,
    block_height_mm,
    image_size_mm,
    layout_paper,
)
from app.knowledge_tracing.application.paper_selection import layout_height_mm
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import (
    PdfSelfCheckError,
    build_paper_pdf,
    new_token,
    qr_text,
    verify_paper_pdf,
)


def questions(n: int, width: int = 945, height: int = 300) -> list[LayoutQuestion]:
    return [LayoutQuestion(f"q{i}", width, height, value=float(i)) for i in range(n)]


def png(width: int, height: int, label: str = "Q") -> bytes:
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).rectangle([4, 4, width - 5, height - 5], outline="black", width=3)
    ImageDraw.Draw(image).text((20, 20), label, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# ---- image size -----------------------------------------------------------------------------


def test_natural_size_is_used_when_it_fits() -> None:
    # 600 px at 150 dpi = 101.6 mm; 300 px = 50.8 mm
    assert image_size_mm(600, 300) == (101.6, 50.8)


def test_wide_images_are_limited_to_160_mm_and_keep_their_shape() -> None:
    width, height = image_size_mm(2400, 600)

    assert width == pytest.approx(160.0, abs=0.01)
    assert height == pytest.approx(40.0, abs=0.01)


def test_tall_images_are_limited_to_90_mm_and_keep_their_shape() -> None:
    width, height = image_size_mm(600, 1500)

    assert height == pytest.approx(90.0, abs=0.01)
    assert width == pytest.approx(36.0, abs=0.01)


def test_the_selection_height_estimate_matches_the_layout() -> None:
    for width, height in ((945, 300), (2400, 600), (600, 1500), (300, 120)):
        estimate = layout_height_mm(width, height)  # includes the gap after the block
        assert estimate == pytest.approx(block_height_mm(width, height) + GAP, abs=0.05)


# ---- pagination -----------------------------------------------------------------------------


def test_blocks_stay_in_the_content_area_and_never_overlap() -> None:
    layout = layout_paper(questions(14), max_pages=6)

    by_page: dict[int, list] = {}
    for block in layout.blocks:
        by_page.setdefault(block.page, []).append(block)
        assert CONTENT_X0 <= block.image_x
        assert block.image_x + block.image_w <= CONTENT_X1 + 1e-6
        assert CONTENT_Y0 <= block.block_y
        assert block.block_y + block.block_h <= CONTENT_Y1 + 1e-6
    for blocks in by_page.values():
        for upper, lower in itertools.pairwise(blocks):
            assert lower.block_y - (upper.block_y + upper.block_h) == pytest.approx(GAP)


def test_numbers_run_across_pages_and_blocks_are_not_split() -> None:
    layout = layout_paper(questions(12), max_pages=6)

    assert [b.position for b in layout.blocks] == list(range(1, 13))
    assert layout.page_count >= 2
    assert [b.page for b in layout.blocks] == sorted(b.page for b in layout.blocks)
    assert not layout.dropped


def test_fractions_of_the_frame_are_between_zero_and_one() -> None:
    layout = layout_paper(questions(10), max_pages=6)

    for block in layout.blocks:
        x, y, w, h = block.frame_fractions()
        assert 0 <= x <= 1 and 0 <= y <= 1
        assert 0 < w <= 1 and 0 < h <= 1
        assert x + w <= 1 + 1e-9 and y + h <= 1 + 1e-9


def test_a_paper_too_long_for_its_pages_drops_the_lowest_value_questions() -> None:
    layout = layout_paper(questions(20), max_pages=1)

    assert layout.page_count == 1
    assert layout.dropped  # something was removed
    kept_values = {int(b.key[1:]) for b in layout.blocks}
    dropped_values = {int(k[1:]) for k in layout.dropped}
    assert max(dropped_values) < min(kept_values)  # the lowest values went first
    assert [b.position for b in layout.blocks] == list(range(1, len(layout.blocks) + 1))


def test_an_unusable_image_size_is_an_error() -> None:
    with pytest.raises(LayoutError):
        layout_paper([LayoutQuestion("bad", 0, 100)], max_pages=1)


def test_even_the_tallest_question_fits_on_a_page() -> None:
    layout = layout_paper([LayoutQuestion("tall", 10, 100000)], max_pages=1)

    assert layout.blocks[0].block_h <= CONTENT_Y1 - CONTENT_Y0


def test_an_empty_paper_is_an_error() -> None:
    with pytest.raises(LayoutError):
        layout_paper([], max_pages=1)


# ---- PDF ------------------------------------------------------------------------------------


def make_pdf(count: int = 6, max_pages: int = 3) -> tuple[bytes, str, int, list]:
    qs = [LayoutQuestion(f"q{i}", 945, 320) for i in range(count)]
    layout = layout_paper(qs, max_pages=max_pages)
    token = new_token()
    images = {q.key: png(945, 320, q.key) for q in qs}
    data = build_paper_pdf(token, layout.blocks, images, layout.page_count)
    return data, token, layout.page_count, list(layout.blocks)


def test_the_pdf_reads_back_markers_and_qr_on_every_page() -> None:
    data, token, pages, _ = make_pdf(10, max_pages=3)

    assert pages >= 2
    verify_paper_pdf(data, token, pages)  # raises if anything is missing


def test_the_pdf_has_a_title_with_the_code_and_no_personal_data() -> None:
    data, token, pages, _ = make_pdf(4)
    document = pdfium.PdfDocument(data)

    assert len(document) == pages
    assert document.get_metadata_value("Title") == f"MindBridge paper {token}"
    text = " ".join(document[i].get_textpage().get_text_range() for i in range(len(document)))
    assert token in text
    assert "Actual size" in text
    assert re.search(r"page 1 of \d", text)
    document.close()


def test_a_wrong_token_fails_the_self_check() -> None:
    data, _, pages, _ = make_pdf(4)

    with pytest.raises(PdfSelfCheckError):
        verify_paper_pdf(data, "AAAAAAAAAAAA", pages)


def test_a_page_without_markers_fails_the_self_check() -> None:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=(210 * mm, 297 * mm))
    page.drawString(50 * mm, 200 * mm, "no markers here")
    page.save()

    with pytest.raises(PdfSelfCheckError):
        verify_paper_pdf(buffer.getvalue(), "AAAAAAAAAAAA", 1)


def test_tokens_are_random_base32_and_the_qr_text_has_the_page() -> None:
    tokens = {new_token() for _ in range(200)}

    assert len(tokens) == 200
    assert all(re.fullmatch(r"[A-Z2-7]{12}", t) for t in tokens)
    assert qr_text("K7QX4M2PD9TB", 2) == "MB1:K7QX4M2PD9TB:2"


def test_large_images_are_downscaled_in_the_pdf() -> None:
    qs = [LayoutQuestion("big", 4000, 1200)]
    layout = layout_paper(qs, max_pages=1)
    noisy = np.random.default_rng(1).integers(0, 255, (1200, 4000, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(noisy).save(buffer, format="PNG")

    small = build_paper_pdf("AAAAAAAAAAAA", layout.blocks, {"big": buffer.getvalue()}, 1)

    assert len(small) < len(buffer.getvalue())  # 200 dpi at 160 mm is far fewer pixels

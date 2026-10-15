"""Turns one uploaded photo of a printed page into straightened question crops.

This is the deterministic first half of grading (no network, no vision model): find the page,
straighten it, check the photo is usable, and cut one crop per question block. The photo is not
stored or logged here.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.knowledge_tracing.application.photo_alignment import (
    Alignment,
    FailureReason,
    PageRenders,
    align_photo,
    load_photo,
    pdf_page_to_canonical,
)
from app.knowledge_tracing.application.photo_crops import CropBox, block_crop_box, crop
from app.knowledge_tracing.domain.paper import Paper, PaperItem

# What a parent is told for each reason. The app can translate these.
FAILURE_MESSAGES: dict[str, str] = {
    "unreadable_image": "We could not open this photo. Please take it again.",
    "markers_missing": (
        "We could not see all four black squares. Please retake the photo and keep every "
        "corner of the page in the picture."
    ),
    "low_match": (
        "We could not match this photo to the printed page. Please retake it flat, in good "
        "light, with the whole page in the picture."
    ),
    "blurry": "The photo is blurry. Hold the phone steady and retake it.",
    "wrong_paper": "This looks like a different paper. Please photograph this week's paper.",
    "wrong_page": "This looks like a different page of the paper. Please check the page number.",
}


@dataclass(frozen=True, slots=True)
class BlockCrop:
    position: int
    question_id: str
    box: CropBox
    image: np.ndarray  # BGR, as photographed
    blank: np.ndarray | None  # the same area from the stored PDF, for telling print from pencil


@dataclass(frozen=True, slots=True)
class PageCheck:
    alignment: Alignment
    crops: tuple[BlockCrop, ...]


def check_page_photo(
    photo_bytes: bytes,
    paper: Paper,
    page: int,
    items: Sequence[PaperItem],
    page_renders: PageRenders,
) -> PageCheck:
    """Straighten the photo of `page` of `paper` and cut its question blocks.

    Raises AlignmentFailure (with a reason from FAILURE_MESSAGES) if the photo cannot be used.
    """
    photo = load_photo(photo_bytes)
    alignment = align_photo(
        photo,
        token=paper.token,
        expected_page=page,
        page_count=paper.page_count,
        page_renders=page_renders,
    )

    blank_page: np.ndarray | None = None
    try:
        grays, px_per_mm = page_renders()
        blank_page = pdf_page_to_canonical(grays[page - 1], px_per_mm)
    except (IndexError, ValueError):  # a missing blank only loses the optional reference
        blank_page = None

    crops: list[BlockCrop] = []
    for item in sorted((i for i in items if i.page == page), key=lambda i: i.position):
        box = block_crop_box(item.block_x, item.block_y, item.block_w, item.block_h)
        crops.append(
            BlockCrop(
                position=item.position,
                question_id=item.question_id,
                box=box,
                image=crop(alignment.canonical, box),
                blank=None if blank_page is None else crop(blank_page, box),
            )
        )
    return PageCheck(alignment, tuple(crops))


def failure_message(reason: FailureReason | str) -> str:
    return FAILURE_MESSAGES.get(reason, "This photo could not be used. Please retake it.")

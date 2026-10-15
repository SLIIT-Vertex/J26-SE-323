"""Places the chosen questions on A4 pages. Pure: numbers in, numbers out.

All lengths are millimetres with the origin at the top-left of the page.

Page geometry
-------------
* ArUco corner markers (12 mm) are centred 13 mm from every page edge.
* The FRAME is the rectangle between the four marker centres: x 13..197, y 13..284
  (184 x 271 mm). Every stored position is a fraction of this frame, so a printer that scales the
  page slightly does not matter: the photo is straightened to the same frame.
* Questions go in the content area x 20..190, y 40..272 (232 mm high).

A question block is the printed image plus 3 mm of clear padding on every side, with the
question number to its left. Blocks are never split across pages, and 12 mm of clear space
separates one block from the next.
"""

from collections.abc import Sequence
from dataclasses import dataclass

PAGE_W, PAGE_H = 210.0, 297.0
MARKER_SIZE = 12.0
MARKER_CENTRE = 13.0  # from each page edge
FRAME_X0, FRAME_Y0 = MARKER_CENTRE, MARKER_CENTRE
FRAME_W = PAGE_W - 2 * MARKER_CENTRE  # 184
FRAME_H = PAGE_H - 2 * MARKER_CENTRE  # 271
CONTENT_X0, CONTENT_X1 = 20.0, 190.0
CONTENT_Y0, CONTENT_Y1 = 40.0, 272.0
NUMBER_X = 20.0  # the printed question number
IMAGE_X = 30.0
PADDING = 3.0
GAP = 12.0
MAX_IMAGE_W = 160.0
MAX_IMAGE_H = 90.0
DEFAULT_DPI = 150.0
QR_X, QR_Y, QR_SIZE = 165.0, 14.0, 20.0


@dataclass(frozen=True, slots=True)
class LayoutQuestion:
    """What the layout needs to know about one question."""

    key: str  # the caller's identifier, handed back unchanged
    width_px: int
    height_px: int
    value: float = 0.0  # used only to decide which question to drop if the paper is too long


@dataclass(frozen=True, slots=True)
class PlacedBlock:
    key: str
    position: int  # printed number, 1-based across all pages
    page: int  # 1-based
    # image rectangle (mm)
    image_x: float
    image_y: float
    image_w: float
    image_h: float
    # whole block, padding included (mm)
    block_x: float
    block_y: float
    block_w: float
    block_h: float

    def frame_fractions(self) -> tuple[float, float, float, float]:
        """The block as (x, y, w, h), each a fraction 0..1 of the marker frame."""
        return (
            round((self.block_x - FRAME_X0) / FRAME_W, 6),
            round((self.block_y - FRAME_Y0) / FRAME_H, 6),
            round(self.block_w / FRAME_W, 6),
            round(self.block_h / FRAME_H, 6),
        )


@dataclass(frozen=True, slots=True)
class PaperLayout:
    blocks: tuple[PlacedBlock, ...]
    page_count: int
    dropped: tuple[str, ...]  # keys removed because the paper would not fit the page limit


class LayoutError(Exception):
    pass


def image_size_mm(width_px: int, height_px: int, dpi: float = DEFAULT_DPI) -> tuple[float, float]:
    """Printed size of a question image: natural size, at most 160 x 90 mm, aspect kept."""
    if width_px <= 0 or height_px <= 0:
        raise LayoutError("image size must be positive")
    width = width_px * 25.4 / dpi
    height = height_px * 25.4 / dpi
    scale = min(1.0, MAX_IMAGE_W / width, MAX_IMAGE_H / height)
    return round(width * scale, 3), round(height * scale, 3)


def block_height_mm(width_px: int, height_px: int, dpi: float = DEFAULT_DPI) -> float:
    return image_size_mm(width_px, height_px, dpi)[1] + 2 * PADDING


def _paginate(questions: Sequence[LayoutQuestion], dpi: float) -> list[PlacedBlock]:
    blocks: list[PlacedBlock] = []
    page, y = 1, CONTENT_Y0
    for number, question in enumerate(questions, start=1):
        image_w, image_h = image_size_mm(question.width_px, question.height_px, dpi)
        height = image_h + 2 * PADDING
        if y > CONTENT_Y0 and y + height > CONTENT_Y1:  # start a new page
            page += 1
            y = CONTENT_Y0
        if height > CONTENT_Y1 - CONTENT_Y0:
            raise LayoutError(f"{question.key}: a single question is taller than a page")
        blocks.append(
            PlacedBlock(
                key=question.key,
                position=number,
                page=page,
                image_x=IMAGE_X,
                image_y=y + PADDING,
                image_w=image_w,
                image_h=image_h,
                block_x=IMAGE_X - PADDING,
                block_y=y,
                block_w=image_w + 2 * PADDING,
                block_h=height,
            )
        )
        y += height + GAP
    return blocks


def layout_paper(
    questions: Sequence[LayoutQuestion], max_pages: int = 3, dpi: float = DEFAULT_DPI
) -> PaperLayout:
    """Place the questions in the order given. Too long for `max_pages`: drop the lowest-value
    question and try again, recording what was dropped."""
    kept = list(questions)
    dropped: list[str] = []
    while kept:
        blocks = _paginate(kept, dpi)
        pages = blocks[-1].page
        if pages <= max_pages:
            return PaperLayout(tuple(blocks), pages, tuple(dropped))
        # lowest value goes first; the later question loses a tie
        victim = min(range(len(kept)), key=lambda i: (kept[i].value, -i))
        dropped.append(kept.pop(victim).key)
    raise LayoutError("no question fits on the paper")

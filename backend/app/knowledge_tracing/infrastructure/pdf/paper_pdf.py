"""Draws a weekly paper as a PDF and checks the result by reading it back.

Each page carries four ArUco corner markers (ids 0..3 clockwise from the top-left) and a QR code
`MB1:<token>:<page>`. They let the grading step straighten a phone photo of the printed page and
know which paper and page it is. The token is random and says nothing about the child.

Text drawn here is Latin characters and digits only: ReportLab does not shape Sinhala or Tamil,
which appear only inside the question images.
"""

import io
import secrets
from collections.abc import Mapping, Sequence

import cv2
import numpy as np
import pypdfium2 as pdfium
import qrcode
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.knowledge_tracing.application.paper_layout import (
    MARKER_CENTRE,
    MARKER_SIZE,
    NUMBER_X,
    PAGE_H,
    PAGE_W,
    QR_SIZE,
    QR_X,
    QR_Y,
    PlacedBlock,
)

ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
# top-left, top-right, bottom-right, bottom-left
MARKER_IDS = (0, 1, 2, 3)
QUIET_ZONE = 2.0  # mm of white around each marker
TOKEN_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
TOKEN_LENGTH = 12
QR_PREFIX = "MB1"
MAX_IMAGE_DPI = 200  # question images are scaled down to this when printed
CHECK_DPI = 150


class PdfSelfCheckError(Exception):
    """The rendered PDF cannot be read back: do not print or store it."""


def new_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def qr_text(token: str, page: int) -> str:
    return f"{QR_PREFIX}:{token}:{page}"


def _marker_image(marker_id: int) -> Image.Image:
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    pixels = cv2.aruco.generateImageMarker(dictionary, marker_id, 400)
    return Image.fromarray(pixels).convert("L")


def _qr_image(text: str) -> Image.Image:
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=2)
    code.add_data(text)
    code.make(fit=True)
    return code.make_image(fill_color="black", back_color="white").get_image().convert("L")


def _prepare_image(data: bytes, width_mm: float) -> Image.Image:
    """RGB, and no more than MAX_IMAGE_DPI at the printed width (keeps the PDF small)."""
    with Image.open(io.BytesIO(data)) as source:
        if source.mode in ("RGBA", "LA", "P"):
            rgba = source.convert("RGBA")
            image = Image.new("RGB", rgba.size, (255, 255, 255))
            image.paste(rgba, mask=rgba.split()[-1])
        else:
            image = source.convert("RGB")
    limit = max(1, round(width_mm / 25.4 * MAX_IMAGE_DPI))
    if image.width > limit:
        height = max(1, round(image.height * limit / image.width))
        image = image.resize((limit, height), Image.Resampling.LANCZOS)
    return image


def _y(top_mm: float) -> float:
    """ReportLab measures from the bottom; the layout measures from the top."""
    return (PAGE_H - top_mm) * mm


def build_paper_pdf(
    token: str,
    blocks: Sequence[PlacedBlock],
    images: Mapping[str, bytes],
    page_count: int,
    title: str = "practice paper",
) -> bytes:
    """Draw the blocks (image bytes by block key) on `page_count` A4 pages."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(PAGE_W * mm, PAGE_H * mm))
    pdf.setTitle(f"MindBridge paper {token}")
    pdf.setAuthor("MindBridge")
    pdf.setSubject("Weekly practice paper")

    markers = {marker_id: ImageReader(_marker_image(marker_id)) for marker_id in MARKER_IDS}
    corners = {
        0: (MARKER_CENTRE, MARKER_CENTRE),
        1: (PAGE_W - MARKER_CENTRE, MARKER_CENTRE),
        2: (PAGE_W - MARKER_CENTRE, PAGE_H - MARKER_CENTRE),
        3: (MARKER_CENTRE, PAGE_H - MARKER_CENTRE),
    }

    for page in range(1, page_count + 1):
        # white quiet zone, then the marker itself
        for marker_id, (cx, cy) in corners.items():
            half = MARKER_SIZE / 2 + QUIET_ZONE
            pdf.setFillColorRGB(1, 1, 1)
            pdf.rect((cx - half) * mm, _y(cy + half), 2 * half * mm, 2 * half * mm, stroke=0, fill=1)
            pdf.drawImage(
                markers[marker_id],
                (cx - MARKER_SIZE / 2) * mm,
                _y(cy + MARKER_SIZE / 2),
                MARKER_SIZE * mm,
                MARKER_SIZE * mm,
            )

        pdf.drawImage(
            ImageReader(_qr_image(qr_text(token, page))),
            QR_X * mm,
            _y(QR_Y + QR_SIZE),
            QR_SIZE * mm,
            QR_SIZE * mm,
        )
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(20 * mm, _y(22), f"MindBridge {title} - code {token} - page {page} of {page_count}")
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(
            PAGE_W / 2 * mm, _y(281), "Print at Actual size (100%). Do not use Fit to page."
        )

        for block in blocks:
            if block.page != page:
                continue
            image = _prepare_image(images[block.key], block.image_w)
            pdf.drawImage(
                ImageReader(image),
                block.image_x * mm,
                _y(block.image_y + block.image_h),
                block.image_w * mm,
                block.image_h * mm,
            )
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(NUMBER_X * mm, _y(block.image_y + 5), f"{block.position}.")
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _render(pdf: bytes, dpi: int = CHECK_DPI) -> list[np.ndarray]:
    document = pdfium.PdfDocument(pdf)
    try:
        return [
            np.array(document[index].render(scale=dpi / 72).to_pil().convert("L"))
            for index in range(len(document))
        ]
    finally:
        document.close()


def verify_paper_pdf(pdf: bytes, token: str, page_count: int) -> None:
    """Render every page and find the four markers and the QR code again.

    Raises PdfSelfCheckError if anything is missing, in the wrong corner or reads differently.
    """
    pages = _render(pdf)
    if len(pages) != page_count:
        raise PdfSelfCheckError(f"expected {page_count} pages, the PDF has {len(pages)}")

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY), cv2.aruco.DetectorParameters()
    )
    qr_reader = cv2.QRCodeDetector()
    for number, gray in enumerate(pages, start=1):
        corners, ids, _ = detector.detectMarkers(gray)
        found = {} if ids is None else {int(i): c.reshape(-1, 2).mean(axis=0) for i, c in zip(ids.flatten(), corners, strict=True)}
        if set(found) != set(MARKER_IDS):
            raise PdfSelfCheckError(f"page {number}: markers found {sorted(found)}, need 0-3")
        height, width = gray.shape
        expected = {
            0: (width * 0.25, height * 0.25),
            1: (width * 0.75, height * 0.25),
            2: (width * 0.75, height * 0.75),
            3: (width * 0.25, height * 0.75),
        }
        for marker_id, (cx, cy) in expected.items():
            x, y = found[marker_id]
            if (x < width / 2) != (cx < width / 2) or (y < height / 2) != (cy < height / 2):
                raise PdfSelfCheckError(f"page {number}: marker {marker_id} is in the wrong corner")

        text, _, _ = qr_reader.detectAndDecode(gray)
        if text != qr_text(token, number):
            raise PdfSelfCheckError(f"page {number}: QR reads {text!r}, expected {qr_text(token, number)!r}")

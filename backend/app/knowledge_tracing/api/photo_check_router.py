"""A dry-run endpoint for photographed pages: straighten, check and crop, but store nothing.

It lets real phone photos be tried against a real paper (from Swagger at /docs or a small page)
to tune the thresholds, before the grading pipeline and its upload endpoint exist. The photo is
read from the request and discarded; nothing is written to storage or the database.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.knowledge_tracing.api.papers_router import get_paper_storage
from app.knowledge_tracing.application.photo_alignment import AlignmentFailure
from app.knowledge_tracing.application.photo_check import (
    check_page_photo,
    failure_message,
)
from app.knowledge_tracing.application.photo_crops import draw_overlay, encode_png
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import render_pages
from app.knowledge_tracing.infrastructure.storage import StorageBackend, StorageKeyNotFound
from app.shared.database.session import get_db

router = APIRouter(tags=["photo-check"])

MAX_PHOTO_BYTES = 15 * 1024 * 1024


class BlockRead(BaseModel):
    position: int
    question_id: str
    width_px: int
    height_px: int


class PhotoCheckRead(BaseModel):
    ok: bool
    page: int
    failure_reason: str | None = None
    message: str | None = None
    method: str | None = None  # markers | features
    blur_score: float | None = None
    blur_minimum: float | None = None
    detail: dict | None = None
    blocks: list[BlockRead] = []


@router.post("/papers/{paper_id}/pages/{page}/photo-check", response_model=PhotoCheckRead)
async def check_photo(
    paper_id: UUID,
    page: int,
    session: Annotated[Session, Depends(get_db)],
    paper_storage: Annotated[StorageBackend, Depends(get_paper_storage)],
    image: Annotated[UploadFile, File(description="A photo of the printed page")],
    output: Annotated[
        Literal["json", "overlay", "crop", "page"], Query(description="what to return")
    ] = "json",
    position: Annotated[int | None, Query(description="question number, for output=crop")] = None,
) -> Response | PhotoCheckRead:
    """Check a photo of one page of a paper. `output=json` describes the result;
    `overlay` returns the straightened page with every question outlined, `page` the straightened
    page itself, and `crop` the picture of one question (give `position`)."""
    repository = SqlAlchemyPaperRepository(session)
    paper = repository.get(paper_id)
    if paper is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
    if not 1 <= page <= paper.page_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This paper has no such page")

    data = await image.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The photo is too large")

    try:
        pdf = paper_storage.get(paper.pdf_key)
    except StorageKeyNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The paper file is missing") from error

    def renders():  # rendered only if the photo needs it
        return render_pages(pdf)

    try:
        result = check_page_photo(data, paper, page, repository.items(paper_id), renders)
    except AlignmentFailure as failure:
        message = failure_message(failure.reason)
        if output != "json":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                {"code": failure.reason, "message": message},
            ) from failure
        return PhotoCheckRead(
            ok=False,
            page=page,
            failure_reason=failure.reason,
            message=message,
            blur_score=failure.detail.get("blur_score"),
            blur_minimum=failure.detail.get("minimum"),
            detail=failure.detail or None,
        )

    if output == "overlay":
        boxes = [(c.position, c.box) for c in result.crops]
        return Response(encode_png(draw_overlay(result.alignment.canonical, boxes)), media_type="image/png")
    if output == "page":
        return Response(encode_png(result.alignment.canonical), media_type="image/png")
    if output == "crop":
        chosen = next((c for c in result.crops if c.position == position), None)
        if chosen is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question on this page")
        return Response(encode_png(chosen.image), media_type="image/png")

    return PhotoCheckRead(
        ok=True,
        page=page,
        method=result.alignment.method,
        blur_score=round(result.alignment.blur_score, 2),
        detail=result.alignment.detail,
        blocks=[
            BlockRead(
                position=c.position,
                question_id=c.question_id,
                width_px=c.box.width,
                height_px=c.box.height,
            )
            for c in result.crops
        ],
    )

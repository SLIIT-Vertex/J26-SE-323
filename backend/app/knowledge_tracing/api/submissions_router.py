"""Photo upload, background marking, parent review and confirmation.

The app's flow for one page: POST the photo, poll GET /submissions/{id} until the status is no
longer uploaded or grading, show the unclear answers (picture and what was read, never the key),
POST the parent's decisions. The marking runs in the background, so the upload returns at once.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.knowledge_tracing.api.papers_router import get_paper_storage
from app.knowledge_tracing.application.grading import GradingConfig
from app.knowledge_tracing.application.grading.types import ReviewPolicy, VisionProvider
from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_generation import PaperNotFoundError
from app.knowledge_tracing.application.photo_check import failure_message
from app.knowledge_tracing.application.submissions import (
    MAX_PHOTO_BYTES,
    BadDecisionError,
    Decision,
    IncompleteDecisionsError,
    PageAlreadyGradedError,
    PageInProgressError,
    PageNotFoundError,
    PaperCancelledError,
    PhotosExpiredError,
    PhotoTooLargeError,
    SubmissionNotFoundError,
    SubmissionService,
    SubmissionView,
    UnavailableProvider,
    UnreadablePhotoError,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.domain.submission import IN_PROGRESS_STATUSES
from app.knowledge_tracing.infrastructure.db.answer_key_repository import (
    SqlAlchemyAnswerKeyRepository,
)
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)
from app.knowledge_tracing.infrastructure.storage import StorageBackend, StorageKeyNotFound
from app.knowledge_tracing.infrastructure.vision.factory import (
    VisionNotConfigured,
    get_second_vision_provider,
    get_vision_provider,
)
from app.shared.database.session import SessionLocal, get_db

router = APIRouter(tags=["submissions"])


# ---- schemas ----------------------------------------------------------------------------------


class UploadAccepted(BaseModel):
    submission_id: UUID
    status: str


class ReviewItemRead(BaseModel):
    paper_item_id: UUID
    position: int
    part_no: int
    part_type: Literal["mcq", "short"]
    crop_url: str  # the whole question as photographed
    reading: dict  # {"selected": "3"} or {"text": "..."}: what the machine read, never the key
    reason: str | None
    options: list[str] | None = None
    ask: str | None = None  # an instruction part: answer yes or no


class PartResultRead(BaseModel):
    part_no: int
    result: str | None


class ItemResultRead(BaseModel):
    paper_item_id: UUID
    position: int
    question_id: str
    result: Literal["correct", "wrong", "blank", "pending_review"]
    parts: list[PartResultRead] | None = None


class SummaryRead(BaseModel):
    items: int
    auto_final: int
    needs_review: int


class SubmissionRead(BaseModel):
    submission_id: UUID
    paper_id: UUID
    page: int
    status: str
    in_progress: bool  # keep polling while true
    failure_reason: str | None = None
    message: str | None = None  # what to tell the parent when the photo cannot be used
    uploaded_at: datetime
    summary: SummaryRead
    review_items: list[ReviewItemRead]
    results: list[ItemResultRead]


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_item_id: UUID
    part_no: int = Field(default=1, ge=1, le=20)
    selected: str | None = Field(default=None, max_length=40)  # a choice part; null = no answer
    text: str | None = Field(default=None, max_length=500)  # a short part; "" = no answer
    instruction_met: bool | None = None  # an instruction part: yes or no


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[DecisionIn] = Field(max_length=200)


# ---- wiring -----------------------------------------------------------------------------------


def _review_policy() -> ReviewPolicy:
    if get_settings().grading_review_policy.strip().lower() == "strict":
        return ReviewPolicy.strict()
    return ReviewPolicy.reader_unsure()


def make_submission_service(
    session: Session,
    paper_storage: StorageBackend,
    *,
    provider: VisionProvider | None = None,
    second_provider: VisionProvider | None = None,
    estimator: object | None = None,
    use_default_readers: bool = True,
) -> SubmissionService:
    settings = get_settings()
    spec = get_feature_spec()

    if provider is None and use_default_readers:
        try:
            provider = get_vision_provider()
            second_provider = second_provider or get_second_vision_provider()
        except VisionNotConfigured as error:
            provider = UnavailableProvider(str(error))
    if provider is None:
        provider = UnavailableProvider("no reader is configured")

    mastery: MasteryService | None = None
    if estimator is None:
        try:
            from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model

            estimator = get_knowledge_model()
        except Exception:  # noqa: BLE001  (without the model marking still works)
            estimator = None
    if estimator is not None:
        mastery = MasteryService(SqlAlchemyMasteryRepository(session), estimator, spec)  # type: ignore[arg-type]

    return SubmissionService(
        SqlAlchemySubmissionRepository(session),
        SqlAlchemyPaperRepository(session),
        SqlAlchemyAnswerKeyRepository(session),
        paper_storage,
        provider,
        spec,
        second_provider=second_provider,
        mastery=mastery,
        config=GradingConfig(
            confidence_min=settings.vision_confidence_min, review_policy=_review_policy()
        ),
        workers=settings.vision_concurrency,
    )


GradingLauncher = Callable[[UUID], None]


def get_grading_launcher(
    paper_storage: Annotated[StorageBackend, Depends(get_paper_storage)],
) -> GradingLauncher:
    """Marks a stored photo in its own database session (the request's one is closed by then)."""

    def launch(submission_id: UUID) -> None:
        with SessionLocal() as session:
            make_submission_service(session, paper_storage).grade(submission_id)

    return launch


def get_submission_service(
    session: Annotated[Session, Depends(get_db)],
    paper_storage: Annotated[StorageBackend, Depends(get_paper_storage)],
) -> SubmissionService:
    return make_submission_service(session, paper_storage)


ServiceDep = Annotated[SubmissionService, Depends(get_submission_service)]


# ---- conversion -------------------------------------------------------------------------------


def _read(view: SubmissionView, prefix: str) -> SubmissionRead:
    submission = view.submission
    base = f"{prefix}/submissions/{submission.id}"
    message = (
        failure_message(submission.failure_reason)
        if submission.status == "failed_alignment" and submission.failure_reason
        else None
    )
    return SubmissionRead(
        submission_id=submission.id,
        paper_id=submission.paper_id,
        page=submission.page,
        status=submission.status,
        in_progress=submission.status in IN_PROGRESS_STATUSES,
        failure_reason=submission.failure_reason,
        message=message,
        uploaded_at=submission.uploaded_at,
        summary=SummaryRead(
            items=view.summary.items,
            auto_final=view.summary.auto_final,
            needs_review=view.summary.needs_review,
        ),
        review_items=[
            ReviewItemRead(
                paper_item_id=r.paper_item_id,
                position=r.position,
                part_no=r.part_no,
                part_type=r.part_type,  # type: ignore[arg-type]
                crop_url=f"{base}/crops/{r.paper_item_id}",
                reading=r.reading,
                reason=r.reason,
                options=list(r.options) if r.options else None,
                ask=r.ask,
            )
            for r in view.review_items
        ],
        results=[
            ItemResultRead(
                paper_item_id=i.paper_item_id,
                position=i.position,
                question_id=i.question_id,
                result=i.result,  # type: ignore[arg-type]
                parts=None
                if i.parts is None
                else [PartResultRead(part_no=p.part_no, result=p.result) for p in i.parts],
            )
            for i in view.results
        ],
    )


def _error(code: int, name: str, message: str, **extra: object) -> HTTPException:
    return HTTPException(code, {"code": name, "message": message, **extra})


# ---- endpoints --------------------------------------------------------------------------------


@router.post(
    "/papers/{paper_id}/pages/{page}/photo",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_page_photo(
    paper_id: UUID,
    page: int,
    background: BackgroundTasks,
    service: ServiceDep,
    launcher: Annotated[GradingLauncher, Depends(get_grading_launcher)],
    image: Annotated[UploadFile, File(description="A photo of the printed page")],
) -> UploadAccepted:
    """Store the photo and start marking it. Poll GET /submissions/{id} for the outcome."""
    data = await image.read(MAX_PHOTO_BYTES + 1)
    try:
        submission = service.accept_photo(paper_id, page, data)
    except (PaperNotFoundError, PageNotFoundError) as error:
        raise _error(404, "not_found", "No such paper or page") from error
    except PaperCancelledError as error:
        raise _error(409, "paper_cancelled", "This paper was cancelled") from error
    except PhotoTooLargeError as error:
        raise _error(413, "photo_too_large", "The photo is too large") from error
    except UnreadablePhotoError as error:
        raise _error(
            422, "unreadable_image", "We could not open this photo. Please take it again."
        ) from error
    except PageAlreadyGradedError as error:
        raise _error(409, "page_already_graded", "This page has already been marked") from error
    except PageInProgressError as error:
        raise _error(
            409, "page_in_progress", "Some answers on this page already count. Finish the unclear ones."
        ) from error
    background.add_task(launcher, submission.id)
    return UploadAccepted(submission_id=submission.id, status=submission.status)


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission(submission_id: UUID, service: ServiceDep) -> SubmissionRead:
    try:
        return _read(service.view(submission_id), get_settings().api_v1_prefix)
    except SubmissionNotFoundError as error:
        raise _error(404, "not_found", "Submission not found") from error


@router.get("/submissions/{submission_id}/crops/{paper_item_id}")
def get_crop(submission_id: UUID, paper_item_id: UUID, service: ServiceDep) -> Response:
    """The picture of one question as photographed (for the review screen)."""
    try:
        data = service.crop(submission_id, paper_item_id)
    except PhotosExpiredError as error:
        raise _error(410, "photos_removed", "This picture is no longer kept") from error
    except (SubmissionNotFoundError, StorageKeyNotFound) as error:
        raise _error(404, "not_found", "No such picture") from error
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.post("/submissions/{submission_id}/confirm", response_model=SubmissionRead)
def confirm_submission(
    submission_id: UUID,
    body: ConfirmIn,
    service: ServiceDep,
    parent_id: Annotated[str | None, Header(alias="X-Parent-Id", max_length=64)] = None,
) -> SubmissionRead:
    """The parent says what the child wrote or marked for each unclear answer.

    The server marks that reading with the same rules; the parent never types correct or wrong.
    """
    decisions = [
        Decision(d.paper_item_id, d.part_no, d.selected, d.text, d.instruction_met)
        for d in body.decisions
    ]
    try:
        view = service.confirm(submission_id, decisions, parent_id or "parent")
    except SubmissionNotFoundError as error:
        raise _error(404, "not_found", "Submission not found") from error
    except PhotosExpiredError as error:
        raise _error(
            410, "photos_removed", "The photos of this page are no longer kept, so it cannot be decided"
        ) from error
    except IncompleteDecisionsError as error:
        raise _error(
            422,
            "decisions_missing",
            "Every unclear answer needs a decision",
            missing=[{"position": p, "part_no": n} for p, n in error.missing],
        ) from error
    except BadDecisionError as error:
        raise _error(
            422,
            "bad_decision",
            str(error),
            paper_item_id=str(error.paper_item_id) if error.paper_item_id else None,
            part_no=error.part_no,
        ) from error
    return _read(view, get_settings().api_v1_prefix)

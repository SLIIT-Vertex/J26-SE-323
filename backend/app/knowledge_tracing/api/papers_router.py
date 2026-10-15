from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.knowledge_tracing.api.mastery_router import get_estimator
from app.knowledge_tracing.application.mastery_service import (
    LearnerNotFoundError,
    MasteryService,
)
from app.knowledge_tracing.application.paper_generation import (
    Availability,
    GeneratedPaper,
    NotEligibleYetError,
    PaperGenerationError,
    PaperNotFoundError,
    PaperRequest,
    PaperService,
    next_paper_date,
)
from app.knowledge_tracing.application.paper_planning import PaperPlanner
from app.knowledge_tracing.application.paper_selection import NotEnoughQuestions
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.domain.paper import Paper
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
    SqlAlchemyPaperInputRepository,
)
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import PdfSelfCheckError
from app.knowledge_tracing.infrastructure.storage import (
    StorageBackend,
    StorageKeyNotFound,
    create_paper_storage,
    create_storage,
)
from app.shared.database.session import get_db

router = APIRouter(tags=["papers"])


class PaperCreate(BaseModel):
    """All fields are optional; the defaults are the weekly paper."""

    model_config = ConfigDict(extra="forbid")

    max_questions: int = Field(default=15, ge=1, le=40)
    max_minutes: int = Field(default=25, ge=1, le=120)
    max_pages: int = Field(default=3, ge=1, le=6)
    mode: Literal["auto", "practice", "diagnostic"] = "auto"
    focus_skills: list[str] = Field(default_factory=list, max_length=10)
    language: Literal["si", "ta"] | None = None


class PaperItemRead(BaseModel):
    position: int
    page: int
    question_id: str
    skill_code: str
    difficulty: str
    role: str


class AvailabilityRead(BaseModel):
    """The state of the get-this-week-paper button."""

    # not_yet_eligible: joined too recently, button unavailable
    # available:        button clickable (one paper per week)
    # generated:        this week's paper exists; show it, button unavailable until next Saturday
    state: Literal["not_yet_eligible", "available", "generated"]
    can_generate: bool
    joined_at: datetime
    eligible_from: datetime  # the moment the first paper can be asked for
    days_until_eligible: int  # 0 once eligible
    week_start: date  # the Saturday the current week began
    next_paper_date: date  # the Saturday the next paper can be asked for
    paper: "PaperRead | None" = None


class PagePhotoRead(BaseModel):
    """Where one printed page stands: not photographed yet, being marked, or done."""

    page: int
    submission_id: UUID | None = None
    submission_status: str | None = None  # null until a photo of this page was uploaded


class PaperRead(BaseModel):
    paper_id: UUID
    code: str
    status: str
    mode: str
    language: str
    week_start: date  # the Saturday this paper belongs to
    next_paper_date: date  # the Saturday the following paper appears
    page_count: int
    question_count: int
    estimated_minutes: float
    pdf_url: str
    created_at: datetime | None
    skipped_skills: list[str]
    items: list[PaperItemRead] | None = None
    pages: list[PagePhotoRead] | None = None  # only on the detail view


@lru_cache
def get_question_storage() -> StorageBackend:
    return create_storage(get_settings())


@lru_cache
def get_paper_storage() -> StorageBackend:
    return create_paper_storage(get_settings())


def make_paper_service(
    session: Session,
    estimator: KnowledgeModel,
    question_storage: StorageBackend,
    paper_storage: StorageBackend,
) -> PaperService:
    """Wire the paper service. Used by the API and by the Saturday batch script."""
    spec = get_feature_spec()
    mastery = MasteryService(SqlAlchemyMasteryRepository(session), estimator, spec)
    planner = PaperPlanner(SqlAlchemyPaperInputRepository(session), mastery, estimator, spec)
    return PaperService(
        SqlAlchemyPaperRepository(session),
        planner,
        question_storage,
        paper_storage,
        min_days_after_joining=get_settings().paper_min_days_after_joining,
    )


def get_paper_service(
    session: Annotated[Session, Depends(get_db)],
    estimator: Annotated[KnowledgeModel, Depends(get_estimator)],
    question_storage: Annotated[StorageBackend, Depends(get_question_storage)],
    paper_storage: Annotated[StorageBackend, Depends(get_paper_storage)],
) -> PaperService:
    return make_paper_service(session, estimator, question_storage, paper_storage)


def _read(paper: Paper, skipped: list[str], items: list | None = None) -> PaperRead:
    prefix = get_settings().api_v1_prefix
    return PaperRead(
        paper_id=paper.id,
        code=paper.token,
        status=paper.status,
        mode=paper.mode,
        language=paper.language,
        week_start=paper.week_start,
        next_paper_date=next_paper_date(paper.week_start),
        page_count=paper.page_count,
        question_count=paper.question_count,
        estimated_minutes=paper.estimated_minutes,
        pdf_url=f"{prefix}/papers/{paper.id}/pdf",
        created_at=paper.created_at,
        skipped_skills=skipped,
        items=None
        if items is None
        else [
            PaperItemRead(
                position=i.position,
                page=i.page,
                question_id=i.question_id,
                skill_code=i.skill_code,
                difficulty=i.shown_difficulty,
                role=i.role,
            )
            for i in items
        ],
    )


def _skipped(paper: Paper) -> list[str]:
    return list(paper.params.get("skipped_skills", []))


def _from_generated(result: GeneratedPaper, with_items: bool = False) -> PaperRead:
    return _read(result.paper, _skipped(result.paper), result.items if with_items else None)


ServiceDep = Annotated[PaperService, Depends(get_paper_service)]


@router.post(
    "/learners/{learner_id}/papers",
    response_model=PaperRead,
    status_code=status.HTTP_201_CREATED,
)
def create_weekly_paper(
    learner_id: UUID,
    response: Response,
    service: ServiceDep,
    body: PaperCreate | None = None,
) -> PaperRead:
    """This week's paper. Called again in the same week it returns the same paper (200)."""
    body = body or PaperCreate()
    request = PaperRequest(
        max_questions=body.max_questions,
        max_minutes=body.max_minutes,
        max_pages=body.max_pages,
        mode=body.mode,
        focus_skills=tuple(body.focus_skills),
        language=body.language,
    )
    try:
        result = service.generate_weekly(learner_id, request)
    except LearnerNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found") from error
    except NotEligibleYetError as error:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "not_eligible_yet",
                "message": "The weekly paper is available after the first week in the app",
                "eligible_from": error.eligible_from.isoformat(),
            },
        ) from error
    except NotEnoughQuestions as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not enough questions for a paper") from error
    except (PaperGenerationError, PdfSelfCheckError) as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "The paper could not be produced"
        ) from error
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _from_generated(result, with_items=True)


def _availability(result: Availability) -> AvailabilityRead:
    return AvailabilityRead(
        state=result.state,
        can_generate=result.can_generate,
        joined_at=result.joined_at,
        eligible_from=result.eligible_from,
        days_until_eligible=result.days_until_eligible,
        week_start=result.week_start,
        next_paper_date=result.next_paper_date,
        paper=None if result.paper is None else _from_generated(result.paper, with_items=True),
    )


@router.get("/learners/{learner_id}/papers/availability", response_model=AvailabilityRead)
def paper_availability(learner_id: UUID, service: ServiceDep) -> AvailabilityRead:
    """Everything the app needs to draw the weekly-paper button for this child."""
    try:
        return _availability(service.availability(learner_id))
    except LearnerNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found") from error


@router.get("/learners/{learner_id}/papers/current", response_model=PaperRead)
def current_paper(learner_id: UUID, service: ServiceDep) -> PaperRead:
    """This week's paper (Saturday to Friday). 404 if it has not been made yet."""
    result = service.current(learner_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This week's paper has not been made yet")
    return _from_generated(result, with_items=True)


@router.get("/learners/{learner_id}/papers", response_model=list[PaperRead])
def list_papers(
    learner_id: UUID,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PaperRead]:
    return [_read(p, _skipped(p)) for p in service.list(learner_id, limit)]


@router.get("/papers/{paper_id}", response_model=PaperRead)
def get_paper(
    paper_id: UUID, service: ServiceDep, session: Annotated[Session, Depends(get_db)]
) -> PaperRead:
    try:
        result = _from_generated(service.get(paper_id), with_items=True)
        from app.knowledge_tracing.infrastructure.db.submission_repository import (
            SqlAlchemySubmissionRepository,
        )

        current = {
            s.page: s for s in SqlAlchemySubmissionRepository(session).current_for_paper(paper_id)
        }
        result.pages = [
            PagePhotoRead(
                page=page,
                submission_id=current[page].id if page in current else None,
                submission_status=current[page].status if page in current else None,
            )
            for page in range(1, result.page_count + 1)
        ]
        return result
    except PaperNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found") from error


@router.get("/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: UUID, service: ServiceDep) -> Response:
    try:
        paper, data = service.pdf(paper_id)
    except PaperNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found") from error
    except StorageKeyNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The paper file is missing") from error
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="mindbridge-paper-{paper.token}.pdf"'},
    )


@router.post("/papers/{paper_id}/cancel", response_model=PaperRead)
def cancel_paper(paper_id: UUID, service: ServiceDep) -> PaperRead:
    """Cancel a paper so the week can get a new one."""
    try:
        paper = service.cancel(paper_id)
    except PaperNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found") from error
    return _read(paper, _skipped(paper))

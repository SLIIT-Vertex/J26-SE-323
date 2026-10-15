"""Makes this week's paper for a learner: choose, lay out, draw, check, store.

One live paper per learner per week. Asking again in the same week returns the same paper, so
a retry, a double tap or a second device never prints two different papers.
"""

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.knowledge_tracing.application.paper_layout import (
    LayoutError,
    LayoutQuestion,
    PaperLayout,
    layout_paper,
)
from app.knowledge_tracing.application.paper_planning import PaperPlanner, PlanDetails
from app.knowledge_tracing.application.paper_selection import PaperParams
from app.knowledge_tracing.domain.paper import Paper, PaperItem
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import (
    build_paper_pdf,
    new_token,
    verify_paper_pdf,
)
from app.knowledge_tracing.infrastructure.storage.base import StorageBackend

logger = logging.getLogger("mindbridge.papers")

# Papers belong to a week in Sri Lanka time, whatever time zone the server runs in.
LOCAL_TIME = timezone(timedelta(hours=5, minutes=30))
MAX_TOKEN_TRIES = 5


class PaperNotFoundError(Exception):
    pass


class PaperGenerationError(Exception):
    """The paper could not be produced (for example an image is missing)."""


@dataclass(frozen=True, slots=True)
class VariantImage:
    image_key: str
    width_px: int
    height_px: int


@dataclass(frozen=True, slots=True)
class PaperRequest:
    max_questions: int = 15
    max_minutes: int = 25
    max_pages: int = 3
    mode: str = "auto"
    focus_skills: tuple[str, ...] = ()
    language: str | None = None
    seed: int | None = None


@dataclass(slots=True)
class GeneratedPaper:
    paper: Paper
    created: bool
    items: list[PaperItem] = field(default_factory=list)


class PaperRepository(Protocol):
    def find_for_week(self, learner_id: UUID, week_start: date) -> Paper | None: ...

    def token_exists(self, token: str) -> bool: ...

    def variants(self, question_ids: list[str], language: str) -> dict[str, VariantImage]: ...

    def add(self, paper: Paper, items: list[PaperItem]) -> tuple[Paper, bool]: ...

    def get(self, paper_id: UUID) -> Paper | None: ...

    def list_for_learner(self, learner_id: UUID, limit: int) -> list[Paper]: ...

    def items(self, paper_id: UUID) -> list[PaperItem]: ...

    def set_status(self, paper_id: UUID, status: str) -> Paper | None: ...


def week_start_for(moment: datetime) -> date:
    """The Monday of the week that `moment` falls in, in Sri Lanka time."""
    local = moment.astimezone(LOCAL_TIME).date()
    return local - timedelta(days=local.weekday())


class PaperService:
    def __init__(
        self,
        repository: PaperRepository,
        planner: PaperPlanner,
        question_storage: StorageBackend,
        paper_storage: StorageBackend,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.planner = planner
        self.question_storage = question_storage
        self.paper_storage = paper_storage
        self.now = now

    # ---- generate ------------------------------------------------------------------------

    def generate_weekly(self, learner_id: UUID, request: PaperRequest = PaperRequest()) -> GeneratedPaper:  # noqa: B008
        """This week's paper: the existing one, or a new one made now."""
        week = week_start_for(self.now())
        existing = self.repository.find_for_week(learner_id, week)
        if existing is not None:
            return GeneratedPaper(existing, False, self.repository.items(existing.id))

        seed = request.seed if request.seed is not None else random.SystemRandom().randrange(2**31)
        params = PaperParams(
            max_questions=request.max_questions,
            max_minutes=request.max_minutes,
            max_pages=request.max_pages,
            seed=seed,
            mode=request.mode,  # type: ignore[arg-type]
            focus_skills=request.focus_skills,
        )
        plan = self.planner.plan_detailed(learner_id, params, request.language)
        return self._make(learner_id, week, params, plan)

    def _make(
        self, learner_id: UUID, week: date, params: PaperParams, plan: PlanDetails
    ) -> GeneratedPaper:
        selection = plan.selection
        variants = self.repository.variants([q.question_id for q in selection.questions], plan.language)
        missing = [q.question_id for q in selection.questions if q.question_id not in variants]
        if missing:
            raise PaperGenerationError(f"no {plan.language} image for questions {missing}")

        # Selection already orders by area and difficulty; keep that order on the page.
        ordered = [
            LayoutQuestion(q.question_id, variants[q.question_id].width_px,
                           variants[q.question_id].height_px, q.value)
            for q in selection.questions
        ]
        try:
            layout: PaperLayout = layout_paper(ordered, max_pages=params.max_pages)
        except LayoutError as error:
            raise PaperGenerationError(str(error)) from error

        by_id = {q.question_id: q for q in selection.questions}
        images = {}
        for block in layout.blocks:
            try:
                images[block.key] = self.question_storage.get(variants[block.key].image_key)
            except Exception as error:  # a missing or unreadable image must not become a paper
                raise PaperGenerationError(f"cannot read the image of question {block.key}") from error

        token = self._unique_token()
        paper_id = uuid4()
        title = "Weekly diagnostic paper" if selection.mode == "diagnostic" else "Weekly practice paper"
        pdf = build_paper_pdf(token, layout.blocks, images, layout.page_count, title)
        verify_paper_pdf(pdf, token, layout.page_count)  # never store an unreadable paper

        kept = [by_id[b.key] for b in layout.blocks]
        paper = Paper(
            id=paper_id,
            learner_id=learner_id,
            token=token,
            week_start=week,
            status="generated",
            mode=selection.mode,
            language=plan.language,
            params={
                "requested": {
                    "max_questions": params.max_questions,
                    "max_minutes": params.max_minutes,
                    "max_pages": params.max_pages,
                    "mode": params.mode,
                    "focus_skills": list(params.focus_skills),
                    "seed": params.seed,
                },
                "selection_method": selection.method,
                "question_count": len(kept),
                "estimated_minutes": round(sum(q.est_seconds for q in kept) / 60, 1),
                "weak_skills": list(selection.weak_skills),
                "verify_skills": list(selection.verify_skills),
                "diagnostic_skills": list(selection.diagnostic_skills),
                "skipped_skills": list(selection.skipped_skills),
                "dropped_questions": list(layout.dropped),
                "notes": list(selection.notes),
            },
            mastery_snapshot_id=plan.snapshot.id,
            model_version=plan.snapshot.model_version,
            page_count=layout.page_count,
            pdf_key=f"papers/{paper_id}.pdf",
        )
        items = []
        for block in layout.blocks:
            chosen = by_id[block.key]
            x, y, w, h = block.frame_fractions()
            items.append(
                PaperItem(
                    id=uuid4(),
                    paper_id=paper_id,
                    position=block.position,
                    question_id=block.key,
                    skill_code=chosen.skill_code,
                    language=plan.language,
                    page=block.page,
                    block_x=x,
                    block_y=y,
                    block_w=w,
                    block_h=h,
                    shown_difficulty=chosen.difficulty,
                    role=chosen.role,
                    predicted_p=chosen.predicted_p,
                )
            )

        self.paper_storage.put(paper.pdf_key, pdf, "application/pdf")
        try:
            stored, created = self.repository.add(paper, items)
        except Exception:
            self._discard_file(paper.pdf_key)
            raise
        if not created:  # another request won the week while this one was drawing
            self._discard_file(paper.pdf_key)
            return GeneratedPaper(stored, False, self.repository.items(stored.id))
        return GeneratedPaper(stored, True, self.repository.items(stored.id))

    def _unique_token(self) -> str:
        for _ in range(MAX_TOKEN_TRIES):
            token = new_token()
            if not self.repository.token_exists(token):
                return token
        raise PaperGenerationError("could not create a unique paper code")

    def _discard_file(self, key: str) -> None:
        try:
            self.paper_storage.delete(key)
        except Exception:  # noqa: BLE001  (best-effort cleanup must never hide the real error)
            logger.warning("could not remove the unused paper file %s", key)

    # ---- read ----------------------------------------------------------------------------

    def get(self, paper_id: UUID) -> GeneratedPaper:
        paper = self.repository.get(paper_id)
        if paper is None:
            raise PaperNotFoundError(paper_id)
        return GeneratedPaper(paper, False, self.repository.items(paper_id))

    def list(self, learner_id: UUID, limit: int = 20) -> list[Paper]:
        return self.repository.list_for_learner(learner_id, limit)

    def pdf(self, paper_id: UUID) -> tuple[Paper, bytes]:
        paper = self.repository.get(paper_id)
        if paper is None:
            raise PaperNotFoundError(paper_id)
        return paper, self.paper_storage.get(paper.pdf_key)

    def cancel(self, paper_id: UUID) -> Paper:
        paper = self.repository.set_status(paper_id, "cancelled")
        if paper is None:
            raise PaperNotFoundError(paper_id)
        return paper

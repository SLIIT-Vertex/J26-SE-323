"""Photo upload, background marking, parent review and the paper attempts that follow.

The life of one uploaded page:

    uploaded -> grading -> graded         every answer decided without the parent
                        -> needs_review   some answers wait for the parent
                        -> failed_alignment   the photo cannot be used (the parent retakes it)
                        -> error          something failed on our side
    needs_review -> confirmed             the parent decided the unclear answers

Rules this module keeps:

* A question's attempt (source = paper) is created only when ALL its parts are final, and is
  correct only if every part is correct. A question left blank creates no attempt.
* The parent never types "correct": they say what the child wrote or marked, and the same
  comparison rules decide.
* Nothing the parent sees before deciding contains the answer key.
* A reader that cannot be reached never marks anything wrong: the parts wait for the parent.
"""

import io
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

from app.knowledge_tracing.application.grading import (
    GradingConfig,
    ItemJob,
    KeyPart,
    PartRead,
    compare_part,
    grade_items,
)
from app.knowledge_tracing.application.grading.call_log import CallContext
from app.knowledge_tracing.application.grading.prompts import PROMPT_VERSION
from app.knowledge_tracing.application.grading.types import (
    CallInfo,
    ItemRead,
    PartSpec,
    ReviewPolicy,
    VisionError,
    VisionProvider,
)
from app.knowledge_tracing.application.paper_generation import PaperNotFoundError
from app.knowledge_tracing.application.photo_alignment import AlignmentFailure
from app.knowledge_tracing.application.photo_check import check_page_photo
from app.knowledge_tracing.application.photo_crops import encode_png
from app.knowledge_tracing.domain.feature_spec import FeatureSpec
from app.knowledge_tracing.domain.paper import Paper, PaperItem
from app.knowledge_tracing.domain.penalty import PAPER, compute_penalty
from app.knowledge_tracing.domain.submission import FINAL_STATUSES, GradedPart, Submission
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import render_pages
from app.knowledge_tracing.infrastructure.storage.base import StorageBackend, StorageKeyNotFound

logger = logging.getLogger("mindbridge.submissions")

MAX_PHOTO_BYTES = 15 * 1024 * 1024
ASK_INSTRUCTION = "Is it done as the question asks?"
_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
# What the parent's own reading is judged with: every rule-level doubt is settled, because there
# is nobody left to ask. A reading that is still unclear (two options) is sent back to them.
PARENT_CONFIG = GradingConfig(review_policy=ReviewPolicy.reader_unsure(), confidence_min=0.0)


# ---- errors ---------------------------------------------------------------------------------


class SubmissionNotFoundError(Exception):
    pass


class PageNotFoundError(Exception):
    pass


class PaperCancelledError(Exception):
    pass


class PageAlreadyGradedError(Exception):
    """The page was already marked: a new photo would not change it."""


class PageInProgressError(Exception):
    """Some answers on this page already count; finish the unclear ones instead."""


class UnreadablePhotoError(Exception):
    pass


class PhotoTooLargeError(Exception):
    pass


class IncompleteDecisionsError(Exception):
    def __init__(self, missing: list[tuple[int, int]]) -> None:
        super().__init__(f"{len(missing)} answers still need a decision")
        self.missing = missing  # (question number, part number)


class BadDecisionError(Exception):
    def __init__(self, message: str, paper_item_id: UUID | None = None, part_no: int = 1) -> None:
        super().__init__(message)
        self.paper_item_id = paper_item_id
        self.part_no = part_no


# ---- what the parent sees ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewItem:
    paper_item_id: UUID
    position: int
    part_no: int
    part_type: str  # mcq | short
    reading: dict  # {"selected": ...} or {"text": ...}
    reason: str | None
    options: tuple[str, ...] | None = None
    ask: str | None = None  # an instruction part: the parent answers yes or no


@dataclass(frozen=True, slots=True)
class PartResult:
    part_no: int
    result: str | None  # correct | wrong | blank, or None while the part waits


@dataclass(frozen=True, slots=True)
class ItemResult:
    paper_item_id: UUID
    position: int
    question_id: str
    result: str  # correct | wrong | blank | pending_review
    parts: tuple[PartResult, ...] | None = None  # only for a question with several parts


@dataclass(frozen=True, slots=True)
class Summary:
    items: int
    auto_final: int
    needs_review: int


@dataclass(frozen=True, slots=True)
class SubmissionView:
    submission: Submission
    summary: Summary
    review_items: tuple[ReviewItem, ...] = ()
    results: tuple[ItemResult, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    paper_item_id: UUID
    part_no: int = 1
    selected: str | None = None  # a choice part: the option label, None for no answer
    text: str | None = None  # a short part: what the child wrote, "" for no answer
    instruction_met: bool | None = None  # an instruction part: yes or no


# ---- collaborators --------------------------------------------------------------------------


class PaperStore(Protocol):
    def get(self, paper_id: UUID) -> Paper | None: ...

    def items(self, paper_id: UUID) -> list[PaperItem]: ...

    def set_status(self, paper_id: UUID, status: str) -> Paper | None: ...


class KeyStore(Protocol):
    def keys(self, question_ids: list[str], language: str) -> dict[str, list[KeyPart]]: ...


class MasteryRefresher(Protocol):
    def refresh(self, learner_id: UUID) -> object: ...


class UnavailableProvider:
    """Stands in when no reader can be created: every part then waits for the parent."""

    name = "unavailable"
    model = ""
    prompt_version = PROMPT_VERSION

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def read_item(
        self,
        crop: bytes,
        parts: Sequence[PartSpec],
        language: str,
        blank_reference: bytes | None = None,
    ) -> tuple[ItemRead, CallInfo]:
        raise VisionError("not_configured", self.reason)


@dataclass(slots=True)
class _QuestionOutcome:
    paper_item_id: UUID
    statuses: list[str] = field(default_factory=list)


class SubmissionService:
    def __init__(
        self,
        submissions: SqlAlchemySubmissionRepository,
        papers: PaperStore,
        answer_keys: KeyStore,
        storage: StorageBackend,
        provider: VisionProvider,
        spec: FeatureSpec,
        *,
        second_provider: VisionProvider | None = None,
        mastery: MasteryRefresher | None = None,
        config: GradingConfig = GradingConfig(),  # noqa: B008
        workers: int = 3,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.submissions = submissions
        self.papers = papers
        self.answer_keys = answer_keys
        self.storage = storage
        self.provider = provider
        self.second_provider = second_provider
        self.spec = spec
        self.mastery = mastery
        self.config = config
        self.workers = workers
        self.now = now

    # ---- upload ----------------------------------------------------------------------------

    def accept_photo(self, paper_id: UUID, page: int, data: bytes) -> Submission:
        """Store the photo and register it for grading. Grading itself runs in the background."""
        paper = self.papers.get(paper_id)
        if paper is None:
            raise PaperNotFoundError(paper_id)
        if paper.status == "cancelled":
            raise PaperCancelledError(paper_id)
        if not 1 <= page <= paper.page_count:
            raise PageNotFoundError(page)
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoTooLargeError(len(data))
        extension = self._photo_extension(data)

        current = self.submissions.current_for_page(paper_id, page)
        if current is not None:
            if current.status in FINAL_STATUSES:
                raise PageAlreadyGradedError(current.id)
            items = [i.id for i in self.papers.items(paper_id) if i.page == page]
            if self.submissions.items_with_attempts(items):
                raise PageInProgressError(current.id)

        submission_id = uuid4()
        key = f"submissions/{submission_id}/photo.{extension}"
        self.storage.put(key, data, f"image/{'jpeg' if extension == 'jpg' else extension}")
        submission = self.submissions.add_submission(
            Submission(submission_id, paper_id, page, key, "uploaded", None, None, True, self.now())
        )
        self._refresh_paper_status(paper_id)
        return submission

    @staticmethod
    def _photo_extension(data: bytes) -> str:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
                return _EXTENSIONS.get(image.format or "", "jpg")
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
            raise UnreadablePhotoError("not an image") from error

    # ---- grading (background) ---------------------------------------------------------------

    def grade(self, submission_id: UUID) -> None:
        """Straighten, read and mark one uploaded page. Never raises: failures become statuses."""
        if not self.submissions.claim_for_grading(submission_id):
            return  # missing, or somebody else is already on it
        submission = self.submissions.get_submission(submission_id)
        if submission is None:
            return
        try:
            self._grade(submission)
        except Exception:
            logger.exception("grading failed for submission %s", submission_id)
            self.submissions.set_status(submission_id, "error", failure_reason="internal_error")
            self._refresh_paper_status(submission.paper_id)

    def _grade(self, submission: Submission) -> None:
        paper = self.papers.get(submission.paper_id)
        if paper is None:
            self.submissions.set_status(submission.id, "error", failure_reason="paper_missing")
            return
        items = [i for i in self.papers.items(paper.id) if i.page == submission.page]

        try:
            photo = self.storage.get(submission.image_key)
            pdf = self.storage.get(paper.pdf_key)
        except StorageKeyNotFound:
            self.submissions.set_status(submission.id, "error", failure_reason="file_missing")
            self._refresh_paper_status(paper.id)
            return

        def renders():
            return render_pages(pdf)

        try:
            check = check_page_photo(photo, paper, submission.page, items, renders)
        except AlignmentFailure as failure:
            self.submissions.set_status(
                submission.id,
                "failed_alignment",
                failure_reason=failure.reason,
                alignment_info={"reason": failure.reason, **_plain(failure.detail)},
            )
            self._refresh_paper_status(paper.id)
            return

        by_position = {i.position: i for i in items}
        keys = self.answer_keys.keys([i.question_id for i in items], paper.language)
        jobs: list[ItemJob] = []
        jobs_items: list[PaperItem] = []
        crop_keys: dict[UUID, str] = {}
        for crop in check.crops:
            item = by_position[crop.position]
            key = keys.get(item.question_id)
            if not key:
                logger.warning("no answer key for question %s: skipped", item.question_id)
                continue
            crop_key = f"submissions/{submission.id}/crops/{item.id}.png"
            crop_bytes = encode_png(crop.image)
            self.storage.put(crop_key, crop_bytes, "image/png")
            crop_keys[item.id] = crop_key
            jobs.append(
                ItemJob(
                    key,
                    crop_bytes,
                    paper.language,
                    blank_reference=None if crop.blank is None else encode_png(crop.blank),
                    context=CallContext(submission.id, item.id),
                )
            )
            jobs_items.append(item)

        graded = grade_items(
            jobs,
            self.provider,
            workers=self.workers,
            second_provider=self.second_provider,
            config=self.config,
        )

        parts: list[GradedPart] = []
        for item, job, result in zip(jobs_items, jobs, graded, strict=True):
            kinds = {k.part_no: k.kind for k in job.key}
            for part in result.question.parts:
                auto_final = (not part.needs_review) and part.status in ("correct", "wrong", "blank")
                is_choice = kinds.get(part.part_no) == "choice"
                parts.append(
                    GradedPart(
                        id=uuid4(),
                        submission_id=submission.id,
                        paper_item_id=item.id,
                        part_no=part.part_no,
                        crop_key=crop_keys[item.id],
                        vision_provider=result.provider or self.provider.name,
                        vision_model=result.model or getattr(self.provider, "model", ""),
                        prompt_version=result.prompt_version or PROMPT_VERSION,
                        raw_response={
                            "answer": part.read_text,
                            "confidence": part.confidence,
                            "instruction_met": part.instruction_met,
                            "errors": list(result.errors),
                        },
                        match_how=part.how[:120],
                        instruction_met=part.instruction_met,
                        read_selected=part.read_text[:40] if is_choice else None,
                        read_text=None if is_choice else part.read_text,
                        auto_status=part.status,
                        confidence=part.confidence,
                        needs_review=part.needs_review,
                        review_reason=part.review_reason,
                        final_status=part.status if auto_final else None,
                        confirmed_by="auto" if auto_final else None,
                    )
                )
        self.submissions.save_parts(parts, confirmed_at=self.now())

        attempts_made = self._create_attempts(submission, paper, items, parts)
        waiting = any(p.final_status is None for p in parts)
        self.submissions.set_status(
            submission.id,
            "needs_review" if waiting else "graded",
            alignment_info={
                "method": check.alignment.method,
                "page": check.alignment.page,
                "blur_score": round(check.alignment.blur_score, 2),
                **_plain(check.alignment.detail),
            },
            graded_at=self.now(),
        )
        self._refresh_paper_status(paper.id)
        if attempts_made:
            self._refresh_mastery(paper.learner_id)

    # ---- attempts ---------------------------------------------------------------------------

    def _create_attempts(
        self, submission: Submission, paper: Paper, items: list[PaperItem], parts: list[GradedPart]
    ) -> int:
        """One attempt for every question whose parts are all final (blank ones make none)."""
        by_item: dict[UUID, _QuestionOutcome] = {}
        for part in parts:
            outcome = by_item.setdefault(part.paper_item_id, _QuestionOutcome(part.paper_item_id))
            outcome.statuses.append(part.final_status or "pending")
        item_by_id = {i.id: i for i in items}
        made = 0
        for item_id, outcome in by_item.items():
            statuses = outcome.statuses
            if "pending" in statuses or all(s == "blank" for s in statuses):
                continue
            if self.submissions.attempt_exists(item_id):
                continue
            item = item_by_id.get(item_id)
            if item is None:
                continue
            self.submissions.add_paper_attempt(
                learner_id=paper.learner_id,
                question_id=item.question_id,
                language=item.language,
                correct=all(s == "correct" for s in statuses),
                penalty=compute_penalty(PAPER, None, None, self.spec.paper_penalty),
                answered_at=submission.uploaded_at,
                paper_item_id=item_id,
            )
            made += 1
        self.submissions.commit()
        return made

    def _refresh_mastery(self, learner_id: UUID) -> None:
        if self.mastery is None:
            return
        try:
            self.mastery.refresh(learner_id)
        except Exception:
            logger.warning("mastery could not be refreshed for %s", learner_id, exc_info=True)

    # ---- the paper's own status -------------------------------------------------------------

    def _refresh_paper_status(self, paper_id: UUID) -> None:
        paper = self.papers.get(paper_id)
        if paper is None or paper.status == "cancelled":
            return
        current = self.submissions.current_for_paper(paper_id)
        by_page = {s.page: s for s in current}
        if not by_page:
            status = "generated"
        elif any(s.status == "needs_review" for s in current):
            status = "needs_review"
        elif len(by_page) == paper.page_count and all(
            s.status in FINAL_STATUSES for s in by_page.values()
        ):
            status = "confirmed" if any(s.status == "confirmed" for s in current) else "graded"
        else:
            status = "partially_uploaded"
        if status != paper.status:
            self.papers.set_status(paper_id, status)

    # ---- reading a submission ---------------------------------------------------------------

    def view(self, submission_id: UUID) -> SubmissionView:
        submission = self.submissions.get_submission(submission_id)
        if submission is None:
            raise SubmissionNotFoundError(submission_id)
        paper = self.papers.get(submission.paper_id)
        if paper is None:
            raise SubmissionNotFoundError(submission_id)
        parts = self.submissions.parts(submission_id)
        if not parts:
            return SubmissionView(submission, Summary(0, 0, 0))

        items = {i.id: i for i in self.papers.items(paper.id) if i.page == submission.page}
        keys = self.answer_keys.keys([i.question_id for i in items.values()], paper.language)

        grouped: dict[UUID, list[GradedPart]] = {}
        for part in parts:
            grouped.setdefault(part.paper_item_id, []).append(part)

        review: list[ReviewItem] = []
        results: list[ItemResult] = []
        auto_final = needs_review = 0
        for item_id, item_parts in sorted(
            grouped.items(), key=lambda kv: items[kv[0]].position if kv[0] in items else 0
        ):
            item = items.get(item_id)
            if item is None:
                continue
            key_by_no = {k.part_no: k for k in keys.get(item.question_id, [])}
            waiting = [p for p in item_parts if not p.is_final]
            if waiting:
                needs_review += 1
            elif all(p.confirmed_by == "auto" for p in item_parts):
                auto_final += 1
            for part in waiting:
                key = key_by_no.get(part.part_no)
                kind = key.kind if key else "text"
                is_choice = kind == "choice"
                review.append(
                    ReviewItem(
                        paper_item_id=item_id,
                        position=item.position,
                        part_no=part.part_no,
                        part_type="mcq" if is_choice else "short",
                        reading={"selected": part.read_selected}
                        if is_choice
                        else {"text": part.read_text or ""},
                        reason=part.review_reason,
                        options=tuple(key.option_labels) if is_choice and key and key.option_labels else None,
                        ask=ASK_INSTRUCTION if kind == "instruction" else None,
                    )
                )
            results.append(self._item_result(item, item_parts, waiting))

        return SubmissionView(
            submission,
            Summary(len(grouped), auto_final, needs_review),
            tuple(review),
            tuple(results),
        )

    @staticmethod
    def _item_result(item: PaperItem, item_parts: list[GradedPart], waiting: list[GradedPart]) -> ItemResult:
        statuses = [p.final_status for p in item_parts]
        if waiting:
            result = "pending_review"
        elif all(s == "blank" for s in statuses):
            result = "blank"
        elif all(s == "correct" for s in statuses):
            result = "correct"
        else:
            result = "wrong"
        detail = None
        if len(item_parts) > 1:
            detail = tuple(
                PartResult(p.part_no, p.final_status) for p in sorted(item_parts, key=lambda p: p.part_no)
            )
        return ItemResult(item.id, item.position, item.question_id, result, detail)

    def crop(self, submission_id: UUID, paper_item_id: UUID) -> bytes:
        parts = [p for p in self.submissions.parts(submission_id) if p.paper_item_id == paper_item_id]
        if not parts or not parts[0].crop_key:
            raise SubmissionNotFoundError(paper_item_id)
        return self.storage.get(parts[0].crop_key)

    # ---- the parent decides -----------------------------------------------------------------

    def confirm(
        self, submission_id: UUID, decisions: Sequence[Decision], parent_id: str = "parent"
    ) -> SubmissionView:
        submission = self.submissions.get_submission(submission_id)
        if submission is None:
            raise SubmissionNotFoundError(submission_id)
        paper = self.papers.get(submission.paper_id)
        if paper is None:
            raise SubmissionNotFoundError(submission_id)
        parts = self.submissions.parts(submission_id)
        waiting = {(p.paper_item_id, p.part_no): p for p in parts if not p.is_final}
        if not waiting:  # already decided: asking again changes nothing
            return self.view(submission_id)
        if submission.status not in ("needs_review", "confirmed"):
            raise BadDecisionError("this page is not waiting for a decision")

        items = {i.id: i for i in self.papers.items(paper.id) if i.page == submission.page}
        keys = self.answer_keys.keys([i.question_id for i in items.values()], paper.language)

        given = {(d.paper_item_id, d.part_no): d for d in decisions}
        for ident in given:
            if ident not in waiting:
                raise BadDecisionError(
                    "this answer is not waiting for a decision", ident[0], ident[1]
                )
        missing = [
            (items[i].position, n) for (i, n) in waiting if (i, n) not in given and i in items
        ]
        if missing:
            raise IncompleteDecisionsError(sorted(missing))

        decided_at = self.now()
        graded: dict[tuple[UUID, int], tuple[str, str | None, str | None, bool | None]] = {}
        for ident, part in waiting.items():
            decision = given[ident]
            item = items[ident[0]]
            key = next(
                (k for k in keys.get(item.question_id, []) if k.part_no == part.part_no), None
            )
            if key is None:
                raise BadDecisionError("no answer key for this part", ident[0], ident[1])
            graded[ident] = self._grade_decision(decision, key, ident)

        for ident, (status, selected, text, met) in graded.items():
            self.submissions.decide_part(
                waiting[ident].id,
                final_status=status,
                confirmed_by=parent_id[:64],
                confirmed_at=decided_at,
                read_selected=selected,
                read_text=text,
                instruction_met=met,
            )
        self.submissions.commit()

        parts_after = self.submissions.parts(submission_id)
        attempts_made = self._create_attempts(
            submission, paper, list(items.values()), parts_after
        )
        if all(p.is_final for p in parts_after):
            self.submissions.set_status(submission.id, "confirmed", confirmed_at=decided_at)
        self._refresh_paper_status(paper.id)
        if attempts_made:
            self._refresh_mastery(paper.learner_id)
        return self.view(submission_id)

    def _grade_decision(
        self, decision: Decision, key: KeyPart, ident: tuple[UUID, int]
    ) -> tuple[str, str | None, str | None, bool | None]:
        """Mark the parent's reading with the same rules. Returns (status, selected, text, met)."""
        has_text = bool(key.alternatives)
        if key.kind == "choice":
            selected = (decision.selected or "").strip()
            read = PartRead(part=key.part_no, answer=selected, blank=not selected, confidence=1.0)
            shown = (selected or None, None)
        elif has_text:
            text = (decision.text or "").strip()
            read = PartRead(
                part=key.part_no,
                answer=text,
                blank=not text and decision.instruction_met is not True,
                confidence=1.0,
                instruction_met=decision.instruction_met,
            )
            shown = (None, text)
        else:  # an instruction-only part: the parent says yes or no
            if decision.instruction_met is None:
                raise BadDecisionError("answer yes or no for this part", ident[0], ident[1])
            read = PartRead(
                part=key.part_no,
                answer="",
                blank=False,
                confidence=1.0,
                instruction_met=decision.instruction_met,
            )
            shown = (None, "")
        if key.instruction is not None and has_text and decision.instruction_met is None:
            raise BadDecisionError("answer yes or no for the instruction", ident[0], ident[1])

        grade = compare_part(read, key, PARENT_CONFIG, second_agrees=True)
        if grade.needs_review or grade.status not in ("correct", "wrong", "blank"):
            raise BadDecisionError(
                "this cannot be decided as given: choose a single option or write the answer",
                ident[0],
                ident[1],
            )
        return grade.status, shown[0], shown[1], decision.instruction_met


def _plain(detail: dict) -> dict:
    """Only simple values, so the alignment record is always storable."""
    out: dict = {}
    for key, value in detail.items():
        if isinstance(value, bool | int | float | str) or value is None:
            out[key] = value
        elif isinstance(value, list | tuple):
            out[key] = [v if isinstance(v, bool | int | float | str) else str(v) for v in value]
        else:
            out[key] = str(value)
    return out

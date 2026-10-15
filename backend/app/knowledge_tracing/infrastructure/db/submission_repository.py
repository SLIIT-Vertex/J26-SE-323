from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.knowledge_tracing.domain.submission import GradedPart, Submission
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    GradedAnswerModel,
    PaperSubmissionModel,
)


def _submission(model: PaperSubmissionModel) -> Submission:
    return Submission(
        id=model.id,
        paper_id=model.paper_id,
        page=model.page,
        image_key=model.image_key,
        status=model.status,
        failure_reason=model.failure_reason,
        alignment_info=model.alignment_info,
        is_current=model.is_current,
        uploaded_at=model.uploaded_at,
        report_viewed_at=model.report_viewed_at,
        files_deleted_at=model.files_deleted_at,
    )


def _part(model: GradedAnswerModel) -> GradedPart:
    return GradedPart(
        id=model.id,
        submission_id=model.submission_id,
        paper_item_id=model.paper_item_id,
        part_no=model.part_no,
        crop_key=model.crop_key,
        vision_provider=model.vision_provider,
        vision_model=model.vision_model,
        prompt_version=model.prompt_version,
        raw_response=model.raw_response,
        match_how=model.match_how,
        instruction_met=model.instruction_met,
        read_selected=model.read_selected,
        read_text=model.read_text,
        auto_status=model.auto_status,
        confidence=model.confidence,
        needs_review=model.needs_review,
        review_reason=model.review_reason,
        final_status=model.final_status,
        confirmed_by=model.confirmed_by,
    )


class SqlAlchemySubmissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- submissions -----------------------------------------------------------------------

    def add_submission(self, submission: Submission) -> Submission:
        """Insert as the current photo of its page, replacing the one that was current."""
        self.session.execute(
            update(PaperSubmissionModel)
            .where(
                PaperSubmissionModel.paper_id == submission.paper_id,
                PaperSubmissionModel.page == submission.page,
                PaperSubmissionModel.is_current.is_(True),
            )
            .values(is_current=False)
        )
        self.session.flush()
        self.session.add(
            PaperSubmissionModel(
                id=submission.id,
                paper_id=submission.paper_id,
                page=submission.page,
                image_key=submission.image_key,
                status=submission.status,
                is_current=True,
            )
        )
        self.session.commit()
        stored = self.session.get(PaperSubmissionModel, submission.id)
        assert stored is not None
        return _submission(stored)

    def get_submission(self, submission_id: UUID) -> Submission | None:
        model = self.session.get(PaperSubmissionModel, submission_id)
        return _submission(model) if model else None

    def current_for_page(self, paper_id: UUID, page: int) -> Submission | None:
        model = self.session.scalars(
            select(PaperSubmissionModel).where(
                PaperSubmissionModel.paper_id == paper_id,
                PaperSubmissionModel.page == page,
                PaperSubmissionModel.is_current.is_(True),
            )
        ).first()
        return _submission(model) if model else None

    def current_for_paper(self, paper_id: UUID) -> list[Submission]:
        models = self.session.scalars(
            select(PaperSubmissionModel)
            .where(
                PaperSubmissionModel.paper_id == paper_id,
                PaperSubmissionModel.is_current.is_(True),
            )
            .order_by(PaperSubmissionModel.page)
        ).all()
        return [_submission(m) for m in models]

    def claim_for_grading(self, submission_id: UUID) -> bool:
        """Move uploaded -> grading, once. False if another worker already took it."""
        result = self.session.execute(
            update(PaperSubmissionModel)
            .where(
                PaperSubmissionModel.id == submission_id,
                PaperSubmissionModel.status == "uploaded",
            )
            .values(status="grading")
        )
        self.session.commit()
        return (result.rowcount or 0) == 1

    def set_status(
        self,
        submission_id: UUID,
        status: str,
        *,
        failure_reason: str | None = None,
        alignment_info: dict | None = None,
        graded_at: datetime | None = None,
        confirmed_at: datetime | None = None,
    ) -> None:
        model = self.session.get(PaperSubmissionModel, submission_id)
        if model is None:
            return
        model.status = status
        model.failure_reason = failure_reason
        if alignment_info is not None:
            model.alignment_info = alignment_info
        if graded_at is not None:
            model.graded_at = graded_at
        if confirmed_at is not None:
            model.confirmed_at = confirmed_at
        self.session.commit()

    def mark_report_viewed(self, submission_ids: list[UUID], viewed_at: datetime) -> None:
        """Remember the first time each page was seen in a report (it is never moved)."""
        if not submission_ids:
            return
        self.session.execute(
            update(PaperSubmissionModel)
            .where(
                PaperSubmissionModel.id.in_(submission_ids),
                PaperSubmissionModel.report_viewed_at.is_(None),
            )
            .values(report_viewed_at=viewed_at)
        )
        self.session.commit()

    def with_files(self) -> list[Submission]:
        """Every submission whose photo and crops are still in storage."""
        models = self.session.scalars(
            select(PaperSubmissionModel).where(PaperSubmissionModel.files_deleted_at.is_(None))
        ).all()
        return [_submission(m) for m in models]

    def mark_files_deleted(self, submission_id: UUID, deleted_at: datetime) -> None:
        """Record that the files are gone and forget where the crops were."""
        self.session.execute(
            update(GradedAnswerModel)
            .where(GradedAnswerModel.submission_id == submission_id)
            .values(crop_key=None)
        )
        self.session.execute(
            update(PaperSubmissionModel)
            .where(PaperSubmissionModel.id == submission_id)
            .values(files_deleted_at=deleted_at)
        )
        self.session.commit()

    # ---- graded parts ----------------------------------------------------------------------

    def save_parts(self, parts: list[GradedPart], confirmed_at: datetime | None = None) -> None:
        for part in parts:
            self.session.add(
                GradedAnswerModel(
                    id=part.id,
                    submission_id=part.submission_id,
                    paper_item_id=part.paper_item_id,
                    part_no=part.part_no,
                    crop_key=part.crop_key,
                    vision_provider=part.vision_provider,
                    vision_model=part.vision_model,
                    prompt_version=part.prompt_version,
                    raw_response=part.raw_response,
                    match_how=part.match_how,
                    instruction_met=part.instruction_met,
                    read_selected=part.read_selected,
                    read_text=part.read_text,
                    auto_status=part.auto_status,
                    confidence=part.confidence,
                    needs_review=part.needs_review,
                    review_reason=part.review_reason,
                    final_status=part.final_status,
                    confirmed_by=part.confirmed_by,
                    confirmed_at=confirmed_at if part.final_status else None,
                )
            )
        self.session.commit()

    def parts(self, submission_id: UUID) -> list[GradedPart]:
        models = self.session.scalars(
            select(GradedAnswerModel)
            .where(GradedAnswerModel.submission_id == submission_id)
            .order_by(GradedAnswerModel.paper_item_id, GradedAnswerModel.part_no)
        ).all()
        return [_part(m) for m in models]

    def decide_part(
        self,
        part_id: UUID,
        *,
        final_status: str,
        confirmed_by: str,
        confirmed_at: datetime,
        read_selected: str | None,
        read_text: str | None,
        instruction_met: bool | None,
    ) -> None:
        model = self.session.get(GradedAnswerModel, part_id)
        if model is None:
            return
        model.final_status = final_status
        model.confirmed_by = confirmed_by
        model.confirmed_at = confirmed_at
        model.needs_review = False
        model.read_selected = read_selected
        model.read_text = read_text
        if instruction_met is not None:
            model.instruction_met = instruction_met

    def commit(self) -> None:
        self.session.commit()

    # ---- attempts --------------------------------------------------------------------------

    def attempt_exists(self, paper_item_id: UUID) -> bool:
        return (
            self.session.scalars(
                select(AttemptModel.id).where(AttemptModel.paper_item_id == paper_item_id)
            ).first()
            is not None
        )

    def items_with_attempts(self, paper_item_ids: list[UUID]) -> set[UUID]:
        if not paper_item_ids:
            return set()
        rows = self.session.scalars(
            select(AttemptModel.paper_item_id).where(AttemptModel.paper_item_id.in_(paper_item_ids))
        ).all()
        return {r for r in rows if r is not None}

    def add_paper_attempt(
        self,
        *,
        learner_id: UUID,
        question_id: str,
        language: str,
        correct: bool,
        penalty: float,
        answered_at: datetime,
        paper_item_id: UUID,
    ) -> None:
        self.session.add(
            AttemptModel(
                learner_id=learner_id,
                question_id=question_id,
                language=language,
                source=0,
                correct=correct,
                time_ms=None,
                hints=None,
                penalty=penalty,
                answered_at=answered_at,
                paper_item_id=paper_item_id,
            )
        )

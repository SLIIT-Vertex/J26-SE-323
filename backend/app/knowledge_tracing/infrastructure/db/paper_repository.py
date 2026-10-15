from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.paper_generation import VariantImage
from app.knowledge_tracing.domain.paper import Paper, PaperItem
from app.knowledge_tracing.infrastructure.db.models import (
    PaperItemModel,
    PaperModel,
    QuestionModel,
    QuestionVariantModel,
)
from app.shared.learner.model import LearnerModel


def _paper(model: PaperModel) -> Paper:
    return Paper(
        id=model.id,
        learner_id=model.learner_id,
        token=model.qr_token,
        week_start=model.week_start,
        status=model.status,
        mode=model.mode,
        language=model.language,
        params=dict(model.params),
        mastery_snapshot_id=model.mastery_snapshot_id,
        model_version=model.model_version,
        page_count=model.page_count,
        pdf_key=model.pdf_key,
        created_at=model.created_at,
    )


class SqlAlchemyPaperRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def learner_exists(self, learner_id: UUID) -> bool:
        return self.session.get(LearnerModel, learner_id) is not None

    def learner_joined_at(self, learner_id: UUID) -> datetime | None:
        learner = self.session.get(LearnerModel, learner_id)
        return learner.created_at if learner else None

    def covered_diagnostic_skills(self, learner_id: UUID) -> set[str]:
        """Skills that the learner's earlier diagnostic papers already asked about."""
        rows = self.session.scalars(
            select(PaperModel.params).where(
                PaperModel.learner_id == learner_id,
                PaperModel.mode == "diagnostic",
                PaperModel.status != "cancelled",
            )
        ).all()
        covered: set[str] = set()
        for params in rows:
            covered.update(params.get("diagnostic_skills", []))
        return covered

    def find_for_week(self, learner_id: UUID, week_start: date) -> Paper | None:
        model = self.session.scalars(
            select(PaperModel).where(
                PaperModel.learner_id == learner_id,
                PaperModel.week_start == week_start,
                PaperModel.status != "cancelled",
            )
        ).first()
        return _paper(model) if model else None

    def token_exists(self, token: str) -> bool:
        return (
            self.session.scalars(select(PaperModel.id).where(PaperModel.qr_token == token)).first()
            is not None
        )

    def variants(self, question_ids: list[str], language: str) -> dict[str, VariantImage]:
        if not question_ids:
            return {}
        rows = self.session.execute(
            select(
                QuestionVariantModel.question_id,
                QuestionVariantModel.image_key,
                QuestionVariantModel.image_width_px,
                QuestionVariantModel.image_height_px,
            ).where(
                QuestionVariantModel.question_id.in_(question_ids),
                QuestionVariantModel.language == language,
            )
        ).all()
        return {qid: VariantImage(key, w, h) for qid, key, w, h in rows}

    def add(self, paper: Paper, items: list[PaperItem]) -> tuple[Paper, bool]:
        """Insert in one transaction. If the week was taken in the meantime, return that paper."""
        self.session.add(
            PaperModel(
                id=paper.id,
                learner_id=paper.learner_id,
                qr_token=paper.token,
                week_start=paper.week_start,
                status=paper.status,
                mode=paper.mode,
                language=paper.language,
                params=paper.params,
                mastery_snapshot_id=paper.mastery_snapshot_id,
                model_version=paper.model_version,
                page_count=paper.page_count,
                pdf_key=paper.pdf_key,
            )
        )
        self.session.flush()  # the papers row must exist before its items
        for item in items:
            self.session.add(
                PaperItemModel(
                    id=item.id,
                    paper_id=item.paper_id,
                    position=item.position,
                    question_id=item.question_id,
                    language=item.language,
                    page=item.page,
                    block_x=item.block_x,
                    block_y=item.block_y,
                    block_w=item.block_w,
                    block_h=item.block_h,
                    answer_boxes=item.answer_boxes,
                    shown_difficulty=item.shown_difficulty,
                    role=item.role,
                    predicted_p=item.predicted_p,
                )
            )
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find_for_week(paper.learner_id, paper.week_start)
            if existing is not None:
                return existing, False
            raise
        stored = self.session.get(PaperModel, paper.id)
        assert stored is not None
        self.session.refresh(stored)
        return _paper(stored), True

    def get(self, paper_id: UUID) -> Paper | None:
        model = self.session.get(PaperModel, paper_id)
        return _paper(model) if model else None

    def list_for_learner(self, learner_id: UUID, limit: int) -> list[Paper]:
        models = self.session.scalars(
            select(PaperModel)
            .where(PaperModel.learner_id == learner_id)
            .order_by(PaperModel.week_start.desc(), PaperModel.created_at.desc())
            .limit(limit)
        ).all()
        return [_paper(m) for m in models]

    def items(self, paper_id: UUID) -> list[PaperItem]:
        rows = self.session.execute(
            select(PaperItemModel, QuestionModel.skill_code)
            .join(QuestionModel, QuestionModel.id == PaperItemModel.question_id)
            .where(PaperItemModel.paper_id == paper_id)
            .order_by(PaperItemModel.position)
        ).all()
        return [
            PaperItem(
                id=m.id,
                paper_id=m.paper_id,
                position=m.position,
                question_id=m.question_id,
                skill_code=skill,
                language=m.language,
                page=m.page,
                block_x=m.block_x,
                block_y=m.block_y,
                block_w=m.block_w,
                block_h=m.block_h,
                shown_difficulty=m.shown_difficulty,
                role=m.role,
                predicted_p=m.predicted_p,
                answer_boxes=m.answer_boxes,
            )
            for m, skill in rows
        ]

    def set_status(self, paper_id: UUID, status: str) -> Paper | None:
        model = self.session.get(PaperModel, paper_id)
        if model is None:
            return None
        model.status = status
        self.session.commit()
        self.session.refresh(model)
        return _paper(model)

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.paper_planning import QuestionRow, SkillActivity
from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.mastery import MasterySnapshot, SkillEstimate
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    MasterySnapshotModel,
    PaperItemModel,
    PaperModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.shared.learner.model import LearnerModel


class SqlAlchemyPaperInputRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._attempts = SqlAlchemyAttemptRepository(session)

    def learner_language(self, learner_id: UUID) -> str | None:
        learner = self.session.get(LearnerModel, learner_id)
        return learner.preferred_language if learner else None

    def skill_catalog(self) -> list[tuple[str, str, int]]:
        rows = self.session.execute(
            select(SkillModel.code, SkillModel.area, SkillModel.sort_index)
        ).all()
        return [(code, area, index) for code, area, index in rows]

    def skill_activity(self, learner_id: UUID) -> dict[str, SkillActivity]:
        # Game answers with no bank question carry their own skill, so they count here too.
        skill = func.coalesce(QuestionModel.skill_code, AttemptModel.skill_code)
        statement = (
            select(
                skill,
                AttemptModel.source,
                func.count(),
                func.sum(case((AttemptModel.correct.is_(True), 1), else_=0)),
            )
            .outerjoin(QuestionModel, QuestionModel.id == AttemptModel.question_id)
            .where(AttemptModel.learner_id == learner_id)
            .group_by(skill, AttemptModel.source)
        )
        digital: dict[str, tuple[int, int]] = {}
        paper: dict[str, int] = {}
        for code, source, total, correct in self.session.execute(statement).all():
            if source == 1:
                digital[code] = (int(total), int(correct or 0))
            else:
                paper[code] = int(total)
        return {
            code: SkillActivity(
                digital_attempts=digital.get(code, (0, 0))[0],
                digital_correct=digital.get(code, (0, 0))[1],
                paper_attempts=paper.get(code, 0),
            )
            for code in set(digital) | set(paper)
        }

    def recently_answered(self, learner_id: UUID, since: datetime) -> set[str]:
        rows = self.session.scalars(
            select(AttemptModel.question_id)
            .where(
                AttemptModel.learner_id == learner_id,
                AttemptModel.answered_at >= since,
                AttemptModel.question_id.is_not(None),  # a game answer has no bank question
            )
            .distinct()
        ).all()
        return set(rows)

    def question_rows(self, language: str) -> list[QuestionRow]:
        rows = self.session.execute(
            select(
                QuestionModel.id,
                QuestionModel.skill_code,
                QuestionModel.difficulty,
                QuestionModel.est_seconds,
                QuestionVariantModel.image_width_px,
                QuestionVariantModel.image_height_px,
            )
            .join(
                QuestionVariantModel,
                (QuestionVariantModel.question_id == QuestionModel.id)
                & (QuestionVariantModel.language == language),
            )
            .where(QuestionModel.active.is_(True))
            .order_by(QuestionModel.id)
        ).all()
        return [QuestionRow(*row) for row in rows]

    def recent_paper_question_ids(self, learner_id: UUID, papers: int) -> set[str]:
        recent = self.session.scalars(
            select(PaperModel.id)
            .where(PaperModel.learner_id == learner_id, PaperModel.status != "cancelled")
            .order_by(PaperModel.week_start.desc(), PaperModel.created_at.desc())
            .limit(papers)
        ).all()
        if not recent:
            return set()
        rows = self.session.scalars(
            select(PaperItemModel.question_id).where(PaperItemModel.paper_id.in_(recent))
        ).all()
        return set(rows)

    def previous_snapshot(self, learner_id: UUID) -> MasterySnapshot | None:
        model = self.session.scalars(
            select(MasterySnapshotModel)
            .where(MasterySnapshotModel.learner_id == learner_id)
            .order_by(MasterySnapshotModel.computed_at.desc(), MasterySnapshotModel.id.desc())
            .offset(1)
            .limit(1)
        ).first()
        if model is None:
            return None
        return MasterySnapshot(
            id=model.id,
            learner_id=model.learner_id,
            computed_at=model.computed_at,
            model_version=model.model_version,
            n_attempts=model.n_attempts,
            skills=tuple(
                SkillEstimate(entry["code"], entry["mastery"], entry["attempts"])
                for entry in model.skills
            ),
        )

    def history(self, learner_id: UUID, limit: int | None) -> list[HistoryItem]:
        return self._attempts.history(learner_id, limit)

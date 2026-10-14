from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.knowledge_tracing.domain.attempt import Attempt, HistoryItem
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.shared.learner.model import LearnerModel


def _to_domain(model: AttemptModel) -> Attempt:
    return Attempt(
        id=model.id,
        learner_id=model.learner_id,
        question_id=model.question_id,
        language=model.language,
        source=model.source,
        correct=model.correct,
        time_ms=model.time_ms,
        hints=model.hints,
        penalty=model.penalty,
        answered_at=model.answered_at,
        idempotency_key=model.idempotency_key,
        paper_item_id=model.paper_item_id,
    )


class SqlAlchemyAttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def learner_exists(self, learner_id: UUID) -> bool:
        return self.session.get(LearnerModel, learner_id) is not None

    def question_exists(self, question_id: str) -> bool:
        return self.session.get(QuestionModel, question_id) is not None

    def variant_exists(self, question_id: str, language: str) -> bool:
        return self.session.get(QuestionVariantModel, (question_id, language)) is not None

    def find_by_idempotency_key(self, key: str) -> Attempt | None:
        model = self.session.scalars(
            select(AttemptModel).where(AttemptModel.idempotency_key == key)
        ).first()
        return _to_domain(model) if model else None

    def add(self, attempt: Attempt) -> tuple[Attempt, bool]:
        model = AttemptModel(
            learner_id=attempt.learner_id,
            question_id=attempt.question_id,
            language=attempt.language,
            source=attempt.source,
            correct=attempt.correct,
            time_ms=attempt.time_ms,
            hints=attempt.hints,
            penalty=attempt.penalty,
            answered_at=attempt.answered_at,
            idempotency_key=attempt.idempotency_key,
            paper_item_id=attempt.paper_item_id,
        )
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            if attempt.idempotency_key:
                existing = self.find_by_idempotency_key(attempt.idempotency_key)
                if existing is not None:
                    return existing, False
            raise
        self.session.refresh(model)
        return _to_domain(model), True

    def history(self, learner_id: UUID, limit: int | None = None) -> list[HistoryItem]:
        statement = (
            select(AttemptModel, QuestionModel.difficulty, SkillModel.code, SkillModel.sort_index)
            .join(QuestionModel, QuestionModel.id == AttemptModel.question_id)
            .join(SkillModel, SkillModel.code == QuestionModel.skill_code)
            .where(AttemptModel.learner_id == learner_id)
        )
        if limit is None:
            statement = statement.order_by(AttemptModel.answered_at, AttemptModel.id)
            rows = self.session.execute(statement).all()
        else:
            statement = statement.order_by(
                AttemptModel.answered_at.desc(), AttemptModel.id.desc()
            ).limit(limit)
            rows = list(reversed(self.session.execute(statement).all()))
        return [
            HistoryItem(
                attempt_id=attempt.id,
                question_id=attempt.question_id,
                language=attempt.language,
                skill_code=skill_code,
                skill_index=skill_index,
                difficulty=difficulty,
                correct=attempt.correct,
                source=attempt.source,
                penalty=attempt.penalty,
                answered_at=attempt.answered_at,
            )
            for attempt, difficulty, skill_code, skill_index in rows
        ]

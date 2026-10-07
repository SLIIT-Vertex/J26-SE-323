from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.learner.domain import Learner
from app.shared.learner.model import LearnerModel


class LearnerRepository(Protocol):
    def add(self, learner: Learner) -> Learner: ...

    def get(self, learner_id: UUID) -> Learner | None: ...

    def list(self) -> list[Learner]: ...


def _to_domain(model: LearnerModel) -> Learner:
    return Learner(
        id=model.id,
        grade=model.grade,
        preferred_language=model.preferred_language,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyLearnerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, learner: Learner) -> Learner:
        model = LearnerModel(
            id=learner.id,
            grade=learner.grade,
            preferred_language=learner.preferred_language,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_domain(model)

    def get(self, learner_id: UUID) -> Learner | None:
        model = self.session.get(LearnerModel, learner_id)
        return _to_domain(model) if model else None

    def list(self) -> list[Learner]:
        models = self.session.scalars(select(LearnerModel).order_by(LearnerModel.created_at)).all()
        return [_to_domain(model) for model in models]


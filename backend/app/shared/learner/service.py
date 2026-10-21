from uuid import UUID, uuid4

from app.shared.learner.domain import Learner
from app.shared.learner.repository import LearnerRepository


class LearnerNotFoundError(Exception):
    pass


class LearnerService:
    def __init__(self, repository: LearnerRepository) -> None:
        self.repository = repository

    def create(
        self, grade: int, preferred_language: str, display_name: str | None = None
    ) -> Learner:
        if display_name is not None:
            display_name = display_name.strip()
            if not display_name or len(display_name) > 60:
                raise ValueError("Name must contain 1 to 60 characters")
        return self.repository.add(
            Learner(
                id=uuid4(),
                grade=grade,
                preferred_language=preferred_language,
                display_name=display_name,
            )
        )

    def get(self, learner_id: UUID) -> Learner:
        learner = self.repository.get(learner_id)
        if learner is None:
            raise LearnerNotFoundError(learner_id)
        return learner

    def list(self) -> list[Learner]:
        return self.repository.list()

    def set_name(self, learner_id: UUID, display_name: str | None) -> Learner:
        if display_name is not None:
            display_name = display_name.strip()
            if not display_name or len(display_name) > 60:
                raise ValueError("Name must contain 1 to 60 characters")
        learner = self.repository.set_name(learner_id, display_name)
        if learner is None:
            raise LearnerNotFoundError(learner_id)
        return learner

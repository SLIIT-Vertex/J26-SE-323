from uuid import UUID, uuid4

from app.shared.learner.domain import Learner
from app.shared.learner.repository import LearnerRepository


class LearnerNotFoundError(Exception):
    pass


class LearnerService:
    def __init__(self, repository: LearnerRepository) -> None:
        self.repository = repository

    def create(self, grade: int, preferred_language: str) -> Learner:
        return self.repository.add(
            Learner(id=uuid4(), grade=grade, preferred_language=preferred_language)
        )

    def get(self, learner_id: UUID) -> Learner:
        learner = self.repository.get(learner_id)
        if learner is None:
            raise LearnerNotFoundError(learner_id)
        return learner

    def list(self) -> list[Learner]:
        return self.repository.list()


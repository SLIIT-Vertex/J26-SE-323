"""Application port for an optional, current-session Learning State reading."""

from datetime import datetime
from typing import Protocol
from uuid import UUID


class LearningStateReader(Protocol):
    def read(
        self, *, learner_id: UUID, skill_id: str, session_id: str, at: datetime
    ) -> dict[str, object]: ...


def read_learning_state(provider: LearningStateReader | None, **values) -> dict[str, object]:
    if provider is None:
        return {"status": "not_available", "reason": "NOT_FOUND"}
    return provider.read(**values)

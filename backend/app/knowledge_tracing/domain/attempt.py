from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Attempt:
    id: int | None
    learner_id: UUID
    question_id: str | None  # None for a game answer that has its own skill and difficulty
    language: str
    source: int
    correct: bool
    time_ms: int | None
    hints: int | None
    penalty: float
    answered_at: datetime
    idempotency_key: str | None = None
    paper_item_id: UUID | None = None
    skill_code: str | None = None  # set with difficulty when there is no bank question
    difficulty: str | None = None


@dataclass(frozen=True, slots=True)
class HistoryItem:
    """One step of a learner's history, in the form the knowledge model reads."""

    attempt_id: int
    question_id: str | None
    language: str
    skill_code: str
    skill_index: int
    difficulty: str
    correct: bool
    source: int
    penalty: float
    answered_at: datetime

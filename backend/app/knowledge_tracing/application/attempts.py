from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.knowledge_tracing.domain.attempt import Attempt, HistoryItem
from app.knowledge_tracing.domain.feature_spec import FeatureSpec
from app.knowledge_tracing.domain.penalty import DIGITAL, compute_penalty

FUTURE_TOLERANCE = timedelta(minutes=5)


class LearnerNotFoundError(Exception):
    pass


class QuestionNotFoundError(Exception):
    pass


class LanguageNotAvailableError(Exception):
    pass


class AnsweredInFutureError(Exception):
    pass


class IdempotencyKeyReusedError(Exception):
    pass


class SkillNotFoundError(Exception):
    pass


class InvalidAttemptError(Exception):
    """The answer names both a bank question and a skill, or neither."""


DIFFICULTIES = ("easy", "medium", "hard")


class AttemptRepository(Protocol):
    def learner_exists(self, learner_id: UUID) -> bool: ...

    def question_exists(self, question_id: str) -> bool: ...

    def variant_exists(self, question_id: str, language: str) -> bool: ...

    def find_by_idempotency_key(self, key: str) -> Attempt | None: ...

    def add(self, attempt: Attempt) -> tuple[Attempt, bool]:
        """Insert. Returns (attempt, created); created is False if the key won a race."""
        ...

    def history(self, learner_id: UUID, limit: int | None = None) -> list[HistoryItem]: ...


@dataclass(frozen=True, slots=True)
class DigitalAttemptCommand:
    """One game answer: either a bank question, or the game's own skill and difficulty."""

    learner_id: UUID
    language: str
    correct: bool
    answered_at: datetime
    question_id: str | None = None
    skill_code: str | None = None
    difficulty: str | None = None
    time_ms: int | None = None
    hints: int | None = None
    idempotency_key: str | None = None


class AttemptService:
    def __init__(
        self,
        repository: AttemptRepository,
        spec: FeatureSpec,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.spec = spec
        self.now = now

    def log_digital_attempt(self, command: DigitalAttemptCommand) -> tuple[Attempt, bool]:
        """Record one game answer. Returns (attempt, created); created is False on a replay."""
        if command.idempotency_key:
            existing = self.repository.find_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                return self._replay(existing, command), False

        with_question = command.question_id is not None
        with_skill = command.skill_code is not None or command.difficulty is not None
        if with_question == with_skill:
            raise InvalidAttemptError("give a question_id, or a skill_code and a difficulty")
        if not self.repository.learner_exists(command.learner_id):
            raise LearnerNotFoundError(command.learner_id)
        if command.question_id is not None:
            if not self.repository.question_exists(command.question_id):
                raise QuestionNotFoundError(command.question_id)
            if not self.repository.variant_exists(command.question_id, command.language):
                raise LanguageNotAvailableError((command.question_id, command.language))
        else:
            if command.skill_code is None or command.difficulty is None:
                raise InvalidAttemptError("a game answer needs both a skill_code and a difficulty")
            if command.skill_code not in self.spec.skills:
                raise SkillNotFoundError(command.skill_code)
            if command.difficulty not in DIFFICULTIES:
                raise InvalidAttemptError(f"difficulty must be one of {DIFFICULTIES}")
        if command.answered_at > self.now() + FUTURE_TOLERANCE:
            raise AnsweredInFutureError(command.answered_at)

        attempt = Attempt(
            id=None,
            learner_id=command.learner_id,
            question_id=command.question_id,
            language=command.language,
            source=DIGITAL,
            correct=command.correct,
            time_ms=command.time_ms,
            hints=command.hints,
            penalty=compute_penalty(
                DIGITAL, command.time_ms, command.hints, self.spec.paper_penalty
            ),
            answered_at=command.answered_at,
            idempotency_key=command.idempotency_key,
            skill_code=command.skill_code,
            difficulty=command.difficulty,
        )
        stored, created = self.repository.add(attempt)
        if not created:
            return self._replay(stored, command), False
        return stored, True

    @staticmethod
    def _replay(existing: Attempt, command: DigitalAttemptCommand) -> Attempt:
        same = (
            existing.learner_id == command.learner_id
            and existing.question_id == command.question_id
            and existing.skill_code == command.skill_code
            and existing.difficulty == command.difficulty
            and existing.language == command.language
            and existing.correct == command.correct
        )
        if not same:
            raise IdempotencyKeyReusedError(command.idempotency_key)
        return existing

    def history(self, learner_id: UUID, limit: int | None = None) -> list[HistoryItem]:
        """A learner's attempts, oldest first, digital and paper mixed.

        With a limit, the most recent `limit` attempts are returned, still oldest first.
        """
        return self.repository.history(learner_id, limit)

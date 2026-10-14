"""Computes and stores a learner's mastery from their digital and paper history.

Not to be confused with `mastery.py`, which holds the contract the Adaptive Tutor reads.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.feature_spec import FeatureSpec
from app.knowledge_tracing.domain.mastery import MasterySnapshot, SkillEstimate
from app.knowledge_tracing.infrastructure.ml.service import SkillMastery

# A learner's mastery is recomputed at most this often (the model is cheap, the database is not).
RECOMPUTE_INTERVAL = timedelta(seconds=30)
# The explicit recompute endpoint is allowed more often, but still not in a tight loop.
FORCED_INTERVAL = timedelta(seconds=5)


class LearnerNotFoundError(Exception):
    pass


class ModelUnavailableError(Exception):
    """The trained weights could not be loaded."""


class Estimator(Protocol):
    version: str

    def mastery(self, history: list[HistoryItem]) -> list[SkillMastery]: ...


class MasteryRepository(Protocol):
    def learner_exists(self, learner_id: UUID) -> bool: ...

    def count_attempts(self, learner_id: UUID) -> int: ...

    def latest_snapshot(self, learner_id: UUID) -> MasterySnapshot | None: ...

    def add_snapshot(self, snapshot: MasterySnapshot) -> MasterySnapshot: ...

    def history(self, learner_id: UUID, limit: int | None) -> list[HistoryItem]: ...


class MasteryService:
    def __init__(
        self,
        repository: MasteryRepository,
        estimator: Estimator,
        spec: FeatureSpec,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.estimator = estimator
        self.spec = spec
        self.now = now

    def current(self, learner_id: UUID) -> MasterySnapshot:
        """The latest mastery, computing one when none exists or new answers have arrived.

        New answers trigger a recompute only if the last snapshot is older than the
        debounce interval, so a busy game session does not recompute on every request.
        """
        self._require_learner(learner_id)
        latest = self.repository.latest_snapshot(learner_id)
        if latest is None:
            return self._compute(learner_id)
        if self._age(latest) < RECOMPUTE_INTERVAL:
            return latest
        if self.repository.count_attempts(learner_id) != latest.n_attempts:
            return self._compute(learner_id)
        return latest

    def recompute(self, learner_id: UUID) -> MasterySnapshot:
        """Recompute now (admin/debug), unless one was made a moment ago."""
        self._require_learner(learner_id)
        latest = self.repository.latest_snapshot(learner_id)
        if latest is not None and self._age(latest) < FORCED_INTERVAL:
            return latest
        return self._compute(learner_id)

    def _compute(self, learner_id: UUID) -> MasterySnapshot:
        total = self.repository.count_attempts(learner_id)
        history = self.repository.history(learner_id, self.spec.history_cap)
        estimates = self.estimator.mastery(history)
        snapshot = MasterySnapshot(
            id=None,
            learner_id=learner_id,
            computed_at=self.now(),
            model_version=self.estimator.version,
            n_attempts=total,
            skills=tuple(SkillEstimate(e.code, e.mastery, e.attempts) for e in estimates),
        )
        return self.repository.add_snapshot(snapshot)

    def _require_learner(self, learner_id: UUID) -> None:
        if not self.repository.learner_exists(learner_id):
            raise LearnerNotFoundError(learner_id)

    def _age(self, snapshot: MasterySnapshot) -> timedelta:
        computed_at = snapshot.computed_at
        if computed_at.tzinfo is None:  # some databases drop the time zone
            computed_at = computed_at.replace(tzinfo=UTC)
        return self.now() - computed_at

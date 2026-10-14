"""In-memory unit of work for the episode use cases."""

from dataclasses import replace
from uuid import UUID

from app.gamification.application.episode_state import EpisodeState
from app.gamification.application.errors import EpisodeFlowError
from app.gamification.application.records import (
    AuditEvent,
    GamificationAttempt,
    LearnerSkillSummary,
)
from app.gamification.domain.types import EpisodeId
from app.gamification.infrastructure.memory import InMemoryAuditOutput, InMemoryLearningRecordStore


class InMemoryEpisodeRepository:
    def __init__(self) -> None:
        self._states: dict[EpisodeId, EpisodeState] = {}

    def insert(self, state: EpisodeState) -> None:
        episode_id = state.episode.episode_id
        if episode_id in self._states:
            raise EpisodeFlowError("EPISODE_ALREADY_OPEN")
        self._states[episode_id] = state

    def get(self, episode_id: EpisodeId) -> EpisodeState:
        try:
            return self._states[episode_id]
        except KeyError as error:
            raise LookupError(str(episode_id)) from error

    def save(self, state: EpisodeState) -> EpisodeState:
        current = self.get(state.episode.episode_id)
        if current.revision != state.revision:
            raise EpisodeFlowError("EPISODE_STATE_CONFLICT")
        stored = replace(state, revision=state.revision + 1)
        self._states[state.episode.episode_id] = stored
        return stored


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.episodes = InMemoryEpisodeRepository()
        self.learning_records = InMemoryLearningRecordStore()
        self.audit = InMemoryAuditOutput()
        self._states: dict[EpisodeId, EpisodeState] | None = None
        self._attempts: list[GamificationAttempt] | None = None
        self._summaries: dict[tuple[UUID, str], LearnerSkillSummary] | None = None
        self._events: list[AuditEvent] | None = None

    def begin(self) -> None:
        # Frozen records stay shared. Copy the containers so a rollback can restore them.
        self._states = dict(self.episodes._states)
        self._attempts = list(self.learning_records.recorded_attempts)
        self._summaries = dict(self.learning_records._summaries)
        self._events = list(self.audit.events)

    def commit(self) -> None:
        self._states = None
        self._attempts = None
        self._summaries = None
        self._events = None

    def rollback(self) -> None:
        if self._states is None or self._attempts is None or self._summaries is None:
            return
        if self._events is None:
            return
        self.episodes._states = self._states
        self.learning_records.recorded_attempts = self._attempts
        self.learning_records._summaries = self._summaries
        self.audit.events = self._events
        self.commit()

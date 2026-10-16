"""
Application use case: evaluate one learner-state window and keep the latest state per skill.

Both the HTTP API and in-process callers (for example a game backend that combines its own
behavioural data with browser-derived visual features) use this use case. They must share one
`LearnerStateService` instance, because temporal and learner-history state is kept in memory
per (session_id, learner_id); `get_learner_state_service()` provides that instance.
"""

from collections.abc import Callable
from functools import lru_cache
from uuid import UUID

from pydantic import TypeAdapter

from app.learner_state.application.service import (
    LearnerStateEvaluation,
    LearnerStateService,
    LearnerStateWindow,
)
from app.learner_state.application.support_need import (
    LearnerSkillStateRepository,
    SkillId,
    skill_state_from_evaluation,
)

_SKILL_ID = TypeAdapter(SkillId)


class UnknownLearnerError(LookupError):
    """The learner does not exist in the shared learner store."""


@lru_cache
def get_learner_state_service() -> LearnerStateService:
    """The single service instance whose in-memory session history all callers share."""
    return LearnerStateService()


class LearnerStateRecorder:
    def __init__(
        self,
        *,
        service: LearnerStateService,
        learner_exists: Callable[[UUID], bool],
        skill_states: LearnerSkillStateRepository,
    ) -> None:
        self._service = service
        self._learner_exists = learner_exists
        self._skill_states = skill_states

    def record(self, window: LearnerStateWindow, *, skill_id: str) -> LearnerStateEvaluation:
        """
        Evaluate the window and store the latest state for (learner_id, skill_id).

        `skill_id` is the Universal Skill ID of the answered question; it labels the stored
        state and is not a model input.

        Raises:
            UnknownLearnerError: the learner does not exist (session history is unchanged).
            WindowOrderError: window_id is not greater than the session's last window.
            pydantic.ValidationError: skill_id is blank or longer than 16 characters.
        """
        universal_skill_id = _SKILL_ID.validate_python(skill_id)

        # Checked before evaluation so that an unknown learner never changes session history.
        if not self._learner_exists(window.learner_id):
            raise UnknownLearnerError(window.learner_id)

        evaluation = self._service.evaluate(window)
        self._skill_states.save(
            skill_state_from_evaluation(
                evaluation,
                skill_id=universal_skill_id,
                observed_at=window.timestamp,
            )
        )
        return evaluation

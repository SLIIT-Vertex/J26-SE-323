"""
In-process adapter for the game's answer-time learner-state boundary (Option B).

`GameAnswerRecorder.record_answer()` has the signature of the game's `LearnerStateAnswerGateway`
protocol (`app/gamification/application/session_play.py`), so the game can compose it without its
own application code importing learner-state. The game computes correctness and timing; this
adapter maps those values onto the behavioural model inputs, adds the browser-derived visual
features and records the window through `LearnerStateRecorder`.

The mapping of game values to the ASSISTments-trained behavioural fields is documented in
docs/learner-state/11_GAME_INTEGRATION.md §5. Values marked provisional still need the game
owner's agreement. No field is filled with an invented value: `bottom_hint` is sent as missing
and `task_progress` as unknown.
"""

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.learner_state.application.recording import (
    LearnerStateRecorder,
    get_learner_state_service,
)
from app.learner_state.application.service import (
    LearnerStateService,
    LearnerStateWindow,
    VisualObservation,
)
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.learner_state.infrastructure.feature_builder import BehaviorObservation
from app.shared.learner.repository import SqlAlchemyLearnerRepository

logger = logging.getLogger(__name__)

# One submission per game item, so there is exactly one attempt.
GAME_ATTEMPT_COUNT = 1.0
# Provisional: answered game items (baseline and verification) are treated as main problems
# ("1 = Main problem"), not scaffolding problems.
GAME_ORIGINAL = 1.0

VISUAL_FEATURE_NAMES = (
    "mean_eye_openness",
    "std_eye_openness",
    "mean_gaze_ratio",
    "std_gaze_ratio",
    "mean_pitch",
    "mean_yaw",
    "mean_roll",
    "mean_abs_pitch",
    "mean_abs_yaw",
    "mean_abs_roll",
    "face_visibility_ratio",
)

# No camera, or no consent: a visibility of 0 gives visual reliability 0, so fusion follows the
# behavioural evidence only and the placeholder values never influence the decision.
NO_VISUAL_EVIDENCE = VisualObservation(**dict.fromkeys(VISUAL_FEATURE_NAMES, 0.0))


def behaviour_from_game_answer(
    *, correct: bool, response_time_ms: int, hint_count: int
) -> BehaviorObservation:
    return BehaviorObservation(
        correct=1.0 if correct else 0.0,
        # "Whether or not the student asks for all hints" has no game equivalent.
        bottom_hint=None,
        hint_count=float(hint_count),
        attempt_count=GAME_ATTEMPT_COUNT,
        ms_first_response=float(response_time_ms),
        # Provisional: with a single response, the overlap time is the response time.
        overlap_time=float(response_time_ms),
        original=GAME_ORIGINAL,
    )


def visual_from_game_answer(visual: Mapping[str, float] | None) -> VisualObservation:
    if visual is None:
        return NO_VISUAL_EVIDENCE
    return VisualObservation(**{name: float(visual[name]) for name in VISUAL_FEATURE_NAMES})


class GameAnswerRecorder:
    """Records one learner-state window per scored game answer and returns its action."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        service: LearnerStateService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._service = service or get_learner_state_service()

    def record_answer(
        self,
        *,
        session_id: UUID,
        learner_id: UUID,
        window_id: int,
        skill_id: str,
        observed_at: datetime,
        correct: bool,
        response_time_ms: int | None,
        supported: bool,
        hint_count: int,
        visual: Mapping[str, float] | None,
    ) -> str | None:
        """
        Evaluate and store the window, and return its `recommended_action`.

        Returns None without recording when the response time is unknown, because both
        behaviour models need it. `supported` is accepted for the game protocol but is not a
        model input. Errors (`UnknownLearnerError`, `WindowOrderError`, an invalid skill id or
        visual value) are logged and raised to the caller.
        """
        if response_time_ms is None:
            return None

        window = LearnerStateWindow(
            session_id=str(session_id),
            learner_id=learner_id,
            window_id=window_id,
            timestamp=observed_at,
            visual=visual_from_game_answer(visual),
            behavior=behaviour_from_game_answer(
                correct=correct,
                response_time_ms=response_time_ms,
                hint_count=hint_count,
            ),
            task_progress=None,
        )

        try:
            with self._session_factory() as session:
                learners = SqlAlchemyLearnerRepository(session)
                recorder = LearnerStateRecorder(
                    service=self._service,
                    learner_exists=lambda candidate: learners.get(candidate) is not None,
                    skill_states=SqlAlchemyLearnerSkillStateRepository(session),
                )
                evaluation = recorder.record(window, skill_id=skill_id)
        except Exception:
            logger.warning(
                "learner-state window %s of game session %s was not recorded",
                window_id,
                session_id,
                exc_info=True,
            )
            raise
        return evaluation.recommended_action

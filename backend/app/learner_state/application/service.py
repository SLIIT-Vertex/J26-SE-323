from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from uuid import UUID

from app.learner_state.domain.confusion import evaluate_confusion_window
from app.learner_state.domain.disengagement import evaluate_disengagement_window
from app.learner_state.infrastructure.feature_builder import (
    HISTORY_WINDOW,
    BehaviorObservation,
    build_confusion_behavior_features,
    build_disengagement_behavior_features,
)
from app.learner_state.infrastructure.model_loader import LearnerStateModels
from app.learner_state.infrastructure.reliability import (
    calculate_behavior_reliability,
    calculate_visual_reliability,
)

TEMPORAL_HISTORY_SIZE = 3


@dataclass(frozen=True)
class VisualObservation:
    mean_eye_openness: float
    std_eye_openness: float
    mean_gaze_ratio: float
    std_gaze_ratio: float
    mean_pitch: float
    mean_yaw: float
    mean_roll: float
    mean_abs_pitch: float
    mean_abs_yaw: float
    mean_abs_roll: float
    face_visibility_ratio: float

    def as_features(self) -> dict[str, float]:
        return {
            "mean_eye_openness": self.mean_eye_openness,
            "std_eye_openness": self.std_eye_openness,
            "mean_gaze_ratio": self.mean_gaze_ratio,
            "std_gaze_ratio": self.std_gaze_ratio,
            "mean_pitch": self.mean_pitch,
            "mean_yaw": self.mean_yaw,
            "mean_roll": self.mean_roll,
            "mean_abs_pitch": self.mean_abs_pitch,
            "mean_abs_yaw": self.mean_abs_yaw,
            "mean_abs_roll": self.mean_abs_roll,
            "face_visibility_ratio": self.face_visibility_ratio,
        }


@dataclass(frozen=True)
class LearnerStateWindow:
    session_id: str
    learner_id: UUID
    window_id: int
    timestamp: datetime
    visual: VisualObservation
    behavior: BehaviorObservation
    task_progress: float | None = None


@dataclass(frozen=True)
class SignalEvaluation:
    visual_probability: float
    behavior_probability: float
    visual_reliability: float
    behavior_reliability: float
    fused_evidence: float
    confidence: float
    state: str
    support_need: str


@dataclass(frozen=True)
class LearnerStateEvaluation:
    session_id: str
    learner_id: UUID
    window_id: int
    confusion: SignalEvaluation
    disengagement: SignalEvaluation
    recommended_action: str


@dataclass
class _SessionState:
    behavior_history: deque[BehaviorObservation] = field(
        default_factory=lambda: deque(maxlen=HISTORY_WINDOW)
    )

    confusion_fused: deque[float] = field(
        default_factory=lambda: deque(maxlen=TEMPORAL_HISTORY_SIZE)
    )
    confusion_confidence: deque[float] = field(
        default_factory=lambda: deque(maxlen=TEMPORAL_HISTORY_SIZE)
    )
    task_progress: deque[float | None] = field(
        default_factory=lambda: deque(maxlen=TEMPORAL_HISTORY_SIZE)
    )

    disengagement_fused: deque[float] = field(
        default_factory=lambda: deque(maxlen=TEMPORAL_HISTORY_SIZE)
    )
    disengagement_confidence: deque[float] = field(
        default_factory=lambda: deque(maxlen=TEMPORAL_HISTORY_SIZE)
    )

    last_window_id: int | None = None


def _choose_recommended_action(
    *,
    confusion_support: str,
    disengagement_support: str,
) -> str:
    # If the learner is persistently disengaged, re-engagement is
    # prioritized before giving additional academic explanations.
    if disengagement_support == "request_reengagement_support":
        return "request_reengagement_support"

    if confusion_support == "request_tutor_support":
        return "request_tutor_support"

    if (
        confusion_support == "collect_more_evidence"
        or disengagement_support == "collect_more_evidence"
    ):
        return "collect_more_evidence"

    if (
        confusion_support == "monitor"
        or disengagement_support == "monitor"
    ):
        return "monitor"

    return "none"


class LearnerStateService:
    """
    Coordinates feature construction, model inference, reliability,
    multimodal fusion and temporal learner-state decisions.

    Session history is currently held in memory. A persistent storage
    implementation can replace this later without changing domain logic.
    """

    def __init__(
        self,
        models: LearnerStateModels | None = None,
    ) -> None:
        self._models = models or LearnerStateModels.load_default()

        self._sessions: dict[
            tuple[str, UUID],
            _SessionState,
        ] = {}

        self._lock = RLock()

    def evaluate(
        self,
        window: LearnerStateWindow,
    ) -> LearnerStateEvaluation:
        session_key = (
            window.session_id,
            window.learner_id,
        )

        with self._lock:
            state = self._sessions.setdefault(
                session_key,
                _SessionState(),
            )

            self._validate_window_order(
                state=state,
                window_id=window.window_id,
            )

            visual_features = window.visual.as_features()

            confusion_behavior_features = (
                build_confusion_behavior_features(
                    window.behavior
                )
            )

            disengagement_behavior_features = (
                build_disengagement_behavior_features(
                    window.behavior,
                    list(state.behavior_history),
                )
            )

            visual_reliability = (
                calculate_visual_reliability(
                    mean_abs_pitch=window.visual.mean_abs_pitch,
                    mean_abs_yaw=window.visual.mean_abs_yaw,
                    mean_abs_roll=window.visual.mean_abs_roll,
                    face_visibility_ratio=(
                        window.visual.face_visibility_ratio
                    ),
                )
            )

            bottom_hint_missing = float(
                confusion_behavior_features[
                    "bottom_hint_missing"
                ]
                or 0.0
            )

            history_confidence = float(
                disengagement_behavior_features[
                    "history_confidence"
                ]
                or 0.0
            )

            behavior_reliability = (
                calculate_behavior_reliability(
                    ms_first_response=(
                        window.behavior.ms_first_response
                    ),
                    overlap_time=window.behavior.overlap_time,
                    bottom_hint_missing=bottom_hint_missing,
                    history_confidence=history_confidence,
                )
            )

            confusion_visual_probability = (
                self._models.predict_confusion_visual(
                    visual_features
                )
            )

            confusion_behavior_probability = (
                self._models.predict_confusion_behavior(
                    confusion_behavior_features
                )
            )

            disengagement_visual_probability = (
                self._models.predict_disengagement_visual(
                    visual_features
                )
            )

            disengagement_behavior_probability = (
                self._models.predict_disengagement_behavior(
                    disengagement_behavior_features
                )
            )

            confusion = evaluate_confusion_window(
                visual_probability=(
                    confusion_visual_probability
                ),
                behavior_probability=(
                    confusion_behavior_probability
                ),
                visual_reliability=(
                    visual_reliability.reliability
                ),
                behavior_reliability=(
                    behavior_reliability.reliability
                ),
                previous_fused_evidence=list(
                    state.confusion_fused
                ),
                previous_fusion_confidence=list(
                    state.confusion_confidence
                ),
                previous_task_progress=list(
                    state.task_progress
                ),
                task_progress=window.task_progress,
            )

            disengagement = evaluate_disengagement_window(
                visual_probability=(
                    disengagement_visual_probability
                ),
                behavior_probability=(
                    disengagement_behavior_probability
                ),
                visual_reliability=(
                    visual_reliability.reliability
                ),
                behavior_reliability=(
                    behavior_reliability.reliability
                ),
                previous_fused_evidence=list(
                    state.disengagement_fused
                ),
                previous_fusion_confidence=list(
                    state.disengagement_confidence
                ),
            )

            recommended_action = _choose_recommended_action(
                confusion_support=confusion.support_need,
                disengagement_support=(
                    disengagement.support_need
                ),
            )

            self._update_history(
                state=state,
                window=window,
                confusion_fused=confusion.fused_evidence,
                confusion_confidence=(
                    confusion.fusion_confidence
                ),
                disengagement_fused=(
                    disengagement.fused_evidence
                ),
                disengagement_confidence=(
                    disengagement.fusion_confidence
                ),
            )

            return LearnerStateEvaluation(
                session_id=window.session_id,
                learner_id=window.learner_id,
                window_id=window.window_id,
                confusion=SignalEvaluation(
                    visual_probability=(
                        confusion_visual_probability
                    ),
                    behavior_probability=(
                        confusion_behavior_probability
                    ),
                    visual_reliability=(
                        visual_reliability.reliability
                    ),
                    behavior_reliability=(
                        behavior_reliability.reliability
                    ),
                    fused_evidence=(
                        confusion.fused_evidence
                    ),
                    confidence=(
                        confusion.fusion_confidence
                    ),
                    state=confusion.state,
                    support_need=confusion.support_need,
                ),
                disengagement=SignalEvaluation(
                    visual_probability=(
                        disengagement_visual_probability
                    ),
                    behavior_probability=(
                        disengagement_behavior_probability
                    ),
                    visual_reliability=(
                        visual_reliability.reliability
                    ),
                    behavior_reliability=(
                        behavior_reliability.reliability
                    ),
                    fused_evidence=(
                        disengagement.fused_evidence
                    ),
                    confidence=(
                        disengagement.fusion_confidence
                    ),
                    state=disengagement.state,
                    support_need=(
                        disengagement.support_need
                    ),
                ),
                recommended_action=recommended_action,
            )

    @staticmethod
    def _validate_window_order(
        *,
        state: _SessionState,
        window_id: int,
    ) -> None:
        if (
            state.last_window_id is not None
            and window_id <= state.last_window_id
        ):
            raise ValueError(
                "window_id must increase within a learner session"
            )

    @staticmethod
    def _update_history(
        *,
        state: _SessionState,
        window: LearnerStateWindow,
        confusion_fused: float,
        confusion_confidence: float,
        disengagement_fused: float,
        disengagement_confidence: float,
    ) -> None:
        state.behavior_history.append(window.behavior)

        state.confusion_fused.append(confusion_fused)
        state.confusion_confidence.append(
            confusion_confidence
        )
        state.task_progress.append(window.task_progress)

        state.disengagement_fused.append(
            disengagement_fused
        )
        state.disengagement_confidence.append(
            disengagement_confidence
        )

        state.last_window_id = window.window_id

    def clear_session(
        self,
        *,
        session_id: str,
        learner_id: UUID,
    ) -> None:
        with self._lock:
            self._sessions.pop(
                (session_id, learner_id),
                None,
            )
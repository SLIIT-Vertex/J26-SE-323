from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.learner_state.application.support_need import SkillId


class VisualFeatures(BaseModel):
    """Derived webcam features for one learner-state window."""

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

    face_visibility_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )


class BehaviourFeatures(BaseModel):
    """Behavioural interaction features for the current learning window."""

    correct: float = Field(
        ge=0.0,
        le=1.0,
    )

    bottom_hint: float | None = None

    hint_count: float = Field(ge=0.0)
    attempt_count: float = Field(ge=0.0)

    ms_first_response: float
    overlap_time: float

    first_action: float
    position: float

    original: float


class LearnerStateRequest(BaseModel):
    """Input received for one synchronized learner-state window."""

    session_id: str = Field(
        min_length=1,
        max_length=100,
    )

    learner_id: UUID

    window_id: int = Field(
        ge=1,
    )

    skill_id: SkillId

    timestamp: datetime

    visual: VisualFeatures

    behaviour: BehaviourFeatures

    task_progress: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

class ConfusionResult(BaseModel):
    visual_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    behavior_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    visual_reliability: float = Field(
        ge=0.0,
        le=1.0,
    )

    behavior_reliability: float = Field(
        ge=0.0,
        le=1.0,
    )

    fused_evidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    temporal_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    average_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    persistent_count: int = Field(
        ge=0,
    )

    state: Literal[
        "no_confusion",
        "transient_confusion",
        "productive_confusion",
        "intervention_worthy_confusion",
        "recovering_from_confusion",
        "uncertain",
    ]

    support_need: Literal[
        "none",
        "monitor",
        "request_tutor_support",
        "collect_more_evidence",
    ]

class DisengagementResult(BaseModel):
    visual_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    behavior_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    visual_reliability: float = Field(
        ge=0.0,
        le=1.0,
    )

    behavior_reliability: float = Field(
        ge=0.0,
        le=1.0,
    )

    fused_evidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    temporal_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    average_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    persistent_count: int = Field(
        ge=0,
    )

    state: Literal[
        "engaged",
        "transient_disengagement",
        "persistent_disengagement",
        "recovering_engagement",
        "uncertain",
    ]

    support_need: Literal[
        "none",
        "monitor",
        "request_reengagement_support",
        "collect_more_evidence",
    ]

class LearnerStateResponse(BaseModel):
    session_id: str
    learner_id: UUID
    window_id: int
    skill_id: str

    confusion: ConfusionResult
    disengagement: DisengagementResult

    recommended_action: Literal[
        "none",
        "monitor",
        "request_tutor_support",
        "request_reengagement_support",
        "collect_more_evidence",
    ]
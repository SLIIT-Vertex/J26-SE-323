"""
Skill-specific support-need contract published by the Learner State module.

Adaptive Tutor needs a normalized 0–1 support need for one learner and
one skill. Learner State stores the latest evaluated state per
(learner_id, skill_id) and exposes it through `SupportNeedProvider`.

Only confusion contributes to this value. Disengagement is about
attention rather than a skill gap and is handled separately through
`request_reengagement_support`.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.learner_state.application.service import LearnerStateEvaluation, SignalEvaluation

SKILL_ID_MAX_LENGTH = 16

SkillId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=SKILL_ID_MAX_LENGTH,
        strict=True,
    ),
]
SupportNeedValue = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]


class SupportNeedStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNCERTAIN = "UNCERTAIN"
    NOT_FOUND = "NOT_FOUND"


class SupportNeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: SkillId


class SupportNeedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: SkillId
    status: SupportNeedStatus
    support_need: SupportNeedValue | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is SupportNeedStatus.AVAILABLE and self.support_need is None:
            raise ValueError("AVAILABLE requires support_need")
        if self.status is not SupportNeedStatus.AVAILABLE and self.support_need is not None:
            raise ValueError("only AVAILABLE may contain support_need")
        if self.status is SupportNeedStatus.NOT_FOUND and self.observed_at is not None:
            raise ValueError("NOT_FOUND cannot contain observed_at")
        if self.status is not SupportNeedStatus.NOT_FOUND and self.observed_at is None:
            raise ValueError("a stored state requires observed_at")
        return self


class SupportNeedProvider(Protocol):
    def get_support_need(self, request: SupportNeedRequest) -> SupportNeedResult: ...


@dataclass(frozen=True)
class LearnerSkillState:
    """Latest learner-state result for one learner and one skill."""

    learner_id: UUID
    skill_id: str
    session_id: str
    window_id: int
    observed_at: datetime
    confusion_state: str
    confusion_support_need: str
    confusion_temporal_score: float
    disengagement_state: str
    disengagement_support_need: str
    recommended_action: str
    support_need: float | None


class LearnerSkillStateRepository(Protocol):
    def save(self, state: LearnerSkillState) -> None: ...

    def get(self, learner_id: UUID, skill_id: str) -> LearnerSkillState | None: ...


def support_need_from_confusion(confusion: SignalEvaluation) -> float | None:
    """
    Map the confusion result to the tutor's 0–1 support need.

    The confusion temporal score is used because it already combines
    recent evidence with fusion confidence. No value is produced while the
    confusion state is uncertain. This mapping is a provisional design
    decision that still requires calibration on synchronized pilot data.
    """

    if confusion.state == "uncertain":
        return None

    return confusion.temporal_score


def skill_state_from_evaluation(
    evaluation: LearnerStateEvaluation,
    *,
    skill_id: str,
    observed_at: datetime,
) -> LearnerSkillState:
    return LearnerSkillState(
        learner_id=evaluation.learner_id,
        skill_id=skill_id,
        session_id=evaluation.session_id,
        window_id=evaluation.window_id,
        observed_at=observed_at,
        confusion_state=evaluation.confusion.state,
        confusion_support_need=evaluation.confusion.support_need,
        confusion_temporal_score=evaluation.confusion.temporal_score,
        disengagement_state=evaluation.disengagement.state,
        disengagement_support_need=evaluation.disengagement.support_need,
        recommended_action=evaluation.recommended_action,
        support_need=support_need_from_confusion(evaluation.confusion),
    )


class StoredSupportNeedProvider:
    """`SupportNeedProvider` backed by the stored latest skill states."""

    def __init__(self, repository: LearnerSkillStateRepository) -> None:
        self._repository = repository

    def get_support_need(self, request: SupportNeedRequest) -> SupportNeedResult:
        state = self._repository.get(request.learner_id, request.skill_id)

        if state is None:
            return SupportNeedResult(
                learner_id=request.learner_id,
                skill_id=request.skill_id,
                status=SupportNeedStatus.NOT_FOUND,
            )

        if state.support_need is None:
            return SupportNeedResult(
                learner_id=request.learner_id,
                skill_id=request.skill_id,
                status=SupportNeedStatus.UNCERTAIN,
                observed_at=state.observed_at,
            )

        return SupportNeedResult(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
            status=SupportNeedStatus.AVAILABLE,
            support_need=state.support_need,
            observed_at=state.observed_at,
        )

from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode

NormalizedValue = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]
AttemptCount = Annotated[int, Field(strict=True, ge=0)]
SkillId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]


class TutoringContext(BaseModel):
    """Inputs available to the Scaffolding Controller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: SkillId
    mastery: NormalizedValue
    support_need: NormalizedValue
    attempt_count: AttemptCount
    is_correct: StrictBool | None
    error_severity: NormalizedValue | None
    previous_assistance_level: AssistanceLevel | None = None
    previous_hint_effective: StrictBool | None = None

    @model_validator(mode="after")
    def validate_relational_fields(self) -> Self:
        if self.attempt_count == 0:
            if self.is_correct is not None or self.error_severity is not None:
                raise ValueError(
                    "is_correct and error_severity must be null when attempt_count is 0"
                )
        elif self.is_correct is None or self.error_severity is None:
            raise ValueError(
                "is_correct and error_severity are required when attempt_count is at least 1"
            )

        if self.previous_assistance_level is None and self.previous_hint_effective is not None:
            raise ValueError(
                "previous_hint_effective requires a previous_assistance_level"
            )
        return self


class AssistanceDecision(BaseModel):
    """Auditable output from the Scaffolding Controller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assistance_level: AssistanceLevel
    reason_codes: tuple[DecisionReasonCode, ...] = Field(min_length=1)

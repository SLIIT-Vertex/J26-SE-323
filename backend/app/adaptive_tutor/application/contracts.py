from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints

from app.adaptive_tutor.domain import AssistanceLevel

NormalizedValue = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]
AttemptCount = Annotated[int, Field(strict=True, ge=0)]
SkillId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]


class TutoringContext(BaseModel):
    """Inputs available to the future Scaffolding Controller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: SkillId
    mastery: NormalizedValue
    support_need: NormalizedValue
    attempt_count: AttemptCount
    is_correct: StrictBool
    error_severity: NormalizedValue
    previous_assistance_level: AssistanceLevel | None = None
    previous_hint_effective: StrictBool | None = None

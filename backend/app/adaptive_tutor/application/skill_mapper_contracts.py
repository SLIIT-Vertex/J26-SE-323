from collections.abc import Collection
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from app.adaptive_tutor.domain import (
    ConversationRole,
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
)

MAX_CONVERSATION_TURNS = 8
MAX_CANDIDATE_SKILLS = 5

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
SkillId = NonBlankText
Confidence = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: ConversationRole
    message: NonBlankText


class SkillMappingRequest(BaseModel):
    """Language-neutral input contract for a future Conversational Skill Mapper."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_message: NonBlankText
    conversation_context: tuple[ConversationTurn, ...] = Field(
        default=(), max_length=MAX_CONVERSATION_TURNS
    )
    active_skill_id: SkillId | None = None
    preferred_language: NonBlankText | None = None


class SkillCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: SkillId
    confidence: Confidence


class SkillMappingResult(BaseModel):
    """Structural output contract; it does not perform semantic skill mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: SkillMappingStatus
    intent: LearningIntent
    skill_id: SkillId | None = None
    confidence: Confidence | None = None
    candidate_skills: tuple[SkillCandidate, ...] = Field(
        default=(), max_length=MAX_CANDIDATE_SKILLS
    )
    clarification_needed: StrictBool
    clarification_question: NonBlankText | None = None
    reason_codes: tuple[SkillMappingReasonCode, ...] = ()

    @model_validator(mode="after")
    def validate_result_state(self) -> Self:
        candidate_ids = [candidate.skill_id for candidate in self.candidate_skills]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate skill IDs must be unique")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason codes must be unique")

        if self.status is SkillMappingStatus.MATCHED:
            if self.skill_id is None or self.confidence is None:
                raise ValueError("MATCHED requires skill_id and confidence")
        elif self.skill_id is not None or self.confidence is not None:
            raise ValueError("only MATCHED may contain a confirmed skill_id and confidence")

        if self.status is SkillMappingStatus.AMBIGUOUS:
            if not self.clarification_needed:
                raise ValueError("AMBIGUOUS requires clarification")
        elif self.clarification_needed:
            raise ValueError("clarification is only valid for AMBIGUOUS results")

        if self.clarification_needed and self.clarification_question is None:
            raise ValueError("clarification_question is required when clarification is needed")
        if not self.clarification_needed and self.clarification_question is not None:
            raise ValueError("clarification_question requires clarification_needed")

        if self.status in {
            SkillMappingStatus.NO_MATCH,
            SkillMappingStatus.NOT_SKILL_RELATED,
        } and self.candidate_skills:
            raise ValueError(f"{self.status} must not contain candidate skills")

        return self


def validate_skill_ids_against_taxonomy(
    contract: SkillMappingRequest | SkillMappingResult,
    valid_skill_ids: Collection[str],
) -> None:
    """Validate referenced IDs against an authoritative taxonomy supplied by the caller."""

    if isinstance(contract, SkillMappingRequest):
        referenced_ids = [contract.active_skill_id] if contract.active_skill_id else []
    else:
        referenced_ids = [
            *([contract.skill_id] if contract.skill_id else []),
            *(candidate.skill_id for candidate in contract.candidate_skills),
        ]

    unknown_ids = sorted(set(referenced_ids) - set(valid_skill_ids))
    if unknown_ids:
        raise ValueError(f"unknown skill IDs: {', '.join(unknown_ids)}")

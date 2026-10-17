from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.adaptive_tutor.application.context_assembly import (
    ContextEvidenceOrigin,
    ContextInput,
    ContextReadinessReason,
    ContextReadinessStatus,
    EvidenceOrigin,
)
from app.adaptive_tutor.application.generation import MAX_CONVERSATION_CHARS, GenerationStatus
from app.adaptive_tutor.application.orchestration import (
    StudentMessage,
    TutorWorkflowRequest,
    TutorWorkflowResult,
    TutorWorkflowStatus,
)
from app.adaptive_tutor.application.skill_mapper_contracts import ConversationTurn
from app.adaptive_tutor.application.verification import (
    VerificationOutcome,
    VerificationReasonCode,
)
from app.adaptive_tutor.domain import (
    AssistanceLevel,
    DecisionReasonCode,
    SkillMappingReasonCode,
    SkillMappingStatus,
)
from app.curriculum.application import CurriculumRetrievalStatus

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
BoundedLanguage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16, strict=True),
]
BoundedSkillId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, strict=True),
]


class TutorApiExecutionMode(StrEnum):
    SYNTHETIC_DEMO = "synthetic-demo"


class TutorApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    student_message: StudentMessage
    response_language: BoundedLanguage
    conversation_context: tuple[ConversationTurn, ...] = Field(default=(), max_length=8)
    active_skill_id: BoundedSkillId | None = None

    @model_validator(mode="after")
    def validate_context_size(self) -> Self:
        if sum(len(turn.message) for turn in self.conversation_context) > MAX_CONVERSATION_CHARS:
            raise ValueError("conversation context is too long")
        return self

    def to_workflow_request(self) -> TutorWorkflowRequest:
        return TutorWorkflowRequest.model_validate(self.model_dump())


class PublicContextProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: ContextInput
    source_id: NonBlankText
    origin: EvidenceOrigin
    status: NonBlankText


class PublicVerificationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    source_version: NonBlankText
    chunk_id: NonBlankText
    page_number: int | None = None


class TutorApiResponse(BaseModel):
    """Safe public projection; generated drafts are never copied into this DTO."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "status": "SIMULATED_VERIFICATION_PASS",
                    "safe_message": (
                        "The offline simulation passed configured checks; no learner response "
                        "is approved."
                    ),
                    "delivery_authorized": False,
                    "execution_mode": "synthetic-demo",
                    "execution_origin": "SYNTHETIC",
                    "demonstration_notice": (
                        "SYNTHETIC RESEARCH DEMONSTRATION — NOT REAL LEARNER DATA OR "
                        "VALIDATED LLM OUTPUT."
                    ),
                    "skill_mapping_status": "MATCHED",
                    "confirmed_skill_id": "MAT-FRC",
                    "context_readiness_status": "READY",
                    "assistance_level": "L0",
                    "generation_status": "DRAFT_GENERATED",
                    "verification_outcome": "PASS",
                    "verification_simulated": True,
                }
            ]
        },
    )

    status: TutorWorkflowStatus
    safe_message: NonBlankText
    response_text: NonBlankText | None = None
    delivery_authorized: bool
    execution_mode: TutorApiExecutionMode
    execution_origin: ContextEvidenceOrigin
    demonstration_notice: NonBlankText
    skill_mapping_status: SkillMappingStatus | None = None
    skill_mapping_reason_codes: tuple[SkillMappingReasonCode, ...] = ()
    confirmed_skill_id: NonBlankText | None = None
    context_readiness_status: ContextReadinessStatus | None = None
    context_issue_codes: tuple[ContextReadinessReason, ...] = ()
    context_provenance: tuple[PublicContextProvenance, ...] = ()
    assistance_level: AssistanceLevel | None = None
    controller_reason_codes: tuple[DecisionReasonCode, ...] = ()
    curriculum_status: CurriculumRetrievalStatus | None = None
    generation_status: GenerationStatus | None = None
    verification_outcome: VerificationOutcome | None = None
    verification_reason_codes: tuple[VerificationReasonCode, ...] = ()
    verification_evidence_provenance: tuple[PublicVerificationProvenance, ...] = ()
    verification_simulated: bool

    @classmethod
    def from_workflow_result(cls, result: TutorWorkflowResult) -> Self:
        if result.demonstration_notice is None:
            raise ValueError("synthetic API results require an explicit demonstration notice")

        context_readiness = None
        if result.context_issues:
            context_readiness = ContextReadinessStatus.NOT_READY
        elif any(
            item.input is not ContextInput.SKILL_MAPPING for item in result.context_provenance
        ):
            context_readiness = ContextReadinessStatus.READY

        return cls(
            status=result.status,
            safe_message=result.safe_message,
            response_text=(
                result.response_text
                if result.status is TutorWorkflowStatus.APPROVED_RESPONSE
                else None
            ),
            delivery_authorized=result.status is TutorWorkflowStatus.APPROVED_RESPONSE,
            execution_mode=TutorApiExecutionMode.SYNTHETIC_DEMO,
            execution_origin=result.execution_origin,
            demonstration_notice=result.demonstration_notice,
            skill_mapping_status=result.skill_mapping_status,
            skill_mapping_reason_codes=result.skill_mapping_reason_codes,
            confirmed_skill_id=result.confirmed_skill_id,
            context_readiness_status=context_readiness,
            context_issue_codes=tuple(issue.reason for issue in result.context_issues),
            context_provenance=tuple(
                PublicContextProvenance(
                    input=item.input,
                    source_id=item.source_id,
                    origin=item.origin,
                    status=item.status,
                )
                for item in result.context_provenance
            ),
            assistance_level=result.assistance_level,
            controller_reason_codes=result.controller_reason_codes,
            curriculum_status=result.curriculum_status,
            generation_status=result.generation_status,
            verification_outcome=result.verification_outcome,
            verification_reason_codes=result.verification_reason_codes,
            verification_evidence_provenance=tuple(
                PublicVerificationProvenance(
                    source_id=item.source_id,
                    source_version=item.source_version,
                    chunk_id=item.chunk_id,
                    page_number=item.page_number,
                )
                for item in result.verification_evidence_provenance
            ),
            verification_simulated=result.verification_simulated,
        )

    @model_validator(mode="after")
    def validate_delivery_boundary(self) -> Self:
        if self.delivery_authorized or self.response_text is not None:
            raise ValueError("synthetic API results cannot authorize learner delivery")
        return self

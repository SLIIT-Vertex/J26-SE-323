from datetime import datetime
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
from app.adaptive_tutor.application.generation import (
    MAX_CONVERSATION_CHARS,
    GenerationStatus,
    ProviderFailureReason,
)
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
from app.adaptive_tutor.infrastructure.demo_sessions import (
    DemoInteraction,
    DemoScenario,
    DemoScenarioId,
    DemoSession,
)
from app.adaptive_tutor.infrastructure.research_sessions import (
    EXPERIMENTAL_CURRICULUM_PROVENANCE,
    EXPERIMENTAL_RESPONSE_NOTICE,
    ExperimentalGenerationStatus,
    ResearchAttemptAnnotation,
    ResearchSession,
    ResearchTurn,
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
    draft_attempt_count: int = 0
    regeneration_reason_codes: tuple[VerificationReasonCode, ...] = ()

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
            draft_attempt_count=result.draft_attempt_count,
            regeneration_reason_codes=result.regeneration_reason_codes,
        )

    @model_validator(mode="after")
    def validate_delivery_boundary(self) -> Self:
        if self.delivery_authorized or self.response_text is not None:
            raise ValueError("synthetic API results cannot authorize learner delivery")
        return self


class DemoScenarioRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: DemoScenarioId
    title: NonBlankText

    @classmethod
    def from_scenario(cls, scenario: DemoScenario) -> Self:
        return cls(scenario_id=scenario.scenario_id, title=scenario.title)


class StartDemoSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: DemoScenarioId


class StartDemoSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    session_token: NonBlankText
    scenario: DemoScenarioRead
    expires_at: datetime
    demonstration_notice: NonBlankText

    @classmethod
    def from_session(cls, session: DemoSession, token: str, notice: str) -> Self:
        return cls(
            session_id=session.session_id,
            session_token=token,
            scenario=DemoScenarioRead.from_scenario(session.scenario),
            expires_at=session.expires_at,
            demonstration_notice=notice,
        )


class SubmitDemoQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    student_message: StudentMessage
    response_language: BoundedLanguage = "en"


class DemoInteractionResponse(TutorApiResponse):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    interaction_id: UUID
    interaction_sequence: int
    occurred_at: datetime
    scenario_id: DemoScenarioId
    demonstration_explanation: NonBlankText | None = None

    @classmethod
    def from_interaction(cls, session: DemoSession, interaction: DemoInteraction) -> Self:
        public = TutorApiResponse.from_workflow_result(interaction.result)
        explanation = (
            session.scenario.example_explanation
            if interaction.result.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS
            else None
        )
        return cls(
            **public.model_dump(),
            session_id=session.session_id,
            interaction_id=interaction.interaction_id,
            interaction_sequence=interaction.sequence,
            occurred_at=interaction.occurred_at,
            scenario_id=session.scenario.scenario_id,
            demonstration_explanation=explanation,
        )


class DemoHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    interactions: tuple[DemoInteractionResponse, ...]


class StartResearchSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID


class ResearchAuthorizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    researcher_authorized: bool = True
    execution_mode: str = "research-local"
    child_delivery_enabled: bool = False
    severity_policy_versions: tuple[str, ...] = ()


class StartResearchSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    session_token: NonBlankText
    learner_id: UUID
    expires_at: datetime
    researcher_authorized: bool = True

    @classmethod
    def from_session(cls, session: ResearchSession, token: str) -> Self:
        return cls(
            session_id=session.session_id,
            session_token=token,
            learner_id=session.learner_id,
            expires_at=session.expires_at,
        )


class ResearchQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    student_message: StudentMessage
    response_language: BoundedLanguage = "en"


class ResearchAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    idempotency_key: NonBlankText
    is_correct: bool
    partial_credit: float | None = Field(default=None, ge=0, le=1)
    severity_category: NonBlankText
    severity_value: float = Field(ge=0, le=1)
    severity_policy_version: NonBlankText
    scoring_version: NonBlankText
    item_rubric_version: NonBlankText
    reviewer_confirmed: bool

    @model_validator(mode="after")
    def validate_correctness_and_severity(self) -> Self:
        if self.is_correct and self.severity_value != 0:
            raise ValueError("a correct attempt requires zero error severity")
        return self

    def to_annotation(self) -> ResearchAttemptAnnotation:
        return ResearchAttemptAnnotation(**self.model_dump())


class ResearchInteractionResponse(BaseModel):
    """Research projection with verified and experimental text kept in separate fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    interaction_id: UUID
    interaction_sequence: int
    status: TutorWorkflowStatus
    safe_message: NonBlankText
    response_text: NonBlankText | None = None
    experimental_response_text: NonBlankText | None = None
    experimental_generation_status: ExperimentalGenerationStatus | None = None
    experimental_provenance: NonBlankText | None = None
    experimental_provider_name: NonBlankText | None = None
    experimental_provider_reason_code: ProviderFailureReason | None = None
    experimental_notice: NonBlankText | None = None
    delivery_authorized: bool
    confirmed_skill_id: NonBlankText | None = None
    skill_mapping_status: SkillMappingStatus | None = None
    skill_mapping_reason_codes: tuple[SkillMappingReasonCode, ...] = ()
    assistance_level: AssistanceLevel | None = None
    controller_reason_codes: tuple[DecisionReasonCode, ...] = ()
    context_issue_codes: tuple[ContextReadinessReason, ...] = ()
    context_provenance: tuple[PublicContextProvenance, ...] = ()
    curriculum_status: CurriculumRetrievalStatus | None = None
    verification_outcome: VerificationOutcome | None = None
    verification_reason_codes: tuple[VerificationReasonCode, ...] = ()
    verification_evidence_provenance: tuple[PublicVerificationProvenance, ...] = ()
    draft_attempt_count: int = 0
    regeneration_reason_codes: tuple[VerificationReasonCode, ...] = ()
    execution_origin: ContextEvidenceOrigin
    assessment_mode: str = "RESEARCHER_REVIEWED_NOT_APPROVED_FOR_LEARNERS"

    @classmethod
    def from_turn(cls, session_id: UUID, turn: ResearchTurn) -> Self:
        result = turn.result
        approved = result.status is TutorWorkflowStatus.APPROVED_RESPONSE
        experimental = turn.experimental_generation
        return cls(
            session_id=session_id,
            interaction_id=turn.interaction_id,
            interaction_sequence=turn.interaction_sequence,
            status=result.status,
            safe_message=result.safe_message,
            response_text=result.response_text if approved else None,
            experimental_response_text=(experimental.text if experimental is not None else None),
            experimental_generation_status=(
                experimental.status if experimental is not None else None
            ),
            experimental_provenance=(
                experimental.provenance if experimental is not None else None
            ),
            experimental_provider_name=(
                experimental.provider_name if experimental is not None else None
            ),
            experimental_provider_reason_code=(
                experimental.provider_reason if experimental is not None else None
            ),
            experimental_notice=(
                EXPERIMENTAL_RESPONSE_NOTICE if experimental is not None else None
            ),
            delivery_authorized=approved,
            confirmed_skill_id=result.confirmed_skill_id,
            skill_mapping_status=result.skill_mapping_status,
            skill_mapping_reason_codes=result.skill_mapping_reason_codes,
            assistance_level=result.assistance_level,
            controller_reason_codes=result.controller_reason_codes,
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
            curriculum_status=result.curriculum_status,
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
            draft_attempt_count=result.draft_attempt_count,
            regeneration_reason_codes=result.regeneration_reason_codes,
            execution_origin=result.execution_origin,
        )

    @model_validator(mode="after")
    def validate_research_delivery(self) -> Self:
        approved = self.status is TutorWorkflowStatus.APPROVED_RESPONSE
        if self.delivery_authorized != approved or (self.response_text is not None) != approved:
            raise ValueError("research text requires a genuine approved workflow response")
        generated = self.experimental_generation_status is ExperimentalGenerationStatus.GENERATED
        if generated != (self.experimental_response_text is not None):
            raise ValueError("only successful experimental generation may expose a draft")
        if self.experimental_response_text is not None and (
            self.delivery_authorized
            or self.experimental_generation_status is not ExperimentalGenerationStatus.GENERATED
            or self.experimental_provenance != EXPERIMENTAL_CURRICULUM_PROVENANCE
            or self.experimental_notice != EXPERIMENTAL_RESPONSE_NOTICE
        ):
            raise ValueError("experimental text requires isolated unverified provenance")
        if self.experimental_generation_status is not None and (
            self.experimental_provenance != EXPERIMENTAL_CURRICULUM_PROVENANCE
            or self.experimental_notice != EXPERIMENTAL_RESPONSE_NOTICE
            or self.experimental_provider_name is None
        ):
            raise ValueError("experimental generation requires labelled provenance")
        if generated and self.experimental_provider_reason_code is not None:
            raise ValueError("successful experimental generation has no failure reason")
        if self.experimental_generation_status is None and any(
            value is not None
            for value in (
                self.experimental_provenance,
                self.experimental_provider_name,
                self.experimental_provider_reason_code,
                self.experimental_notice,
            )
        ):
            raise ValueError("experimental labels require an experimental generation result")
        return self

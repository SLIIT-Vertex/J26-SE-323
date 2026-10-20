from collections.abc import Collection, Mapping
from enum import StrEnum
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.adaptive_tutor.application.context_assembly import (
    ContextAssemblyResult,
    ContextEvidenceOrigin,
    ContextEvidenceProvenance,
    ContextIssue,
    ContextReadinessStatus,
    EvidenceOrigin,
    EvidenceSource,
    TutorContextAssembler,
    TutorContextAssemblyRequest,
)
from app.adaptive_tutor.application.contracts import AssistanceDecision
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.application.curriculum_retrieval import curriculum_request_for_mapping
from app.adaptive_tutor.application.generation import (
    MAX_CONVERSATION_CHARS,
    SUPPORTED_RESPONSE_LANGUAGES,
    DeterministicFakeLlmProvider,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    LlmProvider,
    generate_tutor_draft,
)
from app.adaptive_tutor.application.skill_mapper_contracts import (
    ConversationTurn,
    SkillMappingRequest,
    SkillMappingResult,
    validate_skill_ids_against_taxonomy,
)
from app.adaptive_tutor.application.verification import (
    DeterministicFakeSemanticVerifier,
    EvidenceProvenance,
    SemanticVerifier,
    TrustedAnswerReference,
    VerificationCheckName,
    VerificationOutcome,
    VerificationReasonCode,
    VerificationResult,
    verify_generation_result,
)
from app.adaptive_tutor.domain import (
    AssistanceLevel,
    DecisionReasonCode,
    SkillMappingReasonCode,
    SkillMappingStatus,
)
from app.curriculum.application import (
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumRetriever,
    Grade,
    RetrievedCurriculumPassage,
    validate_retrieval_result_for_request,
)

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
StudentMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000, strict=True),
]
SYNTHETIC_DEMO_NOTICE = (
    "SYNTHETIC RESEARCH DEMONSTRATION — NOT REAL LEARNER DATA OR VALIDATED LLM OUTPUT."
)


class TutorWorkflowStatus(StrEnum):
    APPROVED_RESPONSE = "APPROVED_RESPONSE"
    SIMULATED_VERIFICATION_PASS = "SIMULATED_VERIFICATION_PASS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    NOT_SKILL_RELATED = "NOT_SKILL_RELATED"
    NO_SUPPORTED_SKILL = "NO_SUPPORTED_SKILL"
    CONTEXT_NOT_READY = "CONTEXT_NOT_READY"
    CURRICULUM_UNAVAILABLE = "CURRICULUM_UNAVAILABLE"
    GENERATION_FAILED = "GENERATION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_INDETERMINATE = "VERIFICATION_INDETERMINATE"
    DELIVERY_NOT_AUTHORIZED = "DELIVERY_NOT_AUTHORIZED"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    INVALID_REQUEST = "INVALID_REQUEST"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"


class TutorWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    student_message: StudentMessage
    response_language: NonBlankText
    conversation_context: tuple[ConversationTurn, ...] = Field(default=(), max_length=8)
    active_skill_id: NonBlankText | None = None
    session_id: UUID | None = None
    interaction_id: NonBlankText | None = None
    interaction_sequence: int | None = Field(default=None, strict=True, ge=1)
    as_of: AwareDatetime | None = None
    max_age_ms: int | None = Field(default=None, strict=True, ge=0)
    trusted_skill_mapping: SkillMappingResult | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_context_size(self) -> Self:
        if sum(len(turn.message) for turn in self.conversation_context) > MAX_CONVERSATION_CHARS:
            raise ValueError("conversation context is too long")
        return self


class SkillMapper(Protocol):
    def map(self, request: SkillMappingRequest) -> SkillMappingResult: ...


class TrustedAnswerProvider(Protocol):
    def get_trusted_answer(
        self,
        *,
        student_question: str,
        skill_id: str,
        grade: Grade,
    ) -> TrustedAnswerReference | None: ...


class TutorWorkflowResult(BaseModel):
    """Safe workflow result; rejected drafts are intentionally absent from this contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: TutorWorkflowStatus
    safe_message: NonBlankText
    response_text: NonBlankText | None = None
    skill_mapping_status: SkillMappingStatus | None = None
    skill_mapping_reason_codes: tuple[SkillMappingReasonCode, ...] = ()
    confirmed_skill_id: NonBlankText | None = None
    assistance_level: AssistanceLevel | None = None
    controller_reason_codes: tuple[DecisionReasonCode, ...] = ()
    context_issues: tuple[ContextIssue, ...] = ()
    context_provenance: tuple[ContextEvidenceProvenance, ...] = ()
    curriculum_status: CurriculumRetrievalStatus | None = None
    generation_status: GenerationStatus | None = None
    generation_provider_name: NonBlankText | None = None
    draft_attempt_count: int = Field(default=0, strict=True, ge=0, le=3)
    regeneration_reason_codes: tuple[VerificationReasonCode, ...] = ()
    verification_outcome: VerificationOutcome | None = None
    verification_reason_codes: tuple[VerificationReasonCode, ...] = ()
    verification_evidence_provenance: tuple[EvidenceProvenance, ...] = ()
    semantic_verifier_name: NonBlankText | None = None
    verification_simulated: StrictBool = False
    execution_origin: ContextEvidenceOrigin
    demonstration_notice: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_delivery_boundary(self) -> Self:
        if self.status is TutorWorkflowStatus.APPROVED_RESPONSE:
            if (
                self.response_text is None
                or self.verification_outcome is not VerificationOutcome.PASS
                or self.verification_simulated
                or self.execution_origin is not ContextEvidenceOrigin.REAL
            ):
                raise ValueError("approved response requires a genuine real-evidence PASS")
        elif self.response_text is not None:
            raise ValueError("only APPROVED_RESPONSE may expose response text")

        if self.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS and (
            self.verification_outcome is not VerificationOutcome.PASS
            or (
                not self.verification_simulated
                and self.execution_origin is ContextEvidenceOrigin.REAL
            )
        ):
            raise ValueError("simulated pass requires a simulated verification PASS")

        requires_notice = (
            self.execution_origin is not ContextEvidenceOrigin.REAL or self.verification_simulated
        )
        if requires_notice and self.demonstration_notice != SYNTHETIC_DEMO_NOTICE:
            raise ValueError("synthetic or simulated results require the demonstration notice")
        if not requires_notice and self.demonstration_notice is not None:
            raise ValueError("real results must not contain a synthetic demonstration notice")
        return self


class TutorOrchestrator:
    """Connect existing application boundaries without changing their decisions."""

    def __init__(
        self,
        *,
        skill_mapper: SkillMapper,
        skill_mapper_source: EvidenceSource,
        context_assembler: TutorContextAssembler,
        controller: ScaffoldingController,
        llm_provider: LlmProvider,
        valid_skill_ids: Collection[str],
        curriculum_retriever: CurriculumRetriever | None = None,
        semantic_verifier: SemanticVerifier | None = None,
        trusted_answer_provider: TrustedAnswerProvider | None = None,
        semantic_verifier_is_simulated: bool = False,
        authorized_generation_providers: Collection[str] = (),
        max_regeneration_attempts: int = 2,
        decision_only: bool = False,
    ) -> None:
        self._skill_mapper = skill_mapper
        self._skill_mapper_source = skill_mapper_source
        self._context_assembler = context_assembler
        self._controller = controller
        self._llm_provider = llm_provider
        self._valid_skill_ids = frozenset(valid_skill_ids)
        self._curriculum_retriever = curriculum_retriever
        self._semantic_verifier = semantic_verifier
        self._trusted_answer_provider = trusted_answer_provider
        self._semantic_verifier_is_simulated = semantic_verifier_is_simulated or isinstance(
            semantic_verifier, DeterministicFakeSemanticVerifier
        )
        self._authorized_generation_providers = frozenset(authorized_generation_providers)
        self._decision_only = decision_only
        if isinstance(max_regeneration_attempts, bool) or not 0 <= max_regeneration_attempts <= 2:
            raise ValueError("max_regeneration_attempts must be between zero and two")
        self._max_regeneration_attempts = max_regeneration_attempts
        if not self._valid_skill_ids:
            raise ValueError("valid_skill_ids must not be empty")

    def run(
        self,
        request: TutorWorkflowRequest | Mapping[str, object],
    ) -> TutorWorkflowResult:
        try:
            workflow_request = (
                request
                if isinstance(request, TutorWorkflowRequest)
                else TutorWorkflowRequest.model_validate(request)
            )
        except ValidationError:
            return self._result(
                TutorWorkflowStatus.INVALID_REQUEST,
                "The tutoring request is invalid.",
            )

        if workflow_request.response_language not in SUPPORTED_RESPONSE_LANGUAGES:
            return self._result(
                TutorWorkflowStatus.UNSUPPORTED_LANGUAGE,
                "The requested response language is not supported.",
            )

        mapping_request = SkillMappingRequest(
            learner_message=workflow_request.student_message,
            conversation_context=workflow_request.conversation_context,
            active_skill_id=workflow_request.active_skill_id,
            preferred_language=workflow_request.response_language,
        )
        try:
            validate_skill_ids_against_taxonomy(mapping_request, self._valid_skill_ids)
        except ValueError:
            return self._result(
                TutorWorkflowStatus.INVALID_REQUEST,
                "The active skill reference is not in the authoritative taxonomy.",
            )
        try:
            raw_mapping = workflow_request.trusted_skill_mapping
            if raw_mapping is None:
                raw_mapping = self._skill_mapper.map(mapping_request)
            mapping = SkillMappingResult.model_validate(
                raw_mapping.model_dump() if isinstance(raw_mapping, BaseModel) else raw_mapping,
                from_attributes=True,
            )
            validate_skill_ids_against_taxonomy(mapping, self._valid_skill_ids)
        except Exception:  # noqa: BLE001 - dependency boundary fails closed
            return self._result(
                TutorWorkflowStatus.DEPENDENCY_FAILURE,
                "Skill mapping is currently unavailable.",
            )

        non_match_status = {
            SkillMappingStatus.AMBIGUOUS: TutorWorkflowStatus.CLARIFICATION_REQUIRED,
            SkillMappingStatus.NO_MATCH: TutorWorkflowStatus.NO_SUPPORTED_SKILL,
            SkillMappingStatus.NOT_SKILL_RELATED: TutorWorkflowStatus.NOT_SKILL_RELATED,
        }.get(mapping.status)
        if non_match_status is not None:
            return self._result(
                non_match_status,
                {
                    TutorWorkflowStatus.CLARIFICATION_REQUIRED: (
                        mapping.clarification_question or "Please clarify the learning topic."
                    ),
                    TutorWorkflowStatus.NO_SUPPORTED_SKILL: (
                        "No supported curriculum skill could be confirmed."
                    ),
                    TutorWorkflowStatus.NOT_SKILL_RELATED: (
                        "The message is not related to a supported learning skill."
                    ),
                }[non_match_status],
                mapping=mapping,
            )

        try:
            context_result = self._context_assembler.assemble(
                TutorContextAssemblyRequest(
                    learner_id=workflow_request.learner_id,
                    skill_mapping=mapping,
                    skill_mapping_source=self._skill_mapper_source,
                    session_id=(
                        str(workflow_request.session_id)
                        if workflow_request.session_id is not None
                        else None
                    ),
                    interaction_id=workflow_request.interaction_id,
                    interaction_sequence=workflow_request.interaction_sequence,
                    as_of=workflow_request.as_of,
                    max_age_ms=workflow_request.max_age_ms,
                )
            )
        except Exception:  # noqa: BLE001 - dependency boundary fails closed
            return self._result(
                TutorWorkflowStatus.DEPENDENCY_FAILURE,
                "Context assembly is currently unavailable.",
                mapping=mapping,
            )

        if context_result.status is ContextReadinessStatus.NOT_READY:
            return self._result(
                TutorWorkflowStatus.CONTEXT_NOT_READY,
                "Required learner evidence is not ready.",
                mapping=mapping,
                context_result=context_result,
            )

        assert context_result.context is not None
        assert context_result.learner_grade is not None
        try:
            decision = self._controller.decide(context_result.context)
        except Exception:  # noqa: BLE001 - controller boundary fails closed
            return self._result(
                TutorWorkflowStatus.DEPENDENCY_FAILURE,
                "The assistance decision could not be completed.",
                mapping=mapping,
                context_result=context_result,
            )

        if self._decision_only:
            return self._result(
                TutorWorkflowStatus.DELIVERY_NOT_AUTHORIZED,
                "The Controller decision is available for local experimental generation only.",
                mapping=mapping,
                context_result=context_result,
                decision=decision,
            )

        curriculum_status, evidence = self._retrieve_curriculum(
            workflow_request,
            mapping,
            context_result.learner_grade,
        )
        if decision.assistance_level is AssistanceLevel.FULL_EXPLANATION and not evidence:
            return self._result(
                TutorWorkflowStatus.CURRICULUM_UNAVAILABLE,
                "Approved curriculum evidence is required for a full explanation.",
                mapping=mapping,
                context_result=context_result,
                decision=decision,
                curriculum_status=curriculum_status,
            )

        try:
            generation_request = GenerationRequest(
                student_question=workflow_request.student_message,
                skill_id=mapping.skill_id,
                assistance_level=decision.assistance_level,
                response_language=workflow_request.response_language,
                grade=context_result.learner_grade,
                curriculum_evidence=evidence,
                conversation_context=workflow_request.conversation_context,
            )
        except Exception:  # noqa: BLE001 - generation boundary fails closed
            return self._result(
                TutorWorkflowStatus.GENERATION_FAILED,
                "Response generation failed safely.",
                mapping=mapping,
                context_result=context_result,
                decision=decision,
                curriculum_status=curriculum_status,
            )

        try:
            trusted_answer = self._trusted_answer(
                workflow_request,
                mapping.skill_id,
                context_result.learner_grade,
            )
        except Exception:  # noqa: BLE001 - verification boundary fails closed
            return self._result(
                TutorWorkflowStatus.DEPENDENCY_FAILURE,
                "Response verification is currently unavailable.",
                mapping=mapping,
                context_result=context_result,
                decision=decision,
                curriculum_status=curriculum_status,
            )

        regeneration_codes: list[VerificationReasonCode] = []
        generation: GenerationResult | None = None
        verification: VerificationResult | None = None
        draft_attempt_count = 0
        for attempt in range(1, self._max_regeneration_attempts + 2):
            if attempt > 1:
                generation_request = GenerationRequest(
                    student_question=generation_request.student_question,
                    skill_id=generation_request.skill_id,
                    assistance_level=generation_request.assistance_level,
                    response_language=generation_request.response_language,
                    grade=generation_request.grade,
                    curriculum_evidence=generation_request.curriculum_evidence,
                    conversation_context=generation_request.conversation_context,
                    draft_attempt=attempt,
                    revision_reason_codes=tuple(
                        code.value for code in dict.fromkeys(regeneration_codes)
                    ),
                )
            try:
                generation = generate_tutor_draft(generation_request, self._llm_provider)
            except Exception:  # noqa: BLE001 - generation boundary fails closed
                return self._result(
                    TutorWorkflowStatus.GENERATION_FAILED,
                    "Response generation failed safely.",
                    mapping=mapping,
                    context_result=context_result,
                    decision=decision,
                    curriculum_status=curriculum_status,
                    draft_attempt_count=attempt,
                    regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
                )
            draft_attempt_count = attempt
            if generation.status is not GenerationStatus.DRAFT_GENERATED:
                status = (
                    TutorWorkflowStatus.CURRICULUM_UNAVAILABLE
                    if generation.status is GenerationStatus.INSUFFICIENT_CURRICULUM_EVIDENCE
                    else TutorWorkflowStatus.GENERATION_FAILED
                )
                return self._result(
                    status,
                    "No generated response is eligible for delivery.",
                    mapping=mapping,
                    context_result=context_result,
                    decision=decision,
                    curriculum_status=curriculum_status,
                    generation=generation,
                    draft_attempt_count=draft_attempt_count,
                    regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
                )
            try:
                verification = verify_generation_result(
                    generation_request,
                    generation,
                    trusted_answer=trusted_answer,
                    semantic_verifier=self._semantic_verifier,
                )
            except Exception:  # noqa: BLE001 - verification boundary fails closed
                return self._result(
                    TutorWorkflowStatus.DEPENDENCY_FAILURE,
                    "Response verification is currently unavailable.",
                    mapping=mapping,
                    context_result=context_result,
                    decision=decision,
                    curriculum_status=curriculum_status,
                    generation=generation,
                    draft_attempt_count=draft_attempt_count,
                    regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
                )
            if verification.outcome is VerificationOutcome.PASS:
                break
            if attempt <= self._max_regeneration_attempts and _is_retryable_verification_failure(
                verification
            ):
                regeneration_codes.extend(_retry_reason_codes(verification))
                continue
            status = (
                TutorWorkflowStatus.VERIFICATION_FAILED
                if verification.outcome is VerificationOutcome.FAIL
                else TutorWorkflowStatus.VERIFICATION_INDETERMINATE
            )
            return self._result(
                status,
                (
                    "The generated response did not pass verification."
                    if status is TutorWorkflowStatus.VERIFICATION_FAILED
                    else "The generated response could not be verified with sufficient evidence."
                ),
                mapping=mapping,
                context_result=context_result,
                decision=decision,
                curriculum_status=curriculum_status,
                generation=generation,
                verification=verification,
                draft_attempt_count=draft_attempt_count,
                regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
            )

        assert generation is not None
        assert verification is not None

        execution_origin = self._execution_origin(
            context_result,
            generation_used=True,
            verification_used=True,
        )
        if (
            self._semantic_verifier_is_simulated
            or execution_origin is not ContextEvidenceOrigin.REAL
        ):
            return self._result(
                TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS,
                "The offline simulation passed configured checks; no learner response is approved.",
                mapping=mapping,
                context_result=context_result,
                decision=decision,
                curriculum_status=curriculum_status,
                generation=generation,
                verification=verification,
                draft_attempt_count=draft_attempt_count,
                regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
            )

        if (
            generation.provider_name == "google-gemini"
            and generation.provider_name not in self._authorized_generation_providers
        ):
            return self._result(
                TutorWorkflowStatus.DELIVERY_NOT_AUTHORIZED,
                "The configured generation provider is not authorized for this delivery path.",
                mapping=mapping,
                context_result=context_result,
                decision=decision,
                curriculum_status=curriculum_status,
                generation=generation,
                verification=verification,
                draft_attempt_count=draft_attempt_count,
                regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
            )

        assert generation.draft_text is not None
        return self._result(
            TutorWorkflowStatus.APPROVED_RESPONSE,
            "The response passed all required verification checks.",
            response_text=generation.draft_text,
            mapping=mapping,
            context_result=context_result,
            decision=decision,
            curriculum_status=curriculum_status,
            generation=generation,
            verification=verification,
            draft_attempt_count=draft_attempt_count,
            regeneration_reason_codes=tuple(dict.fromkeys(regeneration_codes)),
        )

    def _retrieve_curriculum(
        self,
        request: TutorWorkflowRequest,
        mapping: SkillMappingResult,
        grade: Grade,
    ) -> tuple[
        CurriculumRetrievalStatus | None,
        tuple[RetrievedCurriculumPassage, ...],
    ]:
        if self._curriculum_retriever is None:
            return None, ()
        retrieval_request = curriculum_request_for_mapping(
            request.student_message,
            mapping,
            grade,
            self._valid_skill_ids,
            requested_language=request.response_language,
        )
        assert retrieval_request is not None
        try:
            raw_result = self._curriculum_retriever.retrieve(retrieval_request)
            result = CurriculumRetrievalResult.model_validate(
                raw_result.model_dump() if isinstance(raw_result, BaseModel) else raw_result,
                from_attributes=True,
            )
            validate_retrieval_result_for_request(retrieval_request, result)
        except Exception:  # noqa: BLE001 - optional retrieval fails closed
            return CurriculumRetrievalStatus.PROVIDER_ERROR, ()
        return result.status, result.passages

    def _trusted_answer(
        self,
        request: TutorWorkflowRequest,
        skill_id: str | None,
        grade: Grade,
    ) -> TrustedAnswerReference | None:
        if self._trusted_answer_provider is None or skill_id is None:
            return None
        answer = self._trusted_answer_provider.get_trusted_answer(
            student_question=request.student_message,
            skill_id=skill_id,
            grade=grade,
        )
        if answer is None:
            return None
        return TrustedAnswerReference.model_validate(
            answer.model_dump() if isinstance(answer, BaseModel) else answer,
            from_attributes=True,
        )

    def _execution_origin(
        self,
        context_result: ContextAssemblyResult | None = None,
        *,
        generation_used: bool = False,
        verification_used: bool = False,
    ) -> ContextEvidenceOrigin:
        origins = {self._skill_mapper_source.origin}
        if context_result is not None:
            origins.update(item.origin for item in context_result.provenance)
        if generation_used and isinstance(self._llm_provider, DeterministicFakeLlmProvider):
            origins.add(EvidenceOrigin.SYNTHETIC)
        if verification_used and isinstance(
            self._semantic_verifier, DeterministicFakeSemanticVerifier
        ):
            origins.add(EvidenceOrigin.SYNTHETIC)
        if origins == {EvidenceOrigin.REAL}:
            return ContextEvidenceOrigin.REAL
        if origins == {EvidenceOrigin.SYNTHETIC}:
            return ContextEvidenceOrigin.SYNTHETIC
        return ContextEvidenceOrigin.MIXED

    def _result(
        self,
        status: TutorWorkflowStatus,
        safe_message: str,
        *,
        response_text: str | None = None,
        mapping: SkillMappingResult | None = None,
        context_result: ContextAssemblyResult | None = None,
        decision: AssistanceDecision | None = None,
        curriculum_status: CurriculumRetrievalStatus | None = None,
        generation: GenerationResult | None = None,
        verification: VerificationResult | None = None,
        draft_attempt_count: int = 0,
        regeneration_reason_codes: tuple[VerificationReasonCode, ...] = (),
    ) -> TutorWorkflowResult:
        execution_origin = self._execution_origin(
            context_result,
            generation_used=generation is not None,
            verification_used=verification is not None,
        )
        verification_simulated = verification is not None and self._semantic_verifier_is_simulated
        return TutorWorkflowResult(
            status=status,
            safe_message=safe_message,
            response_text=response_text,
            skill_mapping_status=mapping.status if mapping else None,
            skill_mapping_reason_codes=mapping.reason_codes if mapping else (),
            confirmed_skill_id=mapping.skill_id if mapping else None,
            assistance_level=decision.assistance_level if decision else None,
            controller_reason_codes=decision.reason_codes if decision else (),
            context_issues=context_result.issues if context_result else (),
            context_provenance=context_result.provenance if context_result else (),
            curriculum_status=curriculum_status,
            generation_status=generation.status if generation else None,
            generation_provider_name=generation.provider_name if generation else None,
            draft_attempt_count=draft_attempt_count,
            regeneration_reason_codes=regeneration_reason_codes,
            verification_outcome=verification.outcome if verification else None,
            verification_reason_codes=verification.reason_codes if verification else (),
            verification_evidence_provenance=(
                verification.evidence_provenance if verification else ()
            ),
            semantic_verifier_name=verification.semantic_verifier_name if verification else None,
            verification_simulated=verification_simulated,
            execution_origin=execution_origin,
            demonstration_notice=(
                SYNTHETIC_DEMO_NOTICE
                if execution_origin is not ContextEvidenceOrigin.REAL or verification_simulated
                else None
            ),
        )


_RETRYABLE_VERIFICATION_CHECKS = frozenset(
    {
        VerificationCheckName.RESPONSE_STRUCTURE,
        VerificationCheckName.LEVEL_STRUCTURE,
        VerificationCheckName.ANSWER_LEAKAGE,
        VerificationCheckName.LANGUAGE_SCRIPT,
        VerificationCheckName.CURRICULUM_CITATIONS,
        VerificationCheckName.SEMANTIC_LEVEL_COMPLIANCE,
        VerificationCheckName.SEMANTIC_ANSWER_LEAKAGE,
        VerificationCheckName.SEMANTIC_FACTUAL_SUPPORT,
        VerificationCheckName.SEMANTIC_LANGUAGE,
        VerificationCheckName.SEMANTIC_AGE_APPROPRIATENESS,
    }
)


def _is_retryable_verification_failure(result: VerificationResult) -> bool:
    failed_checks = {
        check.check
        for check in result.checks
        if check.outcome.value == VerificationOutcome.FAIL.value
    }
    return (
        result.outcome is VerificationOutcome.FAIL
        and bool(failed_checks)
        and failed_checks <= _RETRYABLE_VERIFICATION_CHECKS
    )


def _retry_reason_codes(result: VerificationResult) -> tuple[VerificationReasonCode, ...]:
    return tuple(
        dict.fromkeys(
            code
            for check in result.checks
            if check.outcome.value == VerificationOutcome.FAIL.value
            for code in check.reason_codes
        )
    )

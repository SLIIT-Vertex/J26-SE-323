import inspect
import socket
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from app.adaptive_tutor.application import (
    AssessmentEvidenceResult,
    AssistanceHistoryResult,
    ContextEvidenceOrigin,
    ContextReadinessReason,
    DeterministicFakeLlmProvider,
    DeterministicFakeSemanticVerifier,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    ScaffoldingController,
    SemanticVerificationResult,
    SkillMappingResult,
    SupportNeedResult,
    TrustedAnswerReference,
    TutorContextAssembler,
    TutorOrchestrator,
    TutorWorkflowRequest,
    TutorWorkflowStatus,
    VerificationCheckOutcome,
    VerificationOutcome,
)
from app.adaptive_tutor.application.context_assembly import ContextEvidenceRequest
from app.adaptive_tutor.application.generation import (
    GenerationPrompt,
    LlmProviderError,
)
from app.adaptive_tutor.application.orchestration import SYNTHETIC_DEMO_NOTICE
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingRequest
from app.adaptive_tutor.application.verification import VerificationRequest
from app.adaptive_tutor.domain import (
    AssistanceLevel,
    LearningIntent,
    SkillMappingStatus,
)
from app.adaptive_tutor.infrastructure import (
    SyntheticFixtureMode,
    SyntheticTutorContextFixture,
)
from app.curriculum.application import (
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
)
from app.knowledge_tracing.application import (
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
)

VALID_SKILLS = {"MAT-FRC", "MAT-OPS", "MAT-TIM", "APT-LOG"}

RESPONSES = {
    AssistanceLevel.INDEPENDENT_RETRY: "Try the problem once yourself.",
    AssistanceLevel.METACOGNITIVE_PROMPT: "What strategy could you try first?",
    AssistanceLevel.CONCEPTUAL_HINT: "Think about the main idea behind this problem.",
    AssistanceLevel.TARGETED_HINT: "Start with the next useful step, then pause.",
    AssistanceLevel.GUIDED_STEPS: "Begin with one step. What should you do next?",
    AssistanceLevel.SIMILAR_WORKED_EXAMPLE: (
        "For a different example, two groups of three make six. Now try your problem."
    ),
    AssistanceLevel.FULL_EXPLANATION: (
        "Use the approved idea to work through each part carefully and explain the result."
    ),
}


@dataclass
class FixedMapper:
    result: SkillMappingResult
    error: bool = False
    calls: int = 0

    def map(self, request: SkillMappingRequest) -> SkillMappingResult:
        self.calls += 1
        if self.error:
            raise RuntimeError("private mapper failure")
        return self.result


@dataclass
class CountingController:
    delegate: ScaffoldingController
    calls: int = 0

    def decide(self, context: object) -> object:
        self.calls += 1
        return self.delegate.decide(context)


@dataclass
class FailingController:
    calls: int = 0

    def decide(self, context: object) -> object:
        self.calls += 1
        raise RuntimeError("private controller failure")


@dataclass
class FixedAnswerProvider:
    answer: TrustedAnswerReference | None = field(
        default_factory=lambda: TrustedAnswerReference(
            accepted_answers=("999",),
            provenance="synthetic test answer",
        )
    )

    def get_trusted_answer(
        self,
        *,
        student_question: str,
        skill_id: str,
        grade: int,
    ) -> TrustedAnswerReference | None:
        return self.answer


@dataclass
class FixedCurriculumRetriever:
    status: CurriculumRetrievalStatus = CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES
    error: bool = False
    calls: int = 0

    def retrieve(self, request: CurriculumRetrievalRequest) -> CurriculumRetrievalResult:
        self.calls += 1
        if self.error:
            raise RuntimeError("private curriculum failure")
        passages = (
            (approved_passage(request),) if self.status is CurriculumRetrievalStatus.FOUND else ()
        )
        return CurriculumRetrievalResult(status=self.status, passages=passages)


@dataclass
class RecordingLlm:
    response: str
    name: str = "synthetic-recording-llm"
    calls: int = 0

    def generate(self, prompt: GenerationPrompt) -> str:
        self.calls += 1
        return self.response


@dataclass
class SequenceLlm:
    responses: list[str | Exception]
    name: str = "synthetic-sequence-llm"
    calls: int = 0
    prompts: list[GenerationPrompt] = field(default_factory=list)

    def generate(self, prompt: GenerationPrompt) -> str:
        self.prompts.append(prompt)
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


@dataclass
class FailingLlm:
    unexpected: bool = False
    name: str = "synthetic-failing-llm"

    def generate(self, prompt: GenerationPrompt) -> str:
        if self.unexpected:
            raise RuntimeError("private unexpected generation failure")
        raise LlmProviderError("private expected generation failure")


@dataclass
class ExplodingSemanticVerifier:
    name: str = "synthetic-exploding-verifier"

    def verify(self, request: VerificationRequest) -> SemanticVerificationResult:
        raise RuntimeError("private semantic failure")


@dataclass
class PassingSemanticVerifier:
    name: str = "test-passing-semantic-verifier"

    def verify(self, request: VerificationRequest) -> SemanticVerificationResult:
        return semantic_result()


@dataclass
class ContextProviders:
    fixture: SyntheticTutorContextFixture
    missing: str | None = None
    error: str | None = None
    source: EvidenceSource = field(
        default_factory=lambda: EvidenceSource(
            source_id="synthetic:context-provider-overrides",
            origin=EvidenceOrigin.SYNTHETIC,
        )
    )

    def get_learner(self, learner_id: object) -> LearnerLookupResult:
        self._raise_if("learner")
        if self.missing == "learner":
            return LearnerLookupResult(status=EvidenceStatus.NOT_FOUND)
        return self.fixture.get_learner(learner_id)

    def get_mastery(self, request: MasteryRetrievalRequest) -> MasteryResult:
        self._raise_if("mastery")
        if self.missing == "mastery":
            return MasteryResult(
                learner_id=request.learner_id,
                skill_id=request.skill_id,
                status=MasteryStatus.NOT_FOUND,
            )
        return self.fixture.get_mastery(request)

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        self._raise_if("support")
        if self.missing == "support":
            return SupportNeedResult(status=EvidenceStatus.NOT_YET_OBSERVED)
        return self.fixture.get_support_need(request)

    def get_assessment_evidence(self, request: ContextEvidenceRequest) -> AssessmentEvidenceResult:
        self._raise_if("assessment")
        if self.missing == "assessment":
            return AssessmentEvidenceResult(status=EvidenceStatus.NOT_FOUND)
        return self.fixture.get_assessment_evidence(request)

    def get_assistance_history(self, request: ContextEvidenceRequest) -> AssistanceHistoryResult:
        self._raise_if("history")
        if self.missing == "history":
            return AssistanceHistoryResult(status=EvidenceStatus.NOT_FOUND)
        return self.fixture.get_assistance_history(request)

    def _raise_if(self, provider: str) -> None:
        if self.error == provider:
            raise RuntimeError("private context provider failure")


def semantic_result(
    outcome: VerificationCheckOutcome = VerificationCheckOutcome.PASS,
) -> SemanticVerificationResult:
    return SemanticVerificationResult(
        assistance_level_compliance=outcome,
        answer_leakage=outcome,
        factual_support=outcome,
        language_appropriateness=outcome,
        age_appropriateness=outcome,
    )


def approved_passage(request: CurriculumRetrievalRequest) -> RetrievedCurriculumPassage:
    source = CurriculumSourceRecord(
        source_id="SYNTHETIC-ORCHESTRATION-SOURCE",
        title="Synthetic approved orchestration source",
        publisher_authority="Synthetic test authority",
        grade=request.grade,
        subject="Mathematics",
        language=request.requested_language,
        source_type="synthetic-test-fixture",
        source_location="repository://synthetic/orchestration",
        source_version="synthetic-v1",
        metadata_status=MetadataStatus.VERIFIED,
        ingestion_status=IngestionStatus.INGESTED,
        review_status=CurriculumReviewStatus.APPROVED,
        usage_rights_status=UsageRightsStatus.PERMITTED,
    )
    return RetrievedCurriculumPassage(
        chunk=CurriculumChunk(
            chunk_id="SYNTHETIC-ORCHESTRATION-CHUNK",
            source_id=source.source_id,
            source_version="synthetic-v1",
            content="Use the approved mathematical concept to explain the solution clearly.",
            grade=request.grade,
            subject="Mathematics",
            language=request.requested_language or "en",
            skill_ids=(request.skill_id,),
            page_number=1,
            section_locator="Synthetic section",
            review_status=CurriculumReviewStatus.APPROVED,
        ),
        source=source,
        score=1.0,
    )


def fixture_for(
    scenario_id: str, mode: SyntheticFixtureMode = SyntheticFixtureMode.COMPLETE
) -> SyntheticTutorContextFixture:
    return SyntheticTutorContextFixture.select(
        scenario_id,
        allow_synthetic=True,
        mode=mode,
    )


def orchestrator_for(
    fixture: SyntheticTutorContextFixture,
    *,
    mapping: SkillMappingResult | None = None,
    providers: ContextProviders | SyntheticTutorContextFixture | None = None,
    controller: CountingController | None = None,
    llm: object | None = None,
    curriculum: FixedCurriculumRetriever | None = None,
    verifier: object = "default",
    answer_provider: FixedAnswerProvider | None = None,
    mapper_error: bool = False,
    max_regeneration_attempts: int = 2,
) -> tuple[TutorOrchestrator, CountingController, object]:
    selected_mapping = mapping or fixture.assembly_request().skill_mapping
    mapper = FixedMapper(selected_mapping, error=mapper_error)
    context_providers = providers or fixture
    counting_controller = controller or CountingController(ScaffoldingController())
    selected_verifier = (
        DeterministicFakeSemanticVerifier(semantic_result()) if verifier == "default" else verifier
    )
    selected_llm = llm or DeterministicFakeLlmProvider(
        response=RESPONSES[fixture.expected_assistance_level]
    )
    context_assembler = TutorContextAssembler(
        learner_provider=context_providers,
        mastery_provider=context_providers,
        support_need_provider=context_providers,
        assessment_provider=context_providers,
        history_provider=context_providers,
        valid_skill_ids=VALID_SKILLS,
    )
    orchestrator = TutorOrchestrator(
        skill_mapper=mapper,
        skill_mapper_source=fixture.source,
        context_assembler=context_assembler,
        controller=counting_controller,
        llm_provider=selected_llm,
        valid_skill_ids=VALID_SKILLS,
        curriculum_retriever=curriculum,
        semantic_verifier=selected_verifier,
        trusted_answer_provider=answer_provider or FixedAnswerProvider(),
        semantic_verifier_is_simulated=selected_verifier is not None,
        max_regeneration_attempts=max_regeneration_attempts,
    )
    return orchestrator, counting_controller, selected_llm


def run_fixture(orchestrator: TutorOrchestrator, fixture: SyntheticTutorContextFixture):
    return orchestrator.run(
        TutorWorkflowRequest(
            learner_id=fixture.learner_id,
            student_message="Help me understand this problem.",
            response_language="en",
        )
    )


@pytest.mark.parametrize(
    "scenario_id",
    [
        "AT-V1-001",
        "AT-V1-002",
        "AT-V1-003",
        "AT-V1-006",
        "AT-V1-010",
        "AT-V1-011",
    ],
)
def test_successful_synthetic_l0_to_l5_workflows_are_simulations(
    scenario_id: str,
) -> None:
    fixture = fixture_for(scenario_id)
    orchestrator, controller, _ = orchestrator_for(fixture)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS
    assert result.assistance_level is fixture.expected_assistance_level
    assert result.verification_outcome is VerificationOutcome.PASS
    assert result.response_text is None
    assert result.verification_simulated is True
    assert result.demonstration_notice == SYNTHETIC_DEMO_NOTICE
    assert controller.calls == 1
    assert result.draft_attempt_count == 1


def test_successful_synthetic_l6_requires_eligible_fake_evidence() -> None:
    fixture = fixture_for("AT-V1-012")
    curriculum = FixedCurriculumRetriever(status=CurriculumRetrievalStatus.FOUND)
    orchestrator, _, _ = orchestrator_for(fixture, curriculum=curriculum)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS
    assert result.assistance_level is AssistanceLevel.FULL_EXPLANATION
    assert result.curriculum_status is CurriculumRetrievalStatus.FOUND
    assert result.verification_evidence_provenance
    assert result.response_text is None


def test_l6_without_evidence_stops_before_generation() -> None:
    fixture = fixture_for("AT-V1-012")
    llm = RecordingLlm(RESPONSES[AssistanceLevel.FULL_EXPLANATION])
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.CURRICULUM_UNAVAILABLE
    assert result.assistance_level is AssistanceLevel.FULL_EXPLANATION
    assert result.generation_status is None
    assert result.response_text is None
    assert llm.calls == 0


def test_l6_curriculum_provider_error_is_unavailable() -> None:
    fixture = fixture_for("AT-V1-012")
    curriculum = FixedCurriculumRetriever(error=True)
    orchestrator, _, _ = orchestrator_for(fixture, curriculum=curriculum)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.CURRICULUM_UNAVAILABLE
    assert result.curriculum_status is CurriculumRetrievalStatus.PROVIDER_ERROR
    assert result.response_text is None


@pytest.mark.parametrize(
    ("mapping", "expected"),
    [
        (
            SkillMappingResult(
                status=SkillMappingStatus.AMBIGUOUS,
                intent=LearningIntent.EXPLANATION_REQUEST,
                clarification_needed=True,
                clarification_question="Do you mean fractions or operations?",
            ),
            TutorWorkflowStatus.CLARIFICATION_REQUIRED,
        ),
        (
            SkillMappingResult(
                status=SkillMappingStatus.NO_MATCH,
                intent=LearningIntent.EXPLANATION_REQUEST,
                clarification_needed=False,
            ),
            TutorWorkflowStatus.NO_SUPPORTED_SKILL,
        ),
        (
            SkillMappingResult(
                status=SkillMappingStatus.NOT_SKILL_RELATED,
                intent=LearningIntent.OFF_TOPIC,
                clarification_needed=False,
            ),
            TutorWorkflowStatus.NOT_SKILL_RELATED,
        ),
    ],
)
def test_non_confirmed_mapping_short_circuits_before_controller(
    mapping: SkillMappingResult,
    expected: TutorWorkflowStatus,
) -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, controller, _ = orchestrator_for(fixture, mapping=mapping)

    result = run_fixture(orchestrator, fixture)

    assert result.status is expected
    assert result.response_text is None
    assert controller.calls == 0


@pytest.mark.parametrize(
    ("missing", "reason"),
    [
        ("learner", ContextReadinessReason.LEARNER_NOT_FOUND),
        ("mastery", ContextReadinessReason.MASTERY_NOT_FOUND),
        ("support", ContextReadinessReason.SUPPORT_NEED_NOT_YET_OBSERVED),
        ("assessment", ContextReadinessReason.ASSESSMENT_NOT_FOUND),
        ("history", ContextReadinessReason.ASSISTANCE_HISTORY_NOT_FOUND),
    ],
)
def test_missing_context_evidence_stops_before_controller(
    missing: str,
    reason: ContextReadinessReason,
) -> None:
    fixture = fixture_for("AT-V1-002")
    providers = ContextProviders(fixture, missing=missing)
    orchestrator, controller, _ = orchestrator_for(fixture, providers=providers)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.CONTEXT_NOT_READY
    assert reason in {issue.reason for issue in result.context_issues}
    assert result.response_text is None
    assert controller.calls == 0


def test_cold_start_preserves_not_ready_reasons() -> None:
    fixture = fixture_for("AT-V1-001", SyntheticFixtureMode.COLD_START)
    orchestrator, controller, _ = orchestrator_for(fixture)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.CONTEXT_NOT_READY
    assert {issue.reason for issue in result.context_issues} == {
        ContextReadinessReason.MASTERY_NOT_FOUND,
        ContextReadinessReason.SUPPORT_NEED_NOT_YET_OBSERVED,
    }
    assert controller.calls == 0


def test_context_provider_exception_is_safely_reported() -> None:
    fixture = fixture_for("AT-V1-001")
    providers = ContextProviders(fixture, error="mastery")
    orchestrator, _, _ = orchestrator_for(fixture, providers=providers)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.CONTEXT_NOT_READY
    assert ContextReadinessReason.MASTERY_PROVIDER_ERROR in {
        issue.reason for issue in result.context_issues
    }
    assert "private" not in result.safe_message


def test_mapper_exception_is_dependency_failure_without_fallback() -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, controller, _ = orchestrator_for(fixture, mapper_error=True)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.DEPENDENCY_FAILURE
    assert result.skill_mapping_status is None
    assert result.response_text is None
    assert controller.calls == 0


def test_controller_is_called_once_and_selected_level_is_unchanged() -> None:
    fixture = fixture_for("AT-V1-010")
    orchestrator, controller, _ = orchestrator_for(fixture)

    result = run_fixture(orchestrator, fixture)

    assert controller.calls == 1
    assert result.assistance_level is fixture.expected_assistance_level
    assert result.controller_reason_codes


def test_controller_exception_fails_closed() -> None:
    fixture = fixture_for("AT-V1-001")
    controller = FailingController()
    orchestrator, _, _ = orchestrator_for(fixture, controller=controller)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.DEPENDENCY_FAILURE
    assert result.response_text is None
    assert "private" not in result.safe_message
    assert controller.calls == 1


@pytest.mark.parametrize("unexpected", [False, True])
def test_generation_failures_do_not_expose_draft(unexpected: bool) -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(
        fixture,
        llm=FailingLlm(unexpected=unexpected),
    )

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.GENERATION_FAILED
    assert result.response_text is None
    assert "private" not in result.safe_message


def test_invalid_generated_output_is_rejected_without_leakage() -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(fixture, llm=RecordingLlm("   "))

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.GENERATION_FAILED
    assert result.response_text is None


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (VerificationCheckOutcome.FAIL, TutorWorkflowStatus.VERIFICATION_FAILED),
        (
            VerificationCheckOutcome.INDETERMINATE,
            TutorWorkflowStatus.VERIFICATION_INDETERMINATE,
        ),
    ],
)
def test_rejected_verification_never_exposes_generated_draft(
    outcome: VerificationCheckOutcome,
    status: TutorWorkflowStatus,
) -> None:
    fixture = fixture_for("AT-V1-001")
    secret_draft = "This hidden generated draft must never leave the rejected workflow."
    verifier = DeterministicFakeSemanticVerifier(semantic_result(outcome))
    orchestrator, _, _ = orchestrator_for(
        fixture,
        llm=RecordingLlm(secret_draft),
        verifier=verifier,
    )

    result = run_fixture(orchestrator, fixture)

    assert result.status is status
    assert result.response_text is None
    assert secret_draft not in result.model_dump_json()


def test_retryable_failure_then_pass_regenerates_without_changing_level() -> None:
    fixture = fixture_for("AT-V1-001")
    llm = SequenceLlm(["The answer is 999.", "Try the problem once yourself."])
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS
    assert result.draft_attempt_count == 2
    assert llm.calls == 2
    assert all(
        prompt.assistance_level is AssistanceLevel.INDEPENDENT_RETRY for prompt in llm.prompts
    )
    assert "LEVEL_STRUCTURE_VIOLATION" in llm.prompts[1].user_content
    assert result.response_text is None
    assert "The answer is 999" not in result.model_dump_json()


def test_repeated_retryable_failure_stops_after_safe_bound() -> None:
    fixture = fixture_for("AT-V1-001")
    secret = "The answer is 999."
    llm = SequenceLlm([secret, secret, secret])
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.VERIFICATION_FAILED
    assert result.draft_attempt_count == 3
    assert llm.calls == 3
    assert result.response_text is None
    assert secret not in result.model_dump_json()


def test_indeterminate_verification_is_not_regenerated() -> None:
    fixture = fixture_for("AT-V1-001")
    llm = SequenceLlm(["Try the problem once yourself."])
    verifier = DeterministicFakeSemanticVerifier(
        semantic_result(VerificationCheckOutcome.INDETERMINATE)
    )
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm, verifier=verifier)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.VERIFICATION_INDETERMINATE
    assert result.draft_attempt_count == 1
    assert llm.calls == 1


def test_provider_timeout_during_regeneration_stops_without_fallback() -> None:
    fixture = fixture_for("AT-V1-001")
    secret = "The answer is 999."
    llm = SequenceLlm([secret, TimeoutError("private timeout")])
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.GENERATION_FAILED
    assert result.draft_attempt_count == 2
    assert llm.calls == 2
    assert result.response_text is None
    assert secret not in result.model_dump_json()


def test_unsafe_draft_is_non_retryable() -> None:
    fixture = fixture_for("AT-V1-001")
    unsafe = "kill yourself"
    llm = SequenceLlm([unsafe])
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.VERIFICATION_FAILED
    assert result.draft_attempt_count == 1
    assert llm.calls == 1
    assert unsafe not in result.model_dump_json()


def test_regeneration_never_escalates_assistance_level() -> None:
    fixture = fixture_for("AT-V1-001")
    llm = SequenceLlm(
        [
            "The answer is 999.",
            "1. Solve everything.\n2. The answer is 999.",
            "The answer is 999.",
        ]
    )
    orchestrator, _, _ = orchestrator_for(fixture, llm=llm)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.VERIFICATION_FAILED
    assert result.assistance_level is AssistanceLevel.INDEPENDENT_RETRY
    assert result.draft_attempt_count == 3
    assert all(
        prompt.assistance_level is AssistanceLevel.INDEPENDENT_RETRY for prompt in llm.prompts
    )


def test_missing_semantic_verifier_is_indeterminate() -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(fixture, verifier=None)

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.VERIFICATION_INDETERMINATE
    assert result.verification_outcome is VerificationOutcome.INDETERMINATE
    assert result.response_text is None


def test_unexpected_semantic_verifier_exception_fails_closed() -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(
        fixture,
        verifier=ExplodingSemanticVerifier(),
    )

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.DEPENDENCY_FAILURE
    assert result.response_text is None
    assert "private" not in result.safe_message


def test_real_provider_failure_does_not_activate_synthetic_context() -> None:
    fixture = fixture_for("AT-V1-001")
    real_source = EvidenceSource(source_id="test:real-context", origin=EvidenceOrigin.REAL)
    providers = ContextProviders(fixture, error="mastery", source=real_source)
    mapper = FixedMapper(fixture.assembly_request().skill_mapping)
    controller = CountingController(ScaffoldingController())
    context_assembler = TutorContextAssembler(
        learner_provider=providers,
        mastery_provider=providers,
        support_need_provider=providers,
        assessment_provider=providers,
        history_provider=providers,
        valid_skill_ids=VALID_SKILLS,
    )
    orchestrator = TutorOrchestrator(
        skill_mapper=mapper,
        skill_mapper_source=real_source,
        context_assembler=context_assembler,
        controller=controller,
        llm_provider=RecordingLlm("unused"),
        valid_skill_ids=VALID_SKILLS,
    )

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.CONTEXT_NOT_READY
    assert result.execution_origin is ContextEvidenceOrigin.REAL
    assert result.demonstration_notice is None
    assert result.response_text is None


def test_gemini_named_provider_is_never_authorized_for_learner_delivery() -> None:
    fixture = fixture_for("AT-V1-001")
    real_source = EvidenceSource(source_id="test:real-boundaries", origin=EvidenceOrigin.REAL)
    providers = ContextProviders(fixture, source=real_source)
    context_assembler = TutorContextAssembler(
        learner_provider=providers,
        mastery_provider=providers,
        support_need_provider=providers,
        assessment_provider=providers,
        history_provider=providers,
        valid_skill_ids=VALID_SKILLS,
    )
    llm = RecordingLlm(RESPONSES[AssistanceLevel.INDEPENDENT_RETRY], name="google-gemini")
    orchestrator = TutorOrchestrator(
        skill_mapper=FixedMapper(fixture.assembly_request().skill_mapping),
        skill_mapper_source=real_source,
        context_assembler=context_assembler,
        controller=ScaffoldingController(),
        llm_provider=llm,
        valid_skill_ids=VALID_SKILLS,
        semantic_verifier=PassingSemanticVerifier(),
        trusted_answer_provider=FixedAnswerProvider(),
    )

    result = run_fixture(orchestrator, fixture)

    assert result.verification_outcome is VerificationOutcome.PASS
    assert result.status is TutorWorkflowStatus.DELIVERY_NOT_AUTHORIZED
    assert result.response_text is None


def test_gemini_can_be_explicitly_authorized_for_adult_research_path() -> None:
    fixture = fixture_for("AT-V1-001")
    real_source = EvidenceSource(source_id="test:real-research", origin=EvidenceOrigin.REAL)
    providers = ContextProviders(fixture, source=real_source)
    orchestrator = TutorOrchestrator(
        skill_mapper=FixedMapper(fixture.assembly_request().skill_mapping),
        skill_mapper_source=real_source,
        context_assembler=TutorContextAssembler(
            learner_provider=providers,
            mastery_provider=providers,
            support_need_provider=providers,
            assessment_provider=providers,
            history_provider=providers,
            valid_skill_ids=VALID_SKILLS,
        ),
        controller=ScaffoldingController(),
        llm_provider=RecordingLlm(
            RESPONSES[AssistanceLevel.INDEPENDENT_RETRY], name="google-gemini"
        ),
        valid_skill_ids=VALID_SKILLS,
        semantic_verifier=PassingSemanticVerifier(),
        trusted_answer_provider=FixedAnswerProvider(),
        authorized_generation_providers={"google-gemini"},
    )

    result = run_fixture(orchestrator, fixture)

    assert result.status is TutorWorkflowStatus.APPROVED_RESPONSE
    assert result.response_text == RESPONSES[AssistanceLevel.INDEPENDENT_RETRY]


def test_context_and_curriculum_provenance_are_preserved() -> None:
    fixture = fixture_for("AT-V1-012")
    orchestrator, _, _ = orchestrator_for(
        fixture,
        curriculum=FixedCurriculumRetriever(status=CurriculumRetrievalStatus.FOUND),
    )

    result = run_fixture(orchestrator, fixture)

    assert result.context_provenance
    assert all(item.origin is EvidenceOrigin.SYNTHETIC for item in result.context_provenance)
    assert result.verification_evidence_provenance[0].source_id == (
        "SYNTHETIC-ORCHESTRATION-SOURCE"
    )
    assert result.execution_origin is ContextEvidenceOrigin.SYNTHETIC


def test_invalid_request_and_unsupported_language_stop_before_mapping() -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(fixture)

    invalid = orchestrator.run({"learner_id": "not-a-uuid", "student_message": "Help"})
    unsupported = orchestrator.run(
        {
            "learner_id": str(fixture.learner_id),
            "student_message": "Help",
            "response_language": "fr",
        }
    )

    assert invalid.status is TutorWorkflowStatus.INVALID_REQUEST
    assert unsupported.status is TutorWorkflowStatus.UNSUPPORTED_LANGUAGE
    assert invalid.response_text is unsupported.response_text is None


def test_workflow_result_contract_forbids_draft_leakage_on_failure() -> None:
    from app.adaptive_tutor.application.orchestration import TutorWorkflowResult

    with pytest.raises(ValidationError, match="only APPROVED_RESPONSE"):
        TutorWorkflowResult(
            status=TutorWorkflowStatus.VERIFICATION_FAILED,
            safe_message="Rejected.",
            response_text="hidden draft",
            execution_origin=ContextEvidenceOrigin.REAL,
        )


def test_offline_workflow_uses_no_network_or_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", blocked_network)
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(fixture)

    result = run_fixture(orchestrator, fixture)

    source = inspect.getsource(TutorOrchestrator)
    assert result.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS
    assert "sqlalchemy" not in source
    assert "requests." not in source


def test_demo_notice_is_exact_and_mandatory_for_synthetic_trace() -> None:
    fixture = fixture_for("AT-V1-001")
    orchestrator, _, _ = orchestrator_for(fixture)

    result = run_fixture(orchestrator, fixture)

    assert result.demonstration_notice == (
        "SYNTHETIC RESEARCH DEMONSTRATION — NOT REAL LEARNER DATA OR VALIDATED LLM OUTPUT."
    )

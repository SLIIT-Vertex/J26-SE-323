"""Controlled 14-scenario offline research pipeline; never authorizes delivery."""

from dataclasses import dataclass, field
from uuid import UUID

from app.adaptive_tutor.application.context_assembly import (
    AssessmentEvidenceResult,
    AssistanceHistoryResult,
    ContextEvidenceRequest,
    EvidenceStatus,
)
from app.adaptive_tutor.application.generation import (
    GenerationPrompt,
    LlmProviderUnavailableError,
)
from app.adaptive_tutor.application.orchestration import (
    SYNTHETIC_DEMO_NOTICE,
    TutorWorkflowRequest,
    TutorWorkflowResult,
    TutorWorkflowStatus,
)
from app.adaptive_tutor.application.verification import (
    DeterministicFakeSemanticVerifier,
    SemanticVerificationResult,
    VerificationCheckOutcome,
)
from app.adaptive_tutor.infrastructure.synthetic_context import (
    SyntheticFixtureMode,
    SyntheticTutorContextFixture,
)
from app.adaptive_tutor.infrastructure.synthetic_orchestration import (
    build_controlled_tutor_orchestrator,
)

_LEVEL_SCENARIOS = {
    "L0_PRE_INTERACTION": "AT-V1-001",
    "L1": "AT-V1-002",
    "L2": "AT-V1-003",
    "L3": "AT-V1-006",
    "L4": "AT-V1-010",
    "L5": "AT-V1-011",
    "L6_SYNTHETIC_CURRICULUM": "AT-V1-012",
}


@dataclass(frozen=True, slots=True)
class OfflineScenarioResult:
    scenario: str
    status: TutorWorkflowStatus
    assistance_level: str | None
    draft_attempt_count: int
    demonstration_notice: str


@dataclass
class SequenceOfflineLlm:
    responses: list[str | Exception]
    name: str = "offline-controlled-sequence-llm"
    calls: int = 0
    prompts: list[GenerationPrompt] = field(default_factory=list)

    def generate(self, prompt: GenerationPrompt) -> str:
        self.prompts.append(prompt)
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


@dataclass(frozen=True, slots=True)
class PreInteractionFixture:
    base: SyntheticTutorContextFixture

    def __getattr__(self, name: str) -> object:
        return getattr(self.base, name)

    def get_assessment_evidence(self, request: ContextEvidenceRequest) -> AssessmentEvidenceResult:
        return AssessmentEvidenceResult(
            status=EvidenceStatus.NOT_YET_OBSERVED,
            attempt_count=0,
        )

    def get_assistance_history(self, request: ContextEvidenceRequest) -> AssistanceHistoryResult:
        return AssistanceHistoryResult(status=EvidenceStatus.NOT_YET_OBSERVED)


def run_offline_pipeline() -> tuple[OfflineScenarioResult, ...]:
    runs: list[tuple[str, TutorWorkflowResult]] = []
    for label, scenario_id in _LEVEL_SCENARIOS.items():
        fixture = _fixture(scenario_id)
        controlled = PreInteractionFixture(fixture) if label == "L0_PRE_INTERACTION" else fixture
        orchestrator = build_controlled_tutor_orchestrator(controlled)  # type: ignore[arg-type]
        runs.append((label, _run(orchestrator, fixture.learner_id)))

    l6 = _fixture("AT-V1-012")
    runs.append(
        (
            "L6_BLOCKED_NO_EVIDENCE",
            _run(
                build_controlled_tutor_orchestrator(l6, include_curriculum=False),
                l6.learner_id,
            ),
        )
    )
    l0 = _fixture("AT-V1-001")
    runs.append(
        (
            "FAIL_THEN_REGENERATE",
            _run(
                build_controlled_tutor_orchestrator(
                    l0,
                    llm_provider=SequenceOfflineLlm(
                        ["The answer is 999.", "Try the problem once yourself."]
                    ),
                ),
                l0.learner_id,
            ),
        )
    )
    indeterminate = SemanticVerificationResult(
        assistance_level_compliance=VerificationCheckOutcome.INDETERMINATE,
        answer_leakage=VerificationCheckOutcome.INDETERMINATE,
        factual_support=VerificationCheckOutcome.INDETERMINATE,
        language_appropriateness=VerificationCheckOutcome.INDETERMINATE,
        age_appropriateness=VerificationCheckOutcome.INDETERMINATE,
    )
    runs.append(
        (
            "VERIFIER_INDETERMINATE",
            _run(
                build_controlled_tutor_orchestrator(
                    l0,
                    semantic_verifier=DeterministicFakeSemanticVerifier(indeterminate),
                ),
                l0.learner_id,
            ),
        )
    )
    base = build_controlled_tutor_orchestrator(l0)
    runs.append(("UNSUPPORTED_LANGUAGE", _run(base, l0.learner_id, language="fr")))
    runs.append(("SKILL_MAPPER_ABSTENTION", _run(base, l0.learner_id, message="can you help me?")))
    cold = _fixture("AT-V1-001", SyntheticFixtureMode.COLD_START)
    runs.append(
        (
            "MISSING_CONTEXT",
            _run(build_controlled_tutor_orchestrator(cold), cold.learner_id),
        )
    )
    runs.append(
        (
            "PROVIDER_FAILURE",
            _run(
                build_controlled_tutor_orchestrator(
                    l0,
                    llm_provider=SequenceOfflineLlm(
                        [LlmProviderUnavailableError("controlled offline failure")]
                    ),
                ),
                l0.learner_id,
            ),
        )
    )
    _validate_demonstration(runs)
    return tuple(
        OfflineScenarioResult(
            scenario=label,
            status=result.status,
            assistance_level=result.assistance_level.value if result.assistance_level else None,
            draft_attempt_count=result.draft_attempt_count,
            demonstration_notice=result.demonstration_notice or "",
        )
        for label, result in runs
    )


def _fixture(
    scenario_id: str,
    mode: SyntheticFixtureMode = SyntheticFixtureMode.COMPLETE,
) -> SyntheticTutorContextFixture:
    return SyntheticTutorContextFixture.select(
        scenario_id,
        allow_synthetic=True,
        mode=mode,
    )


def _run(
    orchestrator: object,
    learner_id: UUID,
    *,
    message: str = "Help me understand this problem.",
    language: str = "en",
) -> TutorWorkflowResult:
    return orchestrator.run(  # type: ignore[attr-defined,no-any-return]
        TutorWorkflowRequest(
            learner_id=learner_id,
            student_message=message,
            response_language=language,
        )
    )


def _validate_demonstration(runs: list[tuple[str, TutorWorkflowResult]]) -> None:
    if len(runs) != 14:
        raise RuntimeError("offline research runner must contain exactly 14 scenarios")
    for _label, result in runs:
        if result.response_text is not None or result.demonstration_notice != SYNTHETIC_DEMO_NOTICE:
            raise RuntimeError("offline research runner crossed the non-delivery boundary")

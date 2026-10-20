from dataclasses import dataclass
from uuid import UUID

import pytest

from app.adaptive_tutor.application import (
    AssessmentEvidenceResult,
    AssistanceHistoryResult,
    ContextEvidenceOrigin,
    ContextInput,
    ContextIssueKind,
    ContextReadinessReason,
    ContextReadinessStatus,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    ScaffoldingController,
    SkillMappingResult,
    SupportNeedResult,
    TutorContextAssembler,
    TutorContextAssemblyRequest,
    TutoringContext,
)
from app.adaptive_tutor.application.context_assembly import ContextEvidenceRequest
from app.adaptive_tutor.domain import (
    AssistanceLevel,
    LearningIntent,
    SkillMappingStatus,
)
from app.adaptive_tutor.infrastructure import (
    SyntheticFixtureMode,
    SyntheticTutorContextFixture,
)
from app.knowledge_tracing.application.mastery import (
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
)
from app.shared.learner.domain import Learner

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000001")
VALID_SKILLS = {"MAT-FRC", "MAT-OPS", "MAT-TIM", "APT-LOG"}
REAL_SOURCE = EvidenceSource(source_id="test:real-provider", origin=EvidenceOrigin.REAL)


def matched_mapping(skill_id: str = "MAT-FRC") -> SkillMappingResult:
    return SkillMappingResult(
        status=SkillMappingStatus.MATCHED,
        intent=LearningIntent.EXPLANATION_REQUEST,
        skill_id=skill_id,
        confidence=0.9,
        clarification_needed=False,
    )


def assembly_request(mapping: SkillMappingResult | None = None) -> TutorContextAssemblyRequest:
    return TutorContextAssemblyRequest(
        learner_id=LEARNER_ID,
        skill_mapping=mapping or matched_mapping(),
        skill_mapping_source=REAL_SOURCE,
    )


@dataclass
class FakeProviders:
    source: EvidenceSource = REAL_SOURCE
    learner_result: object = LearnerLookupResult(
        status=EvidenceStatus.AVAILABLE,
        learner=Learner(id=LEARNER_ID, grade=4, preferred_language="en"),
    )
    mastery_result: object = MasteryResult(
        learner_id=LEARNER_ID,
        skill_id="MAT-FRC",
        status=MasteryStatus.AVAILABLE,
        mastery=0.6,
    )
    support_result: object = SupportNeedResult(
        status=EvidenceStatus.AVAILABLE,
        support_need=0.4,
    )
    assessment_result: object = AssessmentEvidenceResult(
        status=EvidenceStatus.AVAILABLE,
        attempt_count=1,
        is_correct=False,
        error_severity=0.3,
    )
    history_result: object = AssistanceHistoryResult(
        status=EvidenceStatus.NOT_YET_OBSERVED,
    )
    failure: str | None = None

    def get_learner(self, learner_id: UUID) -> object:
        self._maybe_fail("learner")
        return self.learner_result

    def get_mastery(self, request: MasteryRetrievalRequest) -> object:
        self._maybe_fail("mastery")
        return self.mastery_result

    def get_support_need(self, request: ContextEvidenceRequest) -> object:
        self._maybe_fail("support")
        return self.support_result

    def get_assessment_evidence(self, request: ContextEvidenceRequest) -> object:
        self._maybe_fail("assessment")
        return self.assessment_result

    def get_assistance_history(self, request: ContextEvidenceRequest) -> object:
        self._maybe_fail("history")
        return self.history_result

    def _maybe_fail(self, provider: str) -> None:
        if self.failure == provider:
            raise RuntimeError("sensitive provider detail must not escape")


def assembler(
    providers: FakeProviders, *, valid_skills: set[str] = VALID_SKILLS
) -> TutorContextAssembler:
    return TutorContextAssembler(
        learner_provider=providers,
        mastery_provider=providers,
        support_need_provider=providers,
        assessment_provider=providers,
        history_provider=providers,
        valid_skill_ids=valid_skills,
    )


def reasons(result: object) -> set[ContextReadinessReason]:
    return {issue.reason for issue in result.issues}


def test_complete_valid_context_assembly_uses_canonical_contract() -> None:
    result = assembler(FakeProviders()).assemble(assembly_request())

    assert result.status is ContextReadinessStatus.READY
    assert isinstance(result.context, TutoringContext)
    assert result.learner_grade == 4
    assert result.context.model_dump() == {
        "learner_id": LEARNER_ID,
        "skill_id": "MAT-FRC",
        "mastery": 0.6,
        "support_need": 0.4,
        "attempt_count": 1,
        "is_correct": False,
        "error_severity": 0.3,
        "previous_assistance_level": None,
        "previous_hint_effective": None,
    }
    assert result.issues == ()
    assert result.evidence_origin is ContextEvidenceOrigin.REAL


def test_missing_learner_is_not_ready() -> None:
    providers = FakeProviders(learner_result=LearnerLookupResult(status=EvidenceStatus.NOT_FOUND))

    result = assembler(providers).assemble(assembly_request())

    assert result.context is None
    assert reasons(result) == {ContextReadinessReason.LEARNER_NOT_FOUND}


def test_unsupported_grade_is_not_ready() -> None:
    providers = FakeProviders(
        learner_result=LearnerLookupResult(
            status=EvidenceStatus.AVAILABLE,
            learner=Learner(id=LEARNER_ID, grade=6, preferred_language="en"),
        )
    )

    result = assembler(providers).assemble(assembly_request())

    assert reasons(result) == {ContextReadinessReason.UNSUPPORTED_GRADE}


@pytest.mark.parametrize(
    ("mapping", "reason"),
    [
        (
            SkillMappingResult(
                status=SkillMappingStatus.AMBIGUOUS,
                intent=LearningIntent.EXPLANATION_REQUEST,
                clarification_needed=True,
                clarification_question="Which topic do you mean?",
            ),
            ContextReadinessReason.SKILL_MAPPING_AMBIGUOUS,
        ),
        (
            SkillMappingResult(
                status=SkillMappingStatus.NO_MATCH,
                intent=LearningIntent.EXPLANATION_REQUEST,
                clarification_needed=False,
            ),
            ContextReadinessReason.SKILL_NOT_MATCHED,
        ),
        (
            SkillMappingResult(
                status=SkillMappingStatus.NOT_SKILL_RELATED,
                intent=LearningIntent.OFF_TOPIC,
                clarification_needed=False,
            ),
            ContextReadinessReason.SKILL_NOT_RELATED,
        ),
    ],
)
def test_non_confirmed_skill_mapping_is_not_ready(
    mapping: SkillMappingResult,
    reason: ContextReadinessReason,
) -> None:
    result = assembler(FakeProviders()).assemble(assembly_request(mapping))

    assert reasons(result) == {reason}


def test_confirmed_unknown_taxonomy_skill_is_rejected() -> None:
    result = assembler(FakeProviders()).assemble(assembly_request(matched_mapping("NOT-REAL")))

    assert reasons(result) == {ContextReadinessReason.SKILL_INVALID}


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (MasteryStatus.NOT_FOUND, ContextReadinessReason.MASTERY_NOT_FOUND),
        (
            MasteryStatus.PROVIDER_UNAVAILABLE,
            ContextReadinessReason.MASTERY_PROVIDER_UNAVAILABLE,
        ),
        (MasteryStatus.PROVIDER_ERROR, ContextReadinessReason.MASTERY_PROVIDER_ERROR),
    ],
)
def test_unavailable_mastery_is_not_ready(
    status: MasteryStatus,
    reason: ContextReadinessReason,
) -> None:
    providers = FakeProviders(
        mastery_result=MasteryResult(
            learner_id=LEARNER_ID,
            skill_id="MAT-FRC",
            status=status,
        )
    )

    result = assembler(providers).assemble(assembly_request())

    assert reason in reasons(result)


@pytest.mark.parametrize("mastery", [-0.1, 1.1])
def test_mastery_outside_normalized_range_is_invalid(mastery: float) -> None:
    providers = FakeProviders(
        mastery_result=MasteryResult.model_construct(
            learner_id=LEARNER_ID,
            skill_id="MAT-FRC",
            status=MasteryStatus.AVAILABLE,
            mastery=mastery,
        )
    )

    result = assembler(providers).assemble(assembly_request())

    assert ContextReadinessReason.MASTERY_INVALID in reasons(result)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (EvidenceStatus.NOT_FOUND, ContextReadinessReason.SUPPORT_NEED_NOT_FOUND),
        (
            EvidenceStatus.NOT_YET_OBSERVED,
            ContextReadinessReason.SUPPORT_NEED_NOT_YET_OBSERVED,
        ),
        (
            EvidenceStatus.PROVIDER_UNAVAILABLE,
            ContextReadinessReason.SUPPORT_NEED_PROVIDER_UNAVAILABLE,
        ),
    ],
)
def test_unavailable_support_need_is_not_ready(
    status: EvidenceStatus,
    reason: ContextReadinessReason,
) -> None:
    providers = FakeProviders(support_result=SupportNeedResult(status=status))

    result = assembler(providers).assemble(assembly_request())

    assert reason in reasons(result)


@pytest.mark.parametrize("support_need", [-0.1, 1.1])
def test_support_need_outside_normalized_range_is_invalid(support_need: float) -> None:
    providers = FakeProviders(
        support_result=SupportNeedResult.model_construct(
            status=EvidenceStatus.AVAILABLE,
            support_need=support_need,
        )
    )

    result = assembler(providers).assemble(assembly_request())

    assert ContextReadinessReason.SUPPORT_NEED_INVALID in reasons(result)


def test_categorical_learner_state_output_is_not_treated_as_numeric_support() -> None:
    providers = FakeProviders(
        support_result={
            "status": EvidenceStatus.AVAILABLE,
            "support_need": "request_tutor_support",
        }
    )

    result = assembler(providers).assemble(assembly_request())

    assert ContextReadinessReason.SUPPORT_NEED_INVALID in reasons(result)


@pytest.mark.parametrize(
    "assessment",
    [
        AssessmentEvidenceResult.model_construct(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=1,
            is_correct=None,
            error_severity=0.3,
        ),
        AssessmentEvidenceResult.model_construct(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=1,
            is_correct=False,
            error_severity=None,
        ),
        AssessmentEvidenceResult.model_construct(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=None,
            is_correct=None,
            error_severity=None,
        ),
        AssessmentEvidenceResult.model_construct(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=-1,
            is_correct=False,
            error_severity=0.3,
        ),
    ],
)
def test_missing_or_invalid_completed_attempt_evidence_is_not_ready(
    assessment: AssessmentEvidenceResult,
) -> None:
    result = assembler(FakeProviders(assessment_result=assessment)).assemble(assembly_request())

    assert ContextReadinessReason.ASSESSMENT_INVALID in reasons(result)


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (EvidenceStatus.UNCERTAIN, ContextReadinessReason.ASSESSMENT_UNCERTAIN),
        (EvidenceStatus.STALE, ContextReadinessReason.ASSESSMENT_STALE),
        (
            EvidenceStatus.SESSION_MISMATCH,
            ContextReadinessReason.ASSESSMENT_SESSION_MISMATCH,
        ),
    ],
)
def test_assessment_fail_closed_statuses_have_explicit_readiness_reasons(
    status: EvidenceStatus,
    reason: ContextReadinessReason,
) -> None:
    result = assembler(
        FakeProviders(assessment_result=AssessmentEvidenceResult(status=status))
    ).assemble(assembly_request())

    assert reasons(result) == {reason}


def test_hint_effectiveness_without_previous_assistance_is_invalid() -> None:
    history = AssistanceHistoryResult.model_construct(
        status=EvidenceStatus.AVAILABLE,
        previous_assistance_level=None,
        previous_hint_effective=True,
    )

    result = assembler(FakeProviders(history_result=history)).assemble(assembly_request())

    assert ContextReadinessReason.ASSISTANCE_HISTORY_INVALID in reasons(result)


def test_unknown_hint_effectiveness_with_previous_assistance_remains_valid() -> None:
    history = AssistanceHistoryResult(
        status=EvidenceStatus.AVAILABLE,
        previous_assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
        previous_hint_effective=None,
    )

    result = assembler(FakeProviders(history_result=history)).assemble(assembly_request())

    assert result.status is ContextReadinessStatus.READY
    assert result.context is not None
    assert result.context.previous_hint_effective is None


def test_legitimate_zero_values_are_preserved() -> None:
    providers = FakeProviders(
        mastery_result=MasteryResult(
            learner_id=LEARNER_ID,
            skill_id="MAT-FRC",
            status=MasteryStatus.AVAILABLE,
            mastery=0.0,
        ),
        support_result=SupportNeedResult(
            status=EvidenceStatus.AVAILABLE,
            support_need=0.0,
        ),
        assessment_result=AssessmentEvidenceResult(
            status=EvidenceStatus.NOT_YET_OBSERVED,
            attempt_count=0,
        ),
    )

    result = assembler(providers).assemble(assembly_request())

    assert result.context is not None
    assert result.context.mastery == 0.0
    assert result.context.support_need == 0.0
    assert result.context.attempt_count == 0
    assert result.context.is_correct is None
    assert result.context.error_severity is None


def test_cold_start_is_not_ready_without_fabricated_defaults() -> None:
    fixture = SyntheticTutorContextFixture.select(
        "AT-V1-001",
        allow_synthetic=True,
        mode=SyntheticFixtureMode.COLD_START,
    )
    result = TutorContextAssembler(
        learner_provider=fixture,
        mastery_provider=fixture,
        support_need_provider=fixture,
        assessment_provider=fixture,
        history_provider=fixture,
        valid_skill_ids=VALID_SKILLS,
    ).assemble(fixture.assembly_request())

    assert result.status is ContextReadinessStatus.NOT_READY
    assert result.context is None
    assert reasons(result) == {
        ContextReadinessReason.MASTERY_NOT_FOUND,
        ContextReadinessReason.SUPPORT_NEED_NOT_YET_OBSERVED,
    }


def test_synthetic_fixture_requires_explicit_opt_in_and_selection() -> None:
    with pytest.raises(PermissionError, match="allow_synthetic=True"):
        SyntheticTutorContextFixture.select("AT-V1-001")
    with pytest.raises(ValueError, match="unknown reference scenario"):
        SyntheticTutorContextFixture.select("missing", allow_synthetic=True)


def test_synthetic_context_is_unambiguously_labelled() -> None:
    fixture = SyntheticTutorContextFixture.select("AT-V1-001", allow_synthetic=True)
    result = TutorContextAssembler(
        learner_provider=fixture,
        mastery_provider=fixture,
        support_need_provider=fixture,
        assessment_provider=fixture,
        history_provider=fixture,
        valid_skill_ids=VALID_SKILLS,
    ).assemble(fixture.assembly_request())

    assert result.status is ContextReadinessStatus.READY
    assert result.evidence_origin is ContextEvidenceOrigin.SYNTHETIC
    assert all(item.origin is EvidenceOrigin.SYNTHETIC for item in result.provenance)
    assert all(item.source_id.startswith("synthetic:") for item in result.provenance)


@pytest.mark.parametrize(
    "scenario_id",
    [
        "AT-V1-001",
        "AT-V1-002",
        "AT-V1-003",
        "AT-V1-010",
        "AT-V1-011",
        "AT-V1-012",
        "AT-V1-020",
    ],
)
def test_selected_reference_fixtures_cover_l0_through_l6_without_forcing_policy(
    scenario_id: str,
) -> None:
    fixture = SyntheticTutorContextFixture.select(scenario_id, allow_synthetic=True)
    result = TutorContextAssembler(
        learner_provider=fixture,
        mastery_provider=fixture,
        support_need_provider=fixture,
        assessment_provider=fixture,
        history_provider=fixture,
        valid_skill_ids=VALID_SKILLS,
    ).assemble(fixture.assembly_request())

    assert result.context is not None
    assert ScaffoldingController().decide(result.context).assistance_level is (
        fixture.expected_assistance_level
    )


def test_real_provider_failure_does_not_trigger_synthetic_fallback() -> None:
    result = assembler(FakeProviders(failure="mastery")).assemble(assembly_request())

    assert ContextReadinessReason.MASTERY_PROVIDER_ERROR in reasons(result)
    assert result.evidence_origin is ContextEvidenceOrigin.REAL
    assert all(item.origin is EvidenceOrigin.REAL for item in result.provenance)


@pytest.mark.parametrize(
    ("failure", "input_name"),
    [
        ("learner", ContextInput.LEARNER),
        ("mastery", ContextInput.MASTERY),
        ("support", ContextInput.SUPPORT_NEED),
        ("assessment", ContextInput.ASSESSMENT),
        ("history", ContextInput.ASSISTANCE_HISTORY),
    ],
)
def test_provider_exceptions_are_safely_surfaced(
    failure: str,
    input_name: ContextInput,
) -> None:
    result = assembler(FakeProviders(failure=failure)).assemble(assembly_request())

    issue = next(issue for issue in result.issues if issue.input is input_name)
    assert issue.kind is ContextIssueKind.PROVIDER_FAILURE
    assert "sensitive provider detail" not in issue.message


def test_assembler_does_not_call_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("assembler called Controller V1")

    monkeypatch.setattr(ScaffoldingController, "decide", unexpected_call)

    assert assembler(FakeProviders()).assemble(assembly_request()).context is not None


def test_context_assembly_has_no_llm_rag_or_network_dependency() -> None:
    names = set(TutorContextAssembler.assemble.__code__.co_names)

    assert not names.intersection({"socket", "httpx", "requests", "gemini", "curriculum"})


def test_canonical_context_and_mastery_contracts_are_reused() -> None:
    result = assembler(FakeProviders()).assemble(assembly_request())

    assert type(result.context) is TutoringContext
    assert isinstance(FakeProviders().mastery_result, MasteryResult)

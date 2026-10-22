from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.api.contracts import ResearchInteractionResponse, TutorApiResponse
from app.adaptive_tutor.application.context_assembly import (
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    SupportNeedResult,
    TutorContextAssembler,
)
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.application.generation import (
    DeterministicFakeLlmProvider,
    LlmProviderUnavailableError,
    ProviderFailureReason,
)
from app.adaptive_tutor.application.orchestration import (
    TutorOrchestrator,
    TutorWorkflowStatus,
)
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.application.verification import (
    DeterministicFakeSemanticVerifier,
    SemanticVerificationResult,
    VerificationCheckOutcome,
)
from app.adaptive_tutor.domain import AssistanceLevel, LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure.assessment_evidence import (
    LedgerAssessmentEvidenceProvider,
)
from app.adaptive_tutor.infrastructure.gemini import (
    GeminiGenerationConfig,
    GeminiLlmProvider,
)
from app.adaptive_tutor.infrastructure.research_sessions import (
    CONTROLLED_ANNOTATION_SOURCE,
    EXPERIMENTAL_CURRICULUM_PROVENANCE,
    ExperimentalGenerationStatus,
    ExperimentalHintGenerator,
    ResearchAttemptAnnotation,
    ResearchSessionError,
    ResearchTutorService,
)
from app.adaptive_tutor.infrastructure.synthetic_orchestration import (
    SyntheticCurriculumRetriever,
    SyntheticTrustedAnswerProvider,
)
from app.adaptive_tutor.infrastructure.tutor_assessment import (
    SqlAlchemyTutorAssessmentRepository,
    TutorAssessmentAttemptModel,
)
from app.adaptive_tutor.infrastructure.tutor_history import (
    SqlAlchemyTutorHistoryRepository,
    TutorHistoryEventType,
    TutorHistoryProvider,
    TutorInteractionEventModel,
)
from app.knowledge_tracing.application.mastery import MasteryResult, MasteryStatus
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.model import LearnerModel

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000221")
RESEARCHER_ID = UUID("00000000-0000-4000-8000-000000000222")
NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)
POLICY = "controlled-research-severity-v1"
SOURCE = EvidenceSource(source_id="MOCKED:test:controlled-research", origin=EvidenceOrigin.SYNTHETIC)


class ArbitraryQuestionMapper:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def map(self, request: object) -> SkillMappingResult:
        self.questions.append(request.learner_message)
        return SkillMappingResult(
            status=SkillMappingStatus.MATCHED,
            intent=LearningIntent.EXPLANATION_REQUEST,
            skill_id="MAT-FRC",
            confidence=0.95,
            clarification_needed=False,
        )


class ControlledContext:
    source = SOURCE

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult:
        return LearnerLookupResult(
            status=EvidenceStatus.AVAILABLE,
            learner=Learner(id=learner_id, grade=5, preferred_language="en"),
        )

    def get_mastery(self, request: object) -> MasteryResult:
        return MasteryResult(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
            status=MasteryStatus.AVAILABLE,
            mastery=0.5,
        )

    def get_support_need(self, request: object) -> SupportNeedResult:
        return SupportNeedResult(status=EvidenceStatus.AVAILABLE, support_need=0.5)


class MissingSupportContext(ControlledContext):
    def get_support_need(self, request: object) -> SupportNeedResult:
        return SupportNeedResult(status=EvidenceStatus.NOT_FOUND)


class AbstainingMapper(ArbitraryQuestionMapper):
    def map(self, request: object) -> SkillMappingResult:
        self.questions.append(request.learner_message)
        return SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.EXPLANATION_REQUEST,
            candidate_skills=(),
            clarification_needed=True,
            clarification_question="Which Fractions idea do you mean?",
        )


class RecordingGeminiModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type("GeminiResponse", (), {"text": "Try drawing equal parts first."})()


class RecordingGeminiClient:
    def __init__(self) -> None:
        self.models = RecordingGeminiModels()


def passing_semantics() -> SemanticVerificationResult:
    return SemanticVerificationResult(
        assistance_level_compliance=VerificationCheckOutcome.PASS,
        answer_leakage=VerificationCheckOutcome.PASS,
        factual_support=VerificationCheckOutcome.PASS,
        language_appropriateness=VerificationCheckOutcome.PASS,
        age_appropriateness=VerificationCheckOutcome.PASS,
    )


def build_service(
    session: Session,
    *,
    mapper: ArbitraryQuestionMapper | None = None,
    controlled: ControlledContext | None = None,
    experimental_generator: ExperimentalHintGenerator | None = None,
    learner_exists: Callable[[UUID], bool] | None = None,
    policies: frozenset[str] = frozenset({POLICY}),
) -> tuple[ResearchTutorService, ArbitraryQuestionMapper]:
    mapper = mapper or ArbitraryQuestionMapper()
    assessments = SqlAlchemyTutorAssessmentRepository(session)
    history = SqlAlchemyTutorHistoryRepository(session)
    controlled = controlled or ControlledContext()
    assembler = TutorContextAssembler(
        learner_provider=controlled,
        mastery_provider=controlled,
        support_need_provider=controlled,
        assessment_provider=LedgerAssessmentEvidenceProvider(
            assessments,
            valid_skill_ids={"MAT-FRC"},
            eligible_scorer_sources={CONTROLLED_ANNOTATION_SOURCE},
            eligible_severity_policy_versions=policies,
            controlled_research=True,
        ),
        history_provider=TutorHistoryProvider(history),
        valid_skill_ids={"MAT-FRC"},
    )
    orchestrator = TutorOrchestrator(
        skill_mapper=mapper,
        skill_mapper_source=SOURCE,
        context_assembler=assembler,
        controller=ScaffoldingController(),
        llm_provider=DeterministicFakeLlmProvider(response="Try one careful step."),
        valid_skill_ids={"MAT-FRC"},
        curriculum_retriever=SyntheticCurriculumRetriever(),
        semantic_verifier=DeterministicFakeSemanticVerifier(passing_semantics()),
        trusted_answer_provider=SyntheticTrustedAnswerProvider(),
        semantic_verifier_is_simulated=True,
        decision_only=experimental_generator is not None,
    )
    return (
        ResearchTutorService(
            skill_mapper=mapper,
            orchestrator=orchestrator,
            assessments=assessments,
            history=history,
            eligible_severity_policy_versions=policies,
            lifetime=timedelta(minutes=5),
            experimental_generator=experimental_generator,
            learner_exists=learner_exists,
        ),
        mapper,
    )


def experimental_generator(
    client: RecordingGeminiClient,
) -> ExperimentalHintGenerator:
    return ExperimentalHintGenerator(
        GeminiLlmProvider(
            GeminiGenerationConfig(api_key="test-key", model="gemini-test"),
            client=client,
        ),
        "UNREVIEWED researcher-authored equivalent Fractions content.",
        lambda _learner_id: 5,
    )


def test_research_session_rejects_unknown_learner_before_question_processing() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service, _ = build_service(session, learner_exists=lambda _learner_id: False)

        with pytest.raises(ResearchSessionError, match="unknown research learner"):
            service.start(researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW)


def test_experimental_mode_invokes_gemini_and_keeps_draft_out_of_verified_field() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="en"))
        session.commit()
        client = RecordingGeminiClient()
        service, _ = build_service(
            session,
            experimental_generator=experimental_generator(client),
        )
        research, token = service.start(
            researcher_id=RESEARCHER_ID,
            learner_id=LEARNER_ID,
            now=NOW,
        )

        turn = service.ask(
            research.session_id,
            token,
            question="Explain equivalent fractions.",
            language="en",
            now=NOW,
        )

        assert len(client.models.calls) == 1
        assert turn.result.assistance_level.value == "L0"
        assert turn.result.response_text is None
        assert turn.result.status is TutorWorkflowStatus.DELIVERY_NOT_AUTHORIZED
        assert turn.experimental_generation is not None
        assert turn.experimental_generation.status is ExperimentalGenerationStatus.GENERATED
        assert turn.experimental_generation.provenance == EXPERIMENTAL_CURRICULUM_PROVENANCE
        assert turn.experimental_generation.text == "Try drawing equal parts first."
        response = ResearchInteractionResponse.from_turn(research.session_id, turn)
        assert response.delivery_authorized is False
        assert response.response_text is None
        assert response.experimental_response_text == "Try drawing equal parts first."
        assert "experimental_response_text" not in TutorApiResponse.model_fields
        call = client.models.calls[0]
        assert "selected L0" in call["config"]["system_instruction"]
        assert EXPERIMENTAL_CURRICULUM_PROVENANCE in call["contents"]

        next_turn = service.submit_attempt(
            research.session_id,
            token,
            turn.interaction_id,
            ResearchAttemptAnnotation(
                idempotency_key="experimental-attempt-1",
                is_correct=False,
                partial_credit=None,
                severity_category="RESEARCHER_ANNOTATED_ERROR",
                severity_value=0.7,
                severity_policy_version=POLICY,
                scoring_version="researcher-review-v1",
                item_rubric_version="controlled-item-v1",
                reviewer_confirmed=True,
            ),
            now=NOW + timedelta(seconds=1),
        )
        assert len(client.models.calls) == 2
        assert next_turn.result.assistance_level.value != "L0"
        assert next_turn.experimental_generation is not None


@pytest.mark.parametrize(
    ("mapper", "controlled"),
    (
        (AbstainingMapper(), ControlledContext()),
        (ArbitraryQuestionMapper(), MissingSupportContext()),
    ),
)
def test_experimental_mode_does_not_invoke_gemini_without_mapping_or_context(
    mapper: ArbitraryQuestionMapper,
    controlled: ControlledContext,
) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="en"))
        session.commit()
        client = RecordingGeminiClient()
        service, _ = build_service(
            session,
            mapper=mapper,
            controlled=controlled,
            experimental_generator=experimental_generator(client),
        )
        research, token = service.start(
            researcher_id=RESEARCHER_ID,
            learner_id=LEARNER_ID,
            now=NOW,
        )

        turn = service.ask(
            research.session_id,
            token,
            question="Help with this.",
            language="en",
            now=NOW,
        )

        assert turn.experimental_generation is None
        assert client.models.calls == []


def test_mocked_complete_question_attempt_and_next_decision_flow() -> None:
    """MOCKED integration: no model, verifier, or external provider call is real."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="en"))
        session.commit()
        service, mapper = build_service(session)
        research, token = service.start(
            researcher_id=RESEARCHER_ID,
            learner_id=LEARNER_ID,
            now=NOW,
        )

        first = service.ask(
            research.session_id,
            token,
            question="Why is one half the same as two quarters?",
            language="en",
            now=NOW,
        )
        annotation = ResearchAttemptAnnotation(
            idempotency_key="research-attempt-1",
            is_correct=False,
            partial_credit=0.25,
            severity_category="MAJOR_CONCEPTUAL",
            severity_value=0.7,
            severity_policy_version=POLICY,
            scoring_version="researcher-review-v1",
            item_rubric_version="controlled-item-v1",
            reviewer_confirmed=True,
        )
        second = service.submit_attempt(
            research.session_id,
            token,
            first.interaction_id,
            annotation,
            now=NOW + timedelta(seconds=1),
        )
        replay = service.submit_attempt(
            research.session_id,
            token,
            first.interaction_id,
            annotation,
            now=NOW + timedelta(seconds=2),
        )

        assert mapper.questions == ["Why is one half the same as two quarters?"]
        assert first.result.assistance_level.value == "L0"
        assert second.result.assistance_level.value != first.result.assistance_level.value
        assert replay == second
        assert second.result.response_text is None
        assert second.result.status is TutorWorkflowStatus.SIMULATED_VERIFICATION_PASS
        assert second.result.execution_origin.value == "MIXED"
        assert second.result.curriculum_status.value == "FOUND"
        assert second.result.verification_simulated is True
        attempts = session.scalars(select(TutorAssessmentAttemptModel)).all()
        assert len(attempts) == 1
        assert attempts[0].status == "ACCEPTED"
        events = session.scalars(select(TutorInteractionEventModel)).all()
        # The post-attempt decision is recorded too. Nothing was shown to the researcher in
        # this simulated-verifier flow, so there is no presentation or effectiveness event.
        assert [event.event_type for event in events] == [
            TutorHistoryEventType.ASSISTANCE_SELECTED.value,
            TutorHistoryEventType.OUTCOME_OBSERVED.value,
            TutorHistoryEventType.ASSISTANCE_SELECTED.value,
        ]
        with pytest.raises(ValueError, match="conflicting"):
            service.submit_attempt(
                research.session_id,
                token,
                first.interaction_id,
                replace(annotation, severity_value=0.9),
                now=NOW + timedelta(seconds=2),
            )

        next_question = service.ask(
            research.session_id,
            token,
            question="What is a unit fraction?",
            language="en",
            now=NOW + timedelta(seconds=3),
        )
        assert next_question.interaction_sequence == 2
        assert next_question.result.assistance_level.value == "L0"
        assert mapper.questions[-1] == "What is a unit fraction?"

        other, other_token = service.start(
            researcher_id=RESEARCHER_ID,
            learner_id=LEARNER_ID,
            now=NOW,
        )
        try:
            service.submit_attempt(
                other.session_id,
                other_token,
                first.interaction_id,
                replace(annotation, idempotency_key="cross-session"),
                now=NOW + timedelta(seconds=2),
            )
        except ResearchSessionError:
            pass
        else:
            raise AssertionError("cross-session attempt was accepted")

        with pytest.raises(ResearchSessionError, match="expired"):
            service.ask(
                research.session_id,
                token,
                question="This session has expired.",
                language="en",
                now=NOW + timedelta(minutes=6),
            )


class FailingGeminiModels(RecordingGeminiModels):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        raise self.error


class FailingGeminiClient(RecordingGeminiClient):
    def __init__(self, error: Exception) -> None:
        self.models = FailingGeminiModels(error)


class NotFoundSdkError(Exception):
    code = 404


def test_experimental_provider_failure_exposes_only_sanitized_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "do-not-expose-provider-detail"
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="en"))
        session.commit()
        client = FailingGeminiClient(NotFoundSdkError(secret))
        service, _ = build_service(
            session,
            experimental_generator=experimental_generator(client),
        )
        research, token = service.start(
            researcher_id=RESEARCHER_ID,
            learner_id=LEARNER_ID,
            now=NOW,
        )

        turn = service.ask(
            research.session_id,
            token,
            question="Explain equivalent fractions.",
            language="en",
            now=NOW,
        )

        response = ResearchInteractionResponse.from_turn(research.session_id, turn)
        assert (
            response.experimental_generation_status is ExperimentalGenerationStatus.PROVIDER_ERROR
        )
        assert response.experimental_provider_reason_code is ProviderFailureReason.MODEL_NOT_FOUND
        assert response.experimental_response_text is None
        assert response.response_text is None
        assert response.delivery_authorized is False
        assert secret not in response.model_dump_json()
        assert "MODEL_NOT_FOUND" in caplog.text
        assert secret not in caplog.text
        assert "equivalent fractions" not in caplog.text


def test_experimental_missing_sdk_is_unavailable_not_generic_provider_error() -> None:
    def missing_sdk(_config: GeminiGenerationConfig) -> object:
        raise LlmProviderUnavailableError(
            "sdk missing", reason=ProviderFailureReason.PROVIDER_SDK_NOT_INSTALLED
        )

    generator = ExperimentalHintGenerator(
        GeminiLlmProvider(
            GeminiGenerationConfig(api_key="test-key", model="gemini-test"),
            client_factory=missing_sdk,
        ),
        "UNREVIEWED researcher-authored equivalent Fractions content.",
        lambda _learner_id: 5,
    )

    result = generator.generate(
        learner_id=LEARNER_ID,
        question="Explain equivalent fractions.",
        language="en",
        assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
        skill_id="MAT-FRC",
    )

    assert result.status is ExperimentalGenerationStatus.PROVIDER_UNAVAILABLE
    assert result.provider_reason is ProviderFailureReason.PROVIDER_SDK_NOT_INSTALLED
    assert result.text is None


def test_successful_experimental_response_has_no_failure_reason() -> None:
    result = experimental_generator(RecordingGeminiClient()).generate(
        learner_id=LEARNER_ID,
        question="Explain equivalent fractions.",
        language="en",
        assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
        skill_id="MAT-FRC",
    )

    assert result.status is ExperimentalGenerationStatus.GENERATED
    assert result.provider_reason is None


class FailingGeminiForPresentation(RecordingGeminiModels):
    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        raise RuntimeError("provider detail")


def reviewed(
    key: str,
    *,
    correct: bool = False,
    severity: float = 0.7,
    policy: str = POLICY,
) -> ResearchAttemptAnnotation:
    return ResearchAttemptAnnotation(
        idempotency_key=key,
        is_correct=correct,
        partial_credit=None,
        severity_category="CORRECT" if correct else "RESEARCHER_ANNOTATED_ERROR",
        severity_value=0.0 if correct else severity,
        severity_policy_version=policy,
        scoring_version="researcher-review-v1",
        item_rubric_version="controlled-item-v1",
        reviewer_confirmed=True,
    )


def research_engine() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="en"))
    session.commit()
    return session


def history_provenance(turn: object) -> object:
    return next(
        item
        for item in turn.result.context_provenance  # type: ignore[attr-defined]
        if item.input.value == "ASSISTANCE_HISTORY"
    )


def effectiveness_statuses(session: Session) -> list[str]:
    return [
        row.status
        for row in session.scalars(
            select(TutorInteractionEventModel)
            .where(
                TutorInteractionEventModel.event_type
                == TutorHistoryEventType.EFFECTIVENESS_STATUS_RECORDED.value
            )
            .order_by(TutorInteractionEventModel.event_sequence)
        ).all()
    ]


def test_research_loop_escalates_maintains_and_fades_from_presented_history() -> None:
    """MOCKED provider, REAL Controller V1 and persistence: transitions follow the policy only."""

    with research_engine() as session:
        client = RecordingGeminiClient()
        service, _ = build_service(session, experimental_generator=experimental_generator(client))
        research, token = service.start(researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW)
        first = service.ask(
            research.session_id,
            token,
            question="Explain equivalent fractions.",
            language="en",
            now=NOW,
        )
        assert first.result.assistance_level is AssistanceLevel.INDEPENDENT_RETRY

        # (annotation, expected level, reason codes that must be present)
        steps = [
            (reviewed("a1"), AssistanceLevel.CONCEPTUAL_HINT, {"MINIMUM_SUFFICIENT_ASSISTANCE"}),
            (
                reviewed("a2"),
                AssistanceLevel.CONCEPTUAL_HINT,
                {"PREVIOUS_HINT_INEFFECTIVE", "SUPPORT_MAINTAINED"},
            ),
            (
                reviewed("a3"),
                AssistanceLevel.TARGETED_HINT,
                {"PREVIOUS_HINT_INEFFECTIVE", "ESCALATION_JUSTIFIED"},
            ),
            (
                reviewed("a4", severity=0.3),
                AssistanceLevel.CONCEPTUAL_HINT,
                {"PREVIOUS_HINT_EFFECTIVE", "FADING_JUSTIFIED"},
            ),
            (
                reviewed("a5", correct=True),
                AssistanceLevel.INDEPENDENT_RETRY,
                {"SUCCESS_AFTER_ASSISTANCE", "FADING_JUSTIFIED"},
            ),
        ]
        for offset, (annotation, level, reasons) in enumerate(steps, start=1):
            turn = service.submit_attempt(
                research.session_id,
                token,
                first.interaction_id,
                annotation,
                now=NOW + timedelta(seconds=offset),
            )
            codes = {code.value for code in turn.result.controller_reason_codes}
            assert turn.result.assistance_level is level, annotation.idempotency_key
            assert reasons <= codes, (annotation.idempotency_key, codes)
            assert turn.result.response_text is None
            assert turn.result.status is TutorWorkflowStatus.DELIVERY_NOT_AUTHORIZED
            assert turn.experimental_generation is not None
            assert turn.experimental_generation.status is ExperimentalGenerationStatus.GENERATED

        assert effectiveness_statuses(session) == [
            "INEFFECTIVE",
            "INEFFECTIVE",
            "EFFECTIVE",
            "EFFECTIVE",
        ]
        delivered = session.scalars(
            select(TutorInteractionEventModel).where(
                TutorInteractionEventModel.event_type
                == TutorHistoryEventType.RESPONSE_DELIVERED.value
            )
        ).all()
        assert delivered == []


def test_presented_history_is_synthetic_and_cannot_make_execution_real() -> None:
    with research_engine() as session:
        service, _ = build_service(
            session, experimental_generator=experimental_generator(RecordingGeminiClient())
        )
        research, token = service.start(researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW)
        first = service.ask(
            research.session_id, token, question="Fractions?", language="en", now=NOW
        )
        service.submit_attempt(
            research.session_id, token, first.interaction_id, reviewed("b1"), now=NOW
        )
        second = service.submit_attempt(
            research.session_id,
            token,
            first.interaction_id,
            reviewed("b2"),
            now=NOW + timedelta(seconds=1),
        )

        provenance = history_provenance(second)
        assert provenance.origin is EvidenceOrigin.SYNTHETIC
        assert provenance.source_id == "adaptive-tutor:interaction-history-research-presentation"
        assert second.result.execution_origin.value != "REAL"
        response = ResearchInteractionResponse.from_turn(research.session_id, second)
        assert response.delivery_authorized is False
        assert response.response_text is None


def test_without_a_presented_hint_each_decision_restarts_from_initial_selection() -> None:
    with research_engine() as session:
        client = RecordingGeminiClient()
        client.models = FailingGeminiForPresentation()
        service, _ = build_service(session, experimental_generator=experimental_generator(client))
        research, token = service.start(researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW)
        first = service.ask(
            research.session_id, token, question="Fractions?", language="en", now=NOW
        )

        turns = [
            service.submit_attempt(
                research.session_id,
                token,
                first.interaction_id,
                reviewed(key),
                now=NOW + timedelta(seconds=index),
            )
            for index, key in enumerate(("c1", "c2", "c3"), start=1)
        ]

        for turn in turns:
            codes = {code.value for code in turn.result.controller_reason_codes}
            assert turn.result.assistance_level is AssistanceLevel.CONCEPTUAL_HINT
            assert "MINIMUM_SUFFICIENT_ASSISTANCE" in codes
            assert not codes & {"PREVIOUS_HINT_EFFECTIVE", "PREVIOUS_HINT_INEFFECTIVE"}
        assert effectiveness_statuses(session) == []
        presentations = session.scalars(
            select(TutorInteractionEventModel).where(
                TutorInteractionEventModel.event_type
                == TutorHistoryEventType.RESEARCH_PRESENTATION.value
            )
        ).all()
        assert presentations == []


def test_incomparable_feedback_is_recorded_as_insufficient_and_maintains_the_level() -> None:
    other = "controlled-research-severity-v2"
    with research_engine() as session:
        service, _ = build_service(
            session,
            experimental_generator=experimental_generator(RecordingGeminiClient()),
            policies=frozenset({POLICY, other}),
        )
        research, token = service.start(researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW)
        first = service.ask(
            research.session_id, token, question="Fractions?", language="en", now=NOW
        )
        service.submit_attempt(
            research.session_id, token, first.interaction_id, reviewed("d1"), now=NOW
        )

        second = service.submit_attempt(
            research.session_id,
            token,
            first.interaction_id,
            reviewed("d2", severity=0.2, policy=other),
            now=NOW + timedelta(seconds=1),
        )

        codes = {code.value for code in second.result.controller_reason_codes}
        assert effectiveness_statuses(session) == ["INSUFFICIENT_EVIDENCE"]
        assert second.result.assistance_level is AssistanceLevel.CONCEPTUAL_HINT
        assert {"PREVIOUS_HINT_EFFECTIVENESS_UNKNOWN", "SUPPORT_MAINTAINED"} <= codes


def test_duplicate_attempt_replays_without_new_history_events() -> None:
    with research_engine() as session:
        service, _ = build_service(
            session, experimental_generator=experimental_generator(RecordingGeminiClient())
        )
        research, token = service.start(researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW)
        first = service.ask(
            research.session_id, token, question="Fractions?", language="en", now=NOW
        )
        service.submit_attempt(
            research.session_id, token, first.interaction_id, reviewed("e1"), now=NOW
        )
        original = service.submit_attempt(
            research.session_id,
            token,
            first.interaction_id,
            reviewed("e2"),
            now=NOW + timedelta(seconds=1),
        )
        count = len(session.scalars(select(TutorInteractionEventModel)).all())

        replay = service.submit_attempt(
            research.session_id,
            token,
            first.interaction_id,
            reviewed("e2"),
            now=NOW + timedelta(seconds=2),
        )

        assert replay == original
        assert len(session.scalars(select(TutorInteractionEventModel)).all()) == count
        assert effectiveness_statuses(session) == ["INEFFECTIVE"]


def test_research_sessions_do_not_share_assistance_history() -> None:
    with research_engine() as session:
        service, _ = build_service(
            session, experimental_generator=experimental_generator(RecordingGeminiClient())
        )
        first_session, first_token = service.start(
            researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW
        )
        first = service.ask(
            first_session.session_id, first_token, question="Fractions?", language="en", now=NOW
        )
        for index, key in enumerate(("f1", "f2", "f3"), start=1):
            escalated = service.submit_attempt(
                first_session.session_id,
                first_token,
                first.interaction_id,
                reviewed(key),
                now=NOW + timedelta(seconds=index),
            )
        assert escalated.result.assistance_level is AssistanceLevel.TARGETED_HINT

        other_session, other_token = service.start(
            researcher_id=RESEARCHER_ID, learner_id=LEARNER_ID, now=NOW
        )
        other = service.ask(
            other_session.session_id, other_token, question="Fractions?", language="en", now=NOW
        )
        fresh = service.submit_attempt(
            other_session.session_id,
            other_token,
            other.interaction_id,
            reviewed("g1"),
            now=NOW + timedelta(seconds=5),
        )

        codes = {code.value for code in fresh.result.controller_reason_codes}
        assert fresh.result.assistance_level is AssistanceLevel.CONCEPTUAL_HINT
        assert "MINIMUM_SUFFICIENT_ASSISTANCE" in codes
        assert history_provenance(fresh).status != "AVAILABLE"

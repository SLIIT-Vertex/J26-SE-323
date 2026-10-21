from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.application import (
    AssessmentEvidenceResult,
    ContextEvidenceOrigin,
    ContextEvidenceRequest,
    ContextReadinessReason,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    SkillMappingResult,
    SupportNeedResult,
    TutorContextAssembler,
)
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure import (
    AssessmentAttemptStatus,
    AssessmentAttemptWrite,
    LedgerAssessmentEvidenceProvider,
    RealDataControllerShadow,
    ShadowControllerRequest,
    ShadowExecutionStatus,
    SqlAlchemyTutorAssessmentRepository,
    SqlAlchemyTutorHistoryRepository,
    StaticShadowAuthorizer,
    TutorAssessmentInteraction,
    TutorHistoryEvent,
    TutorHistoryEventStatus,
    TutorHistoryEventType,
    TutorHistoryProvider,
    TutorInteractionEventModel,
    UnresolvedAssessmentEvidenceProvider,
)
from app.knowledge_tracing.application.mastery import (
    MasteryResult,
    MasteryStatus,
)
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.model import LearnerModel

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000091")
PRINCIPAL_ID = UUID("00000000-0000-4000-8000-000000000092")
UNAUTHORIZED_ID = UUID("00000000-0000-4000-8000-000000000093")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000094")
CORRELATION_ID = UUID("00000000-0000-4000-8000-000000000095")
ASSESSMENT_INTERACTION_ID = UUID("00000000-0000-4000-8000-000000000096")
AS_OF = datetime(2026, 10, 18, 11, 0, tzinfo=UTC)
REAL_SOURCE = EvidenceSource(source_id="test:real-skill-mapper", origin=EvidenceOrigin.REAL)
SYNTHETIC_SOURCE = EvidenceSource(
    source_id="test:controlled-assessment",
    origin=EvidenceOrigin.SYNTHETIC,
)


class MappingStub:
    def __init__(self, result: SkillMappingResult) -> None:
        self.result = result
        self.calls = 0

    def map(self, request: object) -> SkillMappingResult:
        self.calls += 1
        return self.result


class RealContextStubs:
    source = EvidenceSource(source_id="test:real-context", origin=EvidenceOrigin.REAL)

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult:
        return LearnerLookupResult(
            status=EvidenceStatus.AVAILABLE,
            learner=Learner(id=learner_id, grade=5, preferred_language="si"),
        )

    def get_mastery(self, request: object) -> MasteryResult:
        return MasteryResult(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
            status=MasteryStatus.AVAILABLE,
            mastery=0.6,
        )

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        return SupportNeedResult(status=EvidenceStatus.AVAILABLE, support_need=0.4)


class ControlledAssessment:
    source = SYNTHETIC_SOURCE

    def __init__(self, result: AssessmentEvidenceResult) -> None:
        self.result = result

    def get_assessment_evidence(self, request: ContextEvidenceRequest) -> AssessmentEvidenceResult:
        return self.result


def matched() -> SkillMappingResult:
    return SkillMappingResult(
        status=SkillMappingStatus.MATCHED,
        intent=LearningIntent.EXPLANATION_REQUEST,
        skill_id="MAT-FRC",
        confidence=0.9,
        clarification_needed=False,
    )


def request(
    *,
    principal_id: UUID = PRINCIPAL_ID,
    session_id: UUID = SESSION_ID,
    correlation_id: UUID = CORRELATION_ID,
) -> ShadowControllerRequest:
    return ShadowControllerRequest(
        correlation_id=correlation_id,
        principal_id=principal_id,
        learner_id=LEARNER_ID,
        student_message="Explain this fraction question.",
        preferred_language="en",
        session_id=session_id,
        interaction_id=str(ASSESSMENT_INTERACTION_ID),
        interaction_sequence=1,
        as_of=AS_OF,
        max_age_ms=60_000,
    )


def build_shadow(
    session: Session,
    *,
    mapper: MappingStub,
    assessment: object,
) -> RealDataControllerShadow:
    real = RealContextStubs()
    repository = SqlAlchemyTutorHistoryRepository(session)
    assembler = TutorContextAssembler(
        learner_provider=real,
        mastery_provider=real,
        support_need_provider=real,
        assessment_provider=assessment,
        history_provider=TutorHistoryProvider(repository),
        valid_skill_ids={"MAT-FRC"},
    )
    return RealDataControllerShadow(
        authorizer=StaticShadowAuthorizer({(PRINCIPAL_ID, LEARNER_ID)}),
        skill_mapper=mapper,
        skill_mapper_source=REAL_SOURCE,
        context_assembler=assembler,
        history_repository=repository,
        valid_skill_ids={"MAT-FRC"},
    )


def database_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="si"))
    session.commit()
    return session


def ledger_provider(
    session: Session, *, completed: bool = False
) -> LedgerAssessmentEvidenceProvider:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(
        TutorAssessmentInteraction(
            interaction_id=ASSESSMENT_INTERACTION_ID,
            idempotency_key="shadow-controlled-interaction",
            learner_id=LEARNER_ID,
            session_id=SESSION_ID,
            skill_id="MAT-FRC",
            interaction_sequence=1,
            source_component="controlled-item-bank",
            question_reference="controlled-question-1",
            question_version="synthetic-v1",
            authorization_reference="controlled-shadow-authorization",
            opened_at=AS_OF - timedelta(minutes=1),
            provenance="DESIGN_AUTHORED_SYNTHETIC",
        )
    )
    if completed:
        repository.record_attempt(
            AssessmentAttemptWrite(
                attempt_id=uuid4(),
                interaction_id=ASSESSMENT_INTERACTION_ID,
                idempotency_key="shadow-controlled-attempt",
                status=AssessmentAttemptStatus.ACCEPTED,
                source_component="controlled-scorer",
                source_score_reference="controlled-score-1",
                scorer_authorized=True,
                source_mapping_approved=True,
                is_correct=False,
                scoring_version="synthetic-scorer-v1",
                item_rubric_version="synthetic-item-v1",
                severity_category="PARTIAL_CONCEPTUAL",
                severity_value=0.45,
                severity_policy_version="PROPOSED-synthetic-severity-v1",
                severity_reviewed=True,
                observed_at=AS_OF - timedelta(seconds=10),
                accepted_at=AS_OF - timedelta(seconds=5),
                recorded_at=AS_OF - timedelta(seconds=6),
                provenance="DESIGN_AUTHORED_SYNTHETIC",
            )
        )
    return LedgerAssessmentEvidenceProvider(
        repository,
        valid_skill_ids={"MAT-FRC"},
        eligible_scorer_sources={"controlled-scorer"},
        eligible_severity_policy_versions={"PROPOSED-synthetic-severity-v1"},
        controlled_research=True,
    )


def test_unresolved_real_assessment_blocks_controller_shadow() -> None:
    with database_session() as session:
        shadow = build_shadow(
            session,
            mapper=MappingStub(matched()),
            assessment=UnresolvedAssessmentEvidenceProvider(),
        )

        result = shadow.run(request())

        assert result.status is ShadowExecutionStatus.NOT_READY
        assert {issue.reason for issue in result.context_issues} == {
            ContextReadinessReason.ASSESSMENT_POLICY_UNRESOLVED
        }
        assert session.scalars(select(TutorInteractionEventModel)).all() == []


def test_controlled_preinteraction_can_exercise_controller_but_stays_mixed() -> None:
    with database_session() as session:
        shadow = build_shadow(
            session,
            mapper=MappingStub(matched()),
            assessment=ControlledAssessment(
                AssessmentEvidenceResult(
                    status=EvidenceStatus.NOT_YET_OBSERVED,
                    attempt_count=0,
                )
            ),
        )

        first = shadow.run(request())
        second = shadow.run(request())

        assert first == second
        assert first.status is ShadowExecutionStatus.DECIDED
        assert first.assistance_level.value == "L0"
        assert first.evidence_origin is ContextEvidenceOrigin.MIXED
        assert first.controller_policy_version == "reference-policy-v1"
        assert len(session.scalars(select(TutorInteractionEventModel)).all()) == 1
        assert "response_text" not in type(first).model_fields
        assert "student_message" not in type(first).model_fields


def test_persisted_zero_attempt_shadow_is_deterministic_real_and_idempotent() -> None:
    with database_session() as session:
        shadow = build_shadow(
            session,
            mapper=MappingStub(matched()),
            assessment=ledger_provider(session),
        )

        first = shadow.run(request())
        second = shadow.run(request())

        assert first == second
        assert first.status is ShadowExecutionStatus.DECIDED
        assert first.assistance_level.value == "L0"
        assert first.evidence_origin is ContextEvidenceOrigin.REAL
        assert len(session.scalars(select(TutorInteractionEventModel)).all()) == 1


def test_persisted_controlled_attempt_reaches_controller_without_becoming_real() -> None:
    with database_session() as session:
        assessment = ledger_provider(session, completed=True)
        shadow = build_shadow(
            session,
            mapper=MappingStub(matched()),
            assessment=assessment,
        )

        result = shadow.run(request())
        evidence = assessment.get_assessment_evidence(
            ContextEvidenceRequest(
                learner_id=LEARNER_ID,
                skill_id="MAT-FRC",
                session_id=str(SESSION_ID),
                interaction_id=str(ASSESSMENT_INTERACTION_ID),
                interaction_sequence=1,
                as_of=AS_OF,
            )
        )
        assert evidence.assessment_reference is not None
        linked, created = SqlAlchemyTutorHistoryRepository(session).append(
            TutorHistoryEvent(
                event_id=uuid4(),
                idempotency_key="shadow-controlled-outcome-link",
                decision_id=CORRELATION_ID,
                learner_id=LEARNER_ID,
                skill_id="MAT-FRC",
                session_id=SESSION_ID,
                interaction_id=str(ASSESSMENT_INTERACTION_ID),
                interaction_sequence=1,
                event_sequence=2,
                event_type=TutorHistoryEventType.OUTCOME_OBSERVED,
                occurred_at=AS_OF,
                provenance="controlled-shadow-outcome-link",
                status=TutorHistoryEventStatus.OBSERVED,
                assessment_reference=evidence.assessment_reference,
            )
        )

        assert result.status is ShadowExecutionStatus.DECIDED
        assert result.evidence_origin is ContextEvidenceOrigin.MIXED
        assert result.assistance_level is not None
        assert created is True
        assert linked.assessment_reference == evidence.assessment_reference
        assert linked.event_type is TutorHistoryEventType.OUTCOME_OBSERVED
        assert "response_text" not in type(result).model_fields


def test_persisted_assessment_wrong_session_stops_before_controller_and_history() -> None:
    with database_session() as session:
        shadow = build_shadow(
            session,
            mapper=MappingStub(matched()),
            assessment=ledger_provider(session),
        )

        result = shadow.run(request(session_id=UUID(int=999)))

        assert result.status is ShadowExecutionStatus.NOT_READY
        assert {issue.reason for issue in result.context_issues} == {
            ContextReadinessReason.ASSESSMENT_SESSION_MISMATCH
        }
        assert session.scalars(select(TutorInteractionEventModel)).all() == []


def test_unauthorized_request_stops_before_mapping_and_storage() -> None:
    with database_session() as session:
        mapper = MappingStub(matched())
        shadow = build_shadow(
            session,
            mapper=mapper,
            assessment=UnresolvedAssessmentEvidenceProvider(),
        )

        result = shadow.run(request(principal_id=UNAUTHORIZED_ID))

        assert result.status is ShadowExecutionStatus.UNAUTHORIZED
        assert mapper.calls == 0
        assert session.scalars(select(TutorInteractionEventModel)).all() == []


def test_skill_mapper_abstention_stops_before_context_and_storage() -> None:
    with database_session() as session:
        mapper = MappingStub(
            SkillMappingResult(
                status=SkillMappingStatus.AMBIGUOUS,
                intent=LearningIntent.EXPLANATION_REQUEST,
                clarification_needed=True,
                clarification_question="Which topic do you mean?",
            )
        )
        shadow = build_shadow(
            session,
            mapper=mapper,
            assessment=UnresolvedAssessmentEvidenceProvider(),
        )

        result = shadow.run(request())

        assert result.status is ShadowExecutionStatus.SKILL_NOT_CONFIRMED
        assert session.scalars(select(TutorInteractionEventModel)).all() == []


def test_shadow_composition_has_no_generation_or_verification_dependency() -> None:
    parameters = set(RealDataControllerShadow.__init__.__annotations__)

    assert "llm_provider" not in parameters
    assert "semantic_verifier" not in parameters

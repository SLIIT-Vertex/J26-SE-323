from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.application import (
    AssessmentEvidenceResult,
    AssistanceHistoryResult,
    ContextEvidenceOrigin,
    ContextEvidenceRequest,
    ContextInput,
    ContextReadinessReason,
    ContextReadinessStatus,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    ScaffoldingController,
    SkillMappingResult,
    SupportNeedResult,
    TutorContextAssembler,
    TutorContextAssemblyRequest,
)
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure import (
    KnowledgeTracingMasteryProvider,
    LearnerStateSupportNeedProvider,
    SharedLearnerProvider,
    XlsxSkillTaxonomyCatalog,
)
from app.knowledge_tracing.application.mastery import MasteryRetrievalRequest, MasteryStatus
from app.knowledge_tracing.application.mastery_service import (
    MasteryService,
    ModelUnavailableError,
)
from app.knowledge_tracing.domain.feature_spec import load_feature_spec
from app.knowledge_tracing.domain.mastery import MasterySnapshot, SkillEstimate
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    MasterySnapshotModel,
    QuestionModel,
    SkillModel,
)
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel
from app.learner_state.application.support_need import (
    LearnerSkillState,
    StoredSupportNeedProvider,
    SupportNeedStatus,
)
from app.learner_state.application.support_need import (
    SupportNeedResult as LearnerStateSupportNeedResult,
)
from app.learner_state.infrastructure.db.models import LearnerSkillStateModel
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.model import LearnerModel
from app.shared.learner.repository import SqlAlchemyLearnerRepository
from app.shared.learner.service import LearnerNotFoundError, LearnerService

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
TAXONOMY_PATH = REPOSITORY_ROOT / "docs/skill_nodes.xlsx"
FEATURE_SPEC_PATH = REPOSITORY_ROOT / "shared/feature_spec.json"
WEIGHTS_PATH = (
    BACKEND_ROOT / "app/knowledge_tracing/infrastructure/ml/weights/mindbridge_dkt_v2_best.pt"
)
LEARNER_ID = UUID("00000000-0000-4000-8000-000000000011")
OTHER_LEARNER_ID = UUID("00000000-0000-4000-8000-000000000012")
SKILL_ID = "MAT-FRC"
OTHER_SKILL_ID = "MAT-OPS"
OBSERVED_AT = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)
ASSEMBLY_AS_OF = OBSERVED_AT + timedelta(seconds=30)
SESSION_ID = "trusted-tutor-session"
CONTROLLED_SOURCE = EvidenceSource(
    source_id="test:controlled-context-evidence",
    origin=EvidenceOrigin.SYNTHETIC,
)


class StubLearnerService:
    def __init__(
        self,
        learner: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.learner = learner
        self.error = error
        self.requested_ids: list[UUID] = []

    def get(self, learner_id: UUID) -> object:
        self.requested_ids.append(learner_id)
        if self.error is not None:
            raise self.error
        return self.learner


class StubMasteryService:
    def __init__(
        self,
        snapshot: MasterySnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.requested_ids: list[UUID] = []

    def current(self, learner_id: UUID) -> MasterySnapshot:
        self.requested_ids.append(learner_id)
        if self.error is not None:
            raise self.error
        assert self.snapshot is not None
        return self.snapshot


class StubLearnerStateProvider:
    def __init__(
        self,
        result: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def get_support_need(self, request: object) -> object:
        if self.error is not None:
            raise self.error
        return self.result


class ControlledRemainingProviders:
    """Explicit test evidence for the three providers not integrated in AT-17BC."""

    source = CONTROLLED_SOURCE

    def __init__(self) -> None:
        self.requests: list[ContextEvidenceRequest] = []

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        self.requests.append(request)
        return SupportNeedResult(status=EvidenceStatus.AVAILABLE, support_need=0.4)

    def get_assessment_evidence(
        self,
        request: ContextEvidenceRequest,
    ) -> AssessmentEvidenceResult:
        self.requests.append(request)
        return AssessmentEvidenceResult(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=1,
            is_correct=False,
            error_severity=0.3,
        )

    def get_assistance_history(
        self,
        request: ContextEvidenceRequest,
    ) -> AssistanceHistoryResult:
        self.requests.append(request)
        return AssistanceHistoryResult(status=EvidenceStatus.NOT_YET_OBSERVED)


def learner(
    *,
    learner_id: UUID = LEARNER_ID,
    grade: int = 5,
    language: str = "si",
) -> Learner:
    return Learner(id=learner_id, grade=grade, preferred_language=language)


def snapshot(
    mastery: float | None = 0.625,
    *,
    learner_id: UUID = LEARNER_ID,
) -> MasterySnapshot:
    return MasterySnapshot(
        id=1,
        learner_id=learner_id,
        computed_at=OBSERVED_AT,
        model_version="dkt-v2.1-test",
        n_attempts=3,
        skills=(SkillEstimate(SKILL_ID, mastery, 3),),
    )


def learner_state_result(
    status: SupportNeedStatus = SupportNeedStatus.AVAILABLE,
    *,
    learner_id: UUID = LEARNER_ID,
    skill_id: str = SKILL_ID,
    session_id: str = SESSION_ID,
    support_need: float | None = 0.4,
) -> LearnerStateSupportNeedResult:
    if status is not SupportNeedStatus.AVAILABLE:
        support_need = None
    return LearnerStateSupportNeedResult(
        learner_id=learner_id,
        skill_id=skill_id,
        status=status,
        support_need=support_need,
        observed_at=OBSERVED_AT,
        session_id=session_id,
    )


def learner_provider(service: StubLearnerService) -> SharedLearnerProvider:
    return SharedLearnerProvider(service)  # type: ignore[arg-type]


def mastery_provider(service: StubMasteryService) -> KnowledgeTracingMasteryProvider:
    return KnowledgeTracingMasteryProvider(service, {SKILL_ID, OTHER_SKILL_ID})  # type: ignore[arg-type]


def assembly_request(
    *,
    learner_id: UUID = LEARNER_ID,
    skill_id: str = SKILL_ID,
    session_id: str | None = None,
    as_of: datetime | None = None,
    max_age_ms: int | None = None,
) -> TutorContextAssemblyRequest:
    return TutorContextAssemblyRequest(
        learner_id=learner_id,
        skill_mapping=SkillMappingResult(
            status=SkillMappingStatus.MATCHED,
            intent=LearningIntent.EXPLANATION_REQUEST,
            skill_id=skill_id,
            confidence=0.9,
            clarification_needed=False,
        ),
        skill_mapping_source=CONTROLLED_SOURCE,
        session_id=session_id,
        as_of=as_of,
        max_age_ms=max_age_ms,
    )


def assembler(
    learner_service: StubLearnerService,
    mastery_service: StubMasteryService,
    remaining: ControlledRemainingProviders | None = None,
    support_need_provider: object | None = None,
) -> TutorContextAssembler:
    controlled = remaining or ControlledRemainingProviders()
    return TutorContextAssembler(
        learner_provider=learner_provider(learner_service),
        mastery_provider=mastery_provider(mastery_service),
        support_need_provider=support_need_provider or controlled,
        assessment_provider=controlled,
        history_provider=controlled,
        valid_skill_ids={SKILL_ID, OTHER_SKILL_ID},
    )


def reasons(result: object) -> set[ContextReadinessReason]:
    return {issue.reason for issue in result.issues}


@pytest.mark.parametrize(("grade", "language"), [(4, "en"), (5, "si"), (5, "ta")])
def test_shared_learner_adapter_preserves_supported_profile(
    grade: int,
    language: str,
) -> None:
    expected = learner(grade=grade, language=language)
    service = StubLearnerService(expected)
    adapter = learner_provider(service)

    result = adapter.get_learner(LEARNER_ID)

    assert result.status is EvidenceStatus.AVAILABLE
    assert result.learner is expected
    assert result.learner.grade == grade
    assert result.learner.preferred_language == language
    assert service.requested_ids == [LEARNER_ID]
    assert adapter.source.origin is EvidenceOrigin.REAL
    assert adapter.source.source_id == "shared-learner:learner-service"


def test_shared_learner_adapter_maps_missing_learner() -> None:
    result = learner_provider(
        StubLearnerService(error=LearnerNotFoundError(LEARNER_ID))
    ).get_learner(LEARNER_ID)

    assert result.status is EvidenceStatus.NOT_FOUND
    assert result.learner is None


@pytest.mark.parametrize(
    "invalid_learner",
    [
        learner(learner_id=OTHER_LEARNER_ID),
        learner(grade=6),
        learner(language="Singlish"),
        object(),
    ],
    ids=["identity-mismatch", "unsupported-grade", "unsupported-language", "malformed"],
)
def test_shared_learner_adapter_rejects_invalid_profile(invalid_learner: object) -> None:
    result = learner_provider(StubLearnerService(invalid_learner)).get_learner(LEARNER_ID)

    assert result.status is EvidenceStatus.INVALID_EVIDENCE
    assert result.learner is None


@pytest.mark.parametrize("error", [SQLAlchemyError("database failed"), RuntimeError("failed")])
def test_shared_learner_adapter_maps_provider_failures(error: Exception) -> None:
    result = learner_provider(StubLearnerService(error=error)).get_learner(LEARNER_ID)

    assert result.status is EvidenceStatus.PROVIDER_ERROR
    assert result.learner is None


def test_both_real_adapters_make_controlled_context_ready() -> None:
    learner_service = StubLearnerService(learner(grade=4, language="ta"))
    mastery_service = StubMasteryService(snapshot(0.625))
    remaining = ControlledRemainingProviders()

    result = assembler(learner_service, mastery_service, remaining).assemble(assembly_request())

    assert result.status is ContextReadinessStatus.READY
    assert result.learner_grade == 4
    assert result.context is not None
    assert result.context.learner_id == LEARNER_ID
    assert result.context.skill_id == SKILL_ID
    assert result.context.mastery == 0.625
    assert learner_service.requested_ids == [LEARNER_ID]
    assert mastery_service.requested_ids == [LEARNER_ID]
    assert {request.skill_id for request in remaining.requests} == {SKILL_ID}
    assert result.evidence_origin is ContextEvidenceOrigin.MIXED
    assert {item.input: (item.source_id, item.origin) for item in result.provenance}[
        ContextInput.LEARNER
    ] == ("shared-learner:learner-service", EvidenceOrigin.REAL)
    assert {item.input: (item.source_id, item.origin) for item in result.provenance}[
        ContextInput.MASTERY
    ] == ("knowledge-tracing:mastery-service", EvidenceOrigin.REAL)


def test_three_real_adapters_feed_deterministic_controller_without_delivery() -> None:
    learner_service = StubLearnerService(learner(grade=5, language="si"))
    mastery_service = StubMasteryService(snapshot(0.625))
    support_provider = LearnerStateSupportNeedProvider(
        StubLearnerStateProvider(learner_state_result(support_need=0.4))  # type: ignore[arg-type]
    )
    controlled = ControlledRemainingProviders()
    context_assembler = assembler(
        learner_service,
        mastery_service,
        controlled,
        support_need_provider=support_provider,
    )
    request = assembly_request(
        session_id=SESSION_ID,
        as_of=ASSEMBLY_AS_OF,
        max_age_ms=60_000,
    )

    first = context_assembler.assemble(request)
    second = context_assembler.assemble(request)

    assert first.status is ContextReadinessStatus.READY
    assert first.context is not None
    assert first.context.mastery == 0.625
    assert first.context.support_need == 0.4
    assert first.context.learner_id == LEARNER_ID
    assert first.context.skill_id == SKILL_ID
    assert first.evidence_origin is ContextEvidenceOrigin.MIXED
    assert ScaffoldingController().decide(first.context) == ScaffoldingController().decide(
        second.context
    )
    support_provenance = next(
        item for item in first.provenance if item.input is ContextInput.SUPPORT_NEED
    )
    assert support_provenance.origin is EvidenceOrigin.REAL
    assert support_provenance.source_id == "learner-state:stored-support-need"
    assert not hasattr(first, "response_text")


@pytest.mark.parametrize(
    ("result", "error", "expected_reason"),
    [
        (
            LearnerStateSupportNeedResult(
                learner_id=LEARNER_ID,
                skill_id=SKILL_ID,
                status=SupportNeedStatus.NOT_FOUND,
            ),
            None,
            ContextReadinessReason.SUPPORT_NEED_NOT_FOUND,
        ),
        (
            learner_state_result(SupportNeedStatus.UNCERTAIN),
            None,
            ContextReadinessReason.SUPPORT_NEED_UNCERTAIN,
        ),
        (
            learner_state_result(SupportNeedStatus.STALE),
            None,
            ContextReadinessReason.SUPPORT_NEED_STALE,
        ),
        (
            learner_state_result(session_id="another-session"),
            None,
            ContextReadinessReason.SUPPORT_NEED_SESSION_MISMATCH,
        ),
        (
            LearnerStateSupportNeedResult.model_construct(
                learner_id=LEARNER_ID,
                skill_id=SKILL_ID,
                status=SupportNeedStatus.AVAILABLE,
                support_need=float("nan"),
                observed_at=OBSERVED_AT,
                session_id=SESSION_ID,
            ),
            None,
            ContextReadinessReason.SUPPORT_NEED_INVALID,
        ),
        (
            None,
            RuntimeError("provider failed"),
            ContextReadinessReason.SUPPORT_NEED_PROVIDER_ERROR,
        ),
    ],
    ids=["missing", "uncertain", "stale", "wrong-session", "malformed", "failure"],
)
def test_three_provider_context_fails_closed_on_learner_state_evidence(
    result: object | None,
    error: Exception | None,
    expected_reason: ContextReadinessReason,
) -> None:
    support_provider = LearnerStateSupportNeedProvider(  # type: ignore[arg-type]
        StubLearnerStateProvider(result, error)
    )
    context_assembler = assembler(
        StubLearnerService(learner()),
        StubMasteryService(snapshot()),
        support_need_provider=support_provider,
    )

    context = context_assembler.assemble(
        assembly_request(
            session_id=SESSION_ID,
            as_of=ASSEMBLY_AS_OF,
            max_age_ms=60_000,
        )
    )

    assert context.status is ContextReadinessStatus.NOT_READY
    assert context.context is None
    assert expected_reason in reasons(context)


def test_real_learner_state_requires_trusted_assembly_context() -> None:
    support_provider = LearnerStateSupportNeedProvider(  # type: ignore[arg-type]
        StubLearnerStateProvider(learner_state_result())
    )

    context = assembler(
        StubLearnerService(learner()),
        StubMasteryService(snapshot()),
        support_need_provider=support_provider,
    ).assemble(assembly_request())

    assert context.status is ContextReadinessStatus.NOT_READY
    assert reasons(context) == {ContextReadinessReason.SUPPORT_NEED_CONTEXT_REQUIRED}


@pytest.mark.parametrize(
    ("learner_service", "mastery_service", "expected_reason"),
    [
        (
            StubLearnerService(error=LearnerNotFoundError()),
            StubMasteryService(snapshot()),
            ContextReadinessReason.LEARNER_NOT_FOUND,
        ),
        (
            StubLearnerService(learner()),
            StubMasteryService(snapshot(None)),
            ContextReadinessReason.MASTERY_NOT_FOUND,
        ),
        (
            StubLearnerService(learner()),
            StubMasteryService(error=ModelUnavailableError()),
            ContextReadinessReason.MASTERY_PROVIDER_UNAVAILABLE,
        ),
        (
            StubLearnerService(error=SQLAlchemyError("database failed")),
            StubMasteryService(snapshot()),
            ContextReadinessReason.LEARNER_PROVIDER_ERROR,
        ),
        (
            StubLearnerService(learner(learner_id=OTHER_LEARNER_ID)),
            StubMasteryService(snapshot()),
            ContextReadinessReason.LEARNER_INVALID,
        ),
        (
            StubLearnerService(learner()),
            StubMasteryService(snapshot(learner_id=OTHER_LEARNER_ID)),
            ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ),
    ],
    ids=[
        "missing-learner",
        "missing-mastery",
        "kt-failure",
        "learner-failure",
        "learner-identity-mismatch",
        "kt-identity-mismatch",
    ],
)
def test_combined_context_fails_closed_without_synthetic_fallback(
    learner_service: StubLearnerService,
    mastery_service: StubMasteryService,
    expected_reason: ContextReadinessReason,
) -> None:
    result = assembler(learner_service, mastery_service).assemble(assembly_request())

    assert result.status is ContextReadinessStatus.NOT_READY
    assert result.context is None
    assert expected_reason in reasons(result)
    assert all(
        item.origin is EvidenceOrigin.REAL
        for item in result.provenance
        if item.input in {ContextInput.LEARNER, ContextInput.MASTERY}
    )


def test_database_backed_services_and_three_adapters_feed_context() -> None:
    if not WEIGHTS_PATH.is_file():
        pytest.skip("trained KT weights are not available")

    spec = load_feature_spec(str(FEATURE_SPEC_PATH))
    valid_skill_ids = {node.skill_id for node in XlsxSkillTaxonomyCatalog(TAXONOMY_PATH).load()}
    model = KnowledgeModel.load(WEIGHTS_PATH, spec)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            LearnerModel.__table__,
            SkillModel.__table__,
            QuestionModel.__table__,
            AttemptModel.__table__,
            MasterySnapshotModel.__table__,
            LearnerSkillStateModel.__table__,
        ],
    )
    with Session(engine) as session:
        learner_repository = SqlAlchemyLearnerRepository(session)
        stored_learner = learner_repository.add(learner())
        skill_index = spec.skills.index(SKILL_ID)
        session.add(
            SkillModel(
                code=SKILL_ID,
                sort_index=skill_index,
                area="MAT",
                name_en="Fractions",
                name_si=None,
            )
        )
        session.add(QuestionModel(id="q-real-context", skill_code=SKILL_ID, difficulty="medium"))
        session.flush()
        for number, correct in enumerate((True, False, True)):
            session.add(
                AttemptModel(
                    learner_id=LEARNER_ID,
                    question_id="q-real-context",
                    language="si",
                    source=1,
                    correct=correct,
                    penalty=0.1,
                    answered_at=OBSERVED_AT + timedelta(minutes=number),
                    idempotency_key=f"real-context-{number}-{uuid4()}",
                )
            )
        session.commit()

        state_repository = SqlAlchemyLearnerSkillStateRepository(session)
        fresh_state = LearnerSkillState(
            learner_id=LEARNER_ID,
            skill_id=SKILL_ID,
            session_id=SESSION_ID,
            window_id=3,
            observed_at=OBSERVED_AT,
            confusion_state="intervention_worthy_confusion",
            confusion_support_need="request_tutor_support",
            confusion_temporal_score=0.4,
            disengagement_state="engaged",
            disengagement_support_need="none",
            recommended_action="request_tutor_support",
            support_need=0.4,
        )
        state_repository.save(fresh_state)

        mastery_service = MasteryService(
            SqlAlchemyMasteryRepository(session),
            model,
            spec,
            now=lambda: OBSERVED_AT + timedelta(minutes=5),
        )
        real_learner = SharedLearnerProvider(LearnerService(learner_repository))
        real_mastery = KnowledgeTracingMasteryProvider(mastery_service, valid_skill_ids)
        real_support = LearnerStateSupportNeedProvider(StoredSupportNeedProvider(state_repository))
        controlled = ControlledRemainingProviders()
        context_assembler = TutorContextAssembler(
            learner_provider=real_learner,
            mastery_provider=real_mastery,
            support_need_provider=real_support,
            assessment_provider=controlled,
            history_provider=controlled,
            valid_skill_ids=valid_skill_ids,
        )

        learner_result = real_learner.get_learner(LEARNER_ID)
        mastery_result = real_mastery.get_mastery(
            MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id=SKILL_ID)
        )
        trusted_request = assembly_request(
            session_id=SESSION_ID,
            as_of=ASSEMBLY_AS_OF,
            max_age_ms=60_000,
        )
        ready = context_assembler.assemble(trusted_request)
        cold_start = context_assembler.assemble(
            assembly_request(
                skill_id=OTHER_SKILL_ID,
                session_id=SESSION_ID,
                as_of=ASSEMBLY_AS_OF,
                max_age_ms=60_000,
            )
        )
        missing = context_assembler.assemble(
            assembly_request(
                learner_id=OTHER_LEARNER_ID,
                session_id=SESSION_ID,
                as_of=ASSEMBLY_AS_OF,
                max_age_ms=60_000,
            )
        )

        state_repository.save(
            replace(fresh_state, window_id=4, observed_at=OBSERVED_AT - timedelta(minutes=2))
        )
        stale = context_assembler.assemble(trusted_request)
        state_repository.save(
            replace(
                fresh_state,
                session_id="another-session",
                window_id=5,
                observed_at=OBSERVED_AT,
            )
        )
        wrong_session = context_assembler.assemble(trusted_request)
        state_repository.save(
            replace(
                fresh_state,
                window_id=6,
                confusion_state="uncertain",
                support_need=None,
            )
        )
        uncertain = context_assembler.assemble(trusted_request)

        assert learner_result.status is EvidenceStatus.AVAILABLE
        assert learner_result.learner == stored_learner
        assert mastery_result.status is MasteryStatus.AVAILABLE
        assert mastery_result.mastery is not None
        assert ready.status is ContextReadinessStatus.READY
        assert ready.context is not None
        assert ready.context.mastery == mastery_result.mastery
        assert ready.context.support_need == 0.4
        assert ready.context.learner_id == LEARNER_ID
        assert ready.context.skill_id == SKILL_ID
        assert ready.learner_grade == 5
        assert ready.evidence_origin is ContextEvidenceOrigin.MIXED
        assert ContextReadinessReason.MASTERY_NOT_FOUND in reasons(cold_start)
        assert reasons(missing) == {ContextReadinessReason.LEARNER_NOT_FOUND}
        assert reasons(stale) == {ContextReadinessReason.SUPPORT_NEED_STALE}
        assert reasons(wrong_session) == {ContextReadinessReason.SUPPORT_NEED_SESSION_MISMATCH}
        assert reasons(uncertain) == {ContextReadinessReason.SUPPORT_NEED_UNCERTAIN}
        assert ScaffoldingController().decide(ready.context) == ScaffoldingController().decide(
            ready.context
        )
        assert session.query(LearnerModel).count() == 1
        assert session.query(MasterySnapshotModel).count() == 1
        assert session.query(LearnerSkillStateModel).count() == 1

    engine.dispose()

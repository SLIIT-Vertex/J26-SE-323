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
    ContextReadinessReason,
    ContextReadinessStatus,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    SkillMappingResult,
    SupportNeedResult,
    TutorContextAssembler,
    TutorContextAssemblyRequest,
)
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure import (
    KnowledgeTracingMasteryProvider,
    XlsxSkillTaxonomyCatalog,
)
from app.knowledge_tracing.application.mastery import (
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
)
from app.knowledge_tracing.application.mastery_service import (
    LearnerNotFoundError,
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
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.model import LearnerModel

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
TAXONOMY_PATH = REPOSITORY_ROOT / "docs/skill_nodes.xlsx"
FEATURE_SPEC_PATH = REPOSITORY_ROOT / "shared/feature_spec.json"
WEIGHTS_PATH = (
    BACKEND_ROOT / "app/knowledge_tracing/infrastructure/ml/weights/mindbridge_dkt_v2_best.pt"
)
LEARNER_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_LEARNER_ID = UUID("00000000-0000-4000-8000-000000000002")
SKILL_ID = "MAT-FRC"
OTHER_SKILL_ID = "MAT-OPS"
COMPUTED_AT = datetime(2026, 10, 17, 9, 30, tzinfo=UTC)
REAL_MAPPING_SOURCE = EvidenceSource(
    source_id="test:controlled-skill-mapping",
    origin=EvidenceOrigin.SYNTHETIC,
)


class StubMasteryService:
    def __init__(
        self,
        snapshot: MasterySnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls = 0

    def current(self, learner_id: UUID) -> MasterySnapshot:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.snapshot is not None
        return self.snapshot


class ControlledContextProviders:
    """Controlled synthetic non-KT evidence for mixed-source assembly tests."""

    source = EvidenceSource(
        source_id="test:controlled-non-kt-context",
        origin=EvidenceOrigin.SYNTHETIC,
    )

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult:
        return LearnerLookupResult(
            status=EvidenceStatus.AVAILABLE,
            learner=Learner(id=learner_id, grade=5, preferred_language="si"),
        )

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        return SupportNeedResult(status=EvidenceStatus.AVAILABLE, support_need=0.4)

    def get_assessment_evidence(
        self,
        request: ContextEvidenceRequest,
    ) -> AssessmentEvidenceResult:
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
        return AssistanceHistoryResult(status=EvidenceStatus.NOT_YET_OBSERVED)


def snapshot(
    mastery: object = 0.625,
    *,
    learner_id: UUID = LEARNER_ID,
    skill_id: str = SKILL_ID,
    duplicate: bool = False,
) -> MasterySnapshot:
    estimates = [SkillEstimate(skill_id, mastery, 3)]
    if duplicate:
        estimates.append(SkillEstimate(skill_id, mastery, 3))
    return MasterySnapshot(
        id=1,
        learner_id=learner_id,
        computed_at=COMPUTED_AT,
        model_version="dkt-v2.1-test",
        n_attempts=3,
        skills=tuple(estimates),
    )


def provider(service: StubMasteryService) -> KnowledgeTracingMasteryProvider:
    return KnowledgeTracingMasteryProvider(service, {SKILL_ID, OTHER_SKILL_ID})  # type: ignore[arg-type]


def request(skill_id: str = SKILL_ID) -> MasteryRetrievalRequest:
    return MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id=skill_id)


def assembly_request(skill_id: str = SKILL_ID) -> TutorContextAssemblyRequest:
    return TutorContextAssemblyRequest(
        learner_id=LEARNER_ID,
        skill_mapping=SkillMappingResult(
            status=SkillMappingStatus.MATCHED,
            intent=LearningIntent.EXPLANATION_REQUEST,
            skill_id=skill_id,
            confidence=0.9,
            clarification_needed=False,
        ),
        skill_mapping_source=REAL_MAPPING_SOURCE,
    )


def assemble(service: StubMasteryService, skill_id: str = SKILL_ID):
    controlled = ControlledContextProviders()
    return TutorContextAssembler(
        learner_provider=controlled,
        mastery_provider=provider(service),
        support_need_provider=controlled,
        assessment_provider=controlled,
        history_provider=controlled,
        valid_skill_ids={SKILL_ID, OTHER_SKILL_ID},
    ).assemble(assembly_request(skill_id))


def reasons(result: object) -> set[ContextReadinessReason]:
    return {issue.reason for issue in result.issues}


@pytest.mark.parametrize("mastery", [0.0, 0.625, 1.0])
def test_available_mastery_is_preserved_exactly(mastery: float) -> None:
    result = provider(StubMasteryService(snapshot(mastery))).get_mastery(request())

    assert result.status is MasteryStatus.AVAILABLE
    assert result.mastery == mastery
    assert (result.learner_id, result.skill_id) == (LEARNER_ID, SKILL_ID)


@pytest.mark.parametrize(
    "mastery",
    [-0.01, 1.01, float("nan"), float("inf"), float("-inf")],
)
def test_malformed_numeric_mastery_fails_closed(mastery: float) -> None:
    result = provider(StubMasteryService(snapshot(mastery))).get_mastery(request())

    assert result.status is MasteryStatus.PROVIDER_ERROR
    assert result.mastery is None


def test_cold_start_is_not_found_without_fake_mastery() -> None:
    result = provider(StubMasteryService(snapshot(None))).get_mastery(request())

    assert result.status is MasteryStatus.NOT_FOUND
    assert result.mastery is None


def test_explicit_experimental_cold_start_uses_labelled_zero_default() -> None:
    adapter = KnowledgeTracingMasteryProvider(
        StubMasteryService(snapshot(None)),  # type: ignore[arg-type]
        {SKILL_ID, OTHER_SKILL_ID},
        cold_start_default=0.0,
    )

    result, source = adapter.get_mastery_with_source(request())

    assert result.status is MasteryStatus.AVAILABLE
    assert result.mastery == 0.0
    assert type(result) is MasteryResult
    assert source == EvidenceSource(
        source_id="adaptive-tutor:experimental-cold-start-mastery-default",
        origin=EvidenceOrigin.SYNTHETIC,
    )
    assert adapter.get_mastery(request()) == result


def test_real_kt_estimate_stays_real_when_a_cold_start_default_is_configured() -> None:
    adapter = KnowledgeTracingMasteryProvider(
        StubMasteryService(snapshot(0.625)),  # type: ignore[arg-type]
        {SKILL_ID, OTHER_SKILL_ID},
        cold_start_default=0.0,
    )

    result, source = adapter.get_mastery_with_source(request())

    assert result.mastery == 0.625
    assert source == EvidenceSource(
        source_id="knowledge-tracing:mastery-service", origin=EvidenceOrigin.REAL
    )


def test_experimental_default_does_not_hide_a_missing_learner() -> None:
    adapter = KnowledgeTracingMasteryProvider(
        StubMasteryService(error=LearnerNotFoundError()),  # type: ignore[arg-type]
        {SKILL_ID, OTHER_SKILL_ID},
        cold_start_default=0.0,
    )

    assert adapter.get_mastery(request()).status is MasteryStatus.NOT_FOUND


def test_missing_learner_is_not_found() -> None:
    result = provider(StubMasteryService(error=LearnerNotFoundError())).get_mastery(request())

    assert result.status is MasteryStatus.NOT_FOUND


def test_invalid_skill_is_rejected_before_calling_kt() -> None:
    service = StubMasteryService(snapshot())

    result = provider(service).get_mastery(request("NOT-REAL"))

    assert result.status is MasteryStatus.NOT_FOUND
    assert service.calls == 0


@pytest.mark.parametrize(
    "bad_snapshot",
    [
        snapshot(skill_id=OTHER_SKILL_ID),
        snapshot(duplicate=True),
        snapshot(learner_id=OTHER_LEARNER_ID),
    ],
    ids=["missing-skill", "duplicate-skill", "learner-mismatch"],
)
def test_malformed_or_mismatched_snapshot_is_provider_error(
    bad_snapshot: MasterySnapshot,
) -> None:
    result = provider(StubMasteryService(bad_snapshot)).get_mastery(request())

    assert result.status is MasteryStatus.PROVIDER_ERROR
    assert result.mastery is None


@pytest.mark.parametrize(
    "error",
    [ModelUnavailableError(), FileNotFoundError("weights missing"), OSError("weights unreadable")],
)
def test_unavailable_model_is_provider_unavailable(error: Exception) -> None:
    result = provider(StubMasteryService(error=error)).get_mastery(request())

    assert result.status is MasteryStatus.PROVIDER_UNAVAILABLE


def test_repository_failure_is_provider_error() -> None:
    result = provider(StubMasteryService(error=SQLAlchemyError("database failed"))).get_mastery(
        request()
    )

    assert result.status is MasteryStatus.PROVIDER_ERROR


def test_unexpected_service_error_is_provider_error() -> None:
    result = provider(StubMasteryService(error=RuntimeError("inference failed"))).get_mastery(
        request()
    )

    assert result.status is MasteryStatus.PROVIDER_ERROR


def test_provider_declares_real_source_without_rewriting_snapshot_provenance() -> None:
    original = snapshot()
    adapter = provider(StubMasteryService(original))

    adapter.get_mastery(request())

    assert adapter.source.origin is EvidenceOrigin.REAL
    assert adapter.source.source_id == "knowledge-tracing:mastery-service"
    assert original.model_version == "dkt-v2.1-test"
    assert original.computed_at == COMPUTED_AT
    assert original.n_attempts == 3


def test_real_kt_adapter_makes_controlled_context_ready() -> None:
    result = assemble(StubMasteryService(snapshot(0.625)))

    assert result.status is ContextReadinessStatus.READY
    assert result.context is not None
    assert result.context.mastery == 0.625
    assert result.evidence_origin is ContextEvidenceOrigin.MIXED


@pytest.mark.parametrize(
    ("service", "expected_reason"),
    [
        (
            StubMasteryService(snapshot(None)),
            ContextReadinessReason.MASTERY_NOT_FOUND,
        ),
        (
            StubMasteryService(error=LearnerNotFoundError()),
            ContextReadinessReason.MASTERY_NOT_FOUND,
        ),
        (
            StubMasteryService(error=ModelUnavailableError()),
            ContextReadinessReason.MASTERY_PROVIDER_UNAVAILABLE,
        ),
        (
            StubMasteryService(error=SQLAlchemyError("database failed")),
            ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ),
        (
            StubMasteryService(snapshot(learner_id=OTHER_LEARNER_ID)),
            ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ),
        (
            StubMasteryService(snapshot(skill_id=OTHER_SKILL_ID)),
            ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ),
        (
            StubMasteryService(snapshot(float("nan"))),
            ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ),
    ],
    ids=[
        "cold-start",
        "missing-learner",
        "provider-unavailable",
        "provider-error",
        "identity-mismatch",
        "missing-skill",
        "malformed-value",
    ],
)
def test_context_is_not_ready_without_valid_real_mastery(
    service: StubMasteryService,
    expected_reason: ContextReadinessReason,
) -> None:
    result = assemble(service)

    assert result.status is ContextReadinessStatus.NOT_READY
    assert result.context is None
    assert expected_reason in reasons(result)
    assert result.evidence_origin is ContextEvidenceOrigin.MIXED


def test_context_rejects_invalid_skill_before_calling_adapter() -> None:
    service = StubMasteryService(snapshot())

    result = assemble(service, "NOT-REAL")

    assert result.status is ContextReadinessStatus.NOT_READY
    assert reasons(result) == {ContextReadinessReason.SKILL_INVALID}
    assert service.calls == 0


def test_workbook_and_kt_feature_spec_skill_ids_remain_aligned() -> None:
    workbook_ids = {node.skill_id for node in XlsxSkillTaxonomyCatalog(TAXONOMY_PATH).load()}
    feature_spec_ids = set(load_feature_spec(str(FEATURE_SPEC_PATH)).skills)

    assert len(workbook_ids) == 30
    assert workbook_ids == feature_spec_ids


def test_real_repository_service_weights_and_adapter_preserve_mastery() -> None:
    if not WEIGHTS_PATH.is_file():
        pytest.skip("trained KT weights are not available")

    spec = load_feature_spec(str(FEATURE_SPEC_PATH))
    skill_index = spec.skills.index(SKILL_ID)
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
        ],
    )
    with Session(engine) as session:
        session.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="si"))
        session.add(
            SkillModel(
                code=SKILL_ID,
                sort_index=skill_index,
                area="MAT",
                name_en="Fractions",
                name_si=None,
            )
        )
        session.add(QuestionModel(id="q-frc", skill_code=SKILL_ID, difficulty="medium"))
        session.flush()
        for number, correct in enumerate((True, False, True)):
            session.add(
                AttemptModel(
                    learner_id=LEARNER_ID,
                    question_id="q-frc",
                    language="si",
                    source=1,
                    correct=correct,
                    penalty=0.1,
                    answered_at=COMPUTED_AT + timedelta(minutes=number),
                    idempotency_key=f"adapter-test-{number}-{uuid4()}",
                )
            )
        session.commit()

        service = MasteryService(
            SqlAlchemyMasteryRepository(session),
            model,
            spec,
            now=lambda: COMPUTED_AT + timedelta(minutes=5),
        )
        kt_snapshot = service.current(LEARNER_ID)
        expected = next(skill.mastery for skill in kt_snapshot.skills if skill.code == SKILL_ID)
        valid_skill_ids = {node.skill_id for node in XlsxSkillTaxonomyCatalog(TAXONOMY_PATH).load()}
        adapter = KnowledgeTracingMasteryProvider(service, valid_skill_ids)

        result = adapter.get_mastery(request())
        unrelated = adapter.get_mastery(request(OTHER_SKILL_ID))

        assert expected is not None
        assert result.status is MasteryStatus.AVAILABLE
        assert result.mastery == expected
        assert unrelated.status is MasteryStatus.NOT_FOUND
        assert unrelated.mastery is None
        assert session.query(MasterySnapshotModel).count() == 1

    engine.dispose()

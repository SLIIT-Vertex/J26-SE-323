from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy import inspect as inspect_database
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.application import (
    AssessmentEvidenceResult,
    ContextEvidenceRequest,
    EvidenceOrigin,
    EvidenceStatus,
)
from app.adaptive_tutor.infrastructure import (
    AssessmentAttemptStatus,
    AssessmentAttemptWrite,
    LedgerAssessmentEvidenceProvider,
    SqlAlchemyTutorAssessmentRepository,
    TutorAssessmentInteraction,
    UnresolvedAssessmentEvidenceProvider,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000071")
OTHER_LEARNER_ID = UUID("00000000-0000-4000-8000-000000000072")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000073")
OTHER_SESSION_ID = UUID("00000000-0000-4000-8000-000000000074")
INTERACTION_ID = UUID("00000000-0000-4000-8000-000000000075")
AT = datetime(2026, 10, 18, 9, 30, tzinfo=UTC)
PROPOSED_POLICY = "PROPOSED-synthetic-severity-v1"


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                LearnerModel(id=LEARNER_ID, grade=5, preferred_language="si"),
                LearnerModel(id=OTHER_LEARNER_ID, grade=5, preferred_language="ta"),
            ]
        )
        db.commit()
        yield db


def interaction(
    *,
    interaction_id: UUID = INTERACTION_ID,
    learner_id: UUID = LEARNER_ID,
    session_id: UUID = SESSION_ID,
    skill_id: str = "MAT-FRC",
    expires_at: datetime | None = None,
) -> TutorAssessmentInteraction:
    return TutorAssessmentInteraction(
        interaction_id=interaction_id,
        idempotency_key=f"interaction:{interaction_id}",
        learner_id=learner_id,
        session_id=session_id,
        skill_id=skill_id,
        interaction_sequence=1,
        source_component="controlled-item-bank",
        question_reference=f"question:{interaction_id}",
        question_version="synthetic-v1",
        authorization_reference="controlled-research-authorization",
        opened_at=AT,
        expires_at=expires_at,
        provenance="DESIGN_AUTHORED_SYNTHETIC",
    )


def attempt(
    *,
    interaction_id: UUID = INTERACTION_ID,
    idempotency_key: str | None = None,
    status: AssessmentAttemptStatus = AssessmentAttemptStatus.ACCEPTED,
    is_correct: bool | None = False,
    severity_value: float | None = 0.45,
    severity_policy_version: str | None = PROPOSED_POLICY,
    severity_reviewed: bool = True,
    scorer_authorized: bool = True,
    source_mapping_approved: bool = True,
    accepted_at: datetime | None = AT + timedelta(seconds=10),
) -> AssessmentAttemptWrite:
    attempt_id = uuid4()
    accepted = status is AssessmentAttemptStatus.ACCEPTED
    return AssessmentAttemptWrite(
        attempt_id=attempt_id,
        interaction_id=interaction_id,
        idempotency_key=idempotency_key or f"attempt:{attempt_id}",
        status=status,
        source_component="controlled-scorer",
        source_score_reference=f"score:{attempt_id}",
        scorer_authorized=scorer_authorized if accepted else False,
        source_mapping_approved=source_mapping_approved if accepted else False,
        is_correct=is_correct if accepted else None,
        scoring_version="synthetic-scorer-v1" if accepted else None,
        item_rubric_version="synthetic-item-rubric-v1" if accepted else None,
        severity_category=("CORRECT" if is_correct else "PARTIAL_CONCEPTUAL")
        if accepted and severity_value is not None
        else None,
        severity_value=severity_value if accepted else None,
        severity_policy_version=severity_policy_version if accepted else None,
        severity_reviewed=severity_reviewed if accepted else False,
        observed_at=AT + timedelta(seconds=5) if accepted else None,
        accepted_at=accepted_at if accepted else None,
        recorded_at=AT + timedelta(seconds=2),
        provenance="DESIGN_AUTHORED_SYNTHETIC",
    )


def request(
    *,
    learner_id: UUID = LEARNER_ID,
    session_id: UUID = SESSION_ID,
    skill_id: str = "MAT-FRC",
    interaction_id: UUID = INTERACTION_ID,
    as_of: datetime = AT + timedelta(minutes=1),
) -> ContextEvidenceRequest:
    return ContextEvidenceRequest(
        learner_id=learner_id,
        skill_id=skill_id,
        session_id=str(session_id),
        interaction_id=str(interaction_id),
        interaction_sequence=1,
        as_of=as_of,
    )


def controlled_provider(
    repository: SqlAlchemyTutorAssessmentRepository,
) -> LedgerAssessmentEvidenceProvider:
    return LedgerAssessmentEvidenceProvider(
        repository,
        valid_skill_ids={"MAT-FRC"},
        eligible_scorer_sources={"controlled-scorer"},
        eligible_severity_policy_versions={PROPOSED_POLICY},
        controlled_research=True,
    )


def test_missing_trusted_assessment_scope_is_explicit() -> None:
    result = UnresolvedAssessmentEvidenceProvider().get_assessment_evidence(
        ContextEvidenceRequest(learner_id=LEARNER_ID, skill_id="MAT-FRC")
    )

    assert result.status is EvidenceStatus.CONTEXT_REQUIRED
    assert result.attempt_count is None


def test_unreviewed_assessment_semantics_fail_closed_without_values() -> None:
    result = UnresolvedAssessmentEvidenceProvider().get_assessment_evidence(request())

    assert result.status is EvidenceStatus.POLICY_UNRESOLVED
    assert result.attempt_count is None
    assert UnresolvedAssessmentEvidenceProvider.source.origin is EvidenceOrigin.REAL


def test_interaction_replay_and_conflicting_idempotency(session: Session) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    original = interaction()

    assert repository.create_interaction(original) == (original, True)
    assert repository.create_interaction(original) == (original, False)

    with pytest.raises(ValueError, match="idempotency"):
        repository.create_interaction(original.model_copy(update={"skill_id": "MAT-OPS"}))


def test_committed_zero_attempt_is_proved_with_snapshot_metadata(session: Session) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction())

    result = controlled_provider(repository).get_assessment_evidence(request())

    assert result.status is EvidenceStatus.NOT_YET_OBSERVED
    assert result.attempt_count == 0
    assert result.assessment_reference == f"interaction:{INTERACTION_ID}"
    assert result.observed_at == request().as_of
    assert result.error_severity is None
    assert controlled_provider(repository).source_for_result(result).origin is EvidenceOrigin.REAL


def test_unknown_wrong_scope_stale_and_future_interactions_fail_closed(
    session: Session,
) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction(expires_at=AT + timedelta(seconds=30)))
    provider = controlled_provider(repository)

    assert (
        provider.get_assessment_evidence(request(interaction_id=uuid4())).status
        is EvidenceStatus.NOT_FOUND
    )
    assert (
        provider.get_assessment_evidence(request(session_id=OTHER_SESSION_ID)).status
        is EvidenceStatus.SESSION_MISMATCH
    )
    assert (
        provider.get_assessment_evidence(request(learner_id=OTHER_LEARNER_ID)).status
        is EvidenceStatus.INVALID_EVIDENCE
    )
    assert (
        provider.get_assessment_evidence(request(skill_id="MAT-OPS")).status
        is EvidenceStatus.INVALID_EVIDENCE
    )
    assert provider.get_assessment_evidence(request()).status is EvidenceStatus.STALE
    assert (
        provider.get_assessment_evidence(request(as_of=AT - timedelta(seconds=1))).status
        is EvidenceStatus.INVALID_EVIDENCE
    )


def test_pending_submission_is_not_mistaken_for_zero(session: Session) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction())
    repository.record_attempt(attempt(status=AssessmentAttemptStatus.PENDING))

    result = controlled_provider(repository).get_assessment_evidence(request())

    assert result.status is EvidenceStatus.UNCERTAIN
    assert result.attempt_count is None


def test_completed_controlled_attempt_is_available_but_synthetic(session: Session) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction())
    first, created = repository.record_attempt(attempt())
    second, replay_created = repository.record_attempt(
        AssessmentAttemptWrite.model_validate(first.model_dump(exclude={"attempt_sequence"}))
    )

    result = controlled_provider(repository).get_assessment_evidence(request())

    assert created is True
    assert replay_created is False
    assert second == first
    assert result.status is EvidenceStatus.AVAILABLE
    assert result.attempt_count == 1
    assert result.is_correct is False
    assert result.error_severity == 0.45
    assert result.severity_policy_version == PROPOSED_POLICY
    assert controlled_provider(repository).source.origin is EvidenceOrigin.SYNTHETIC


@pytest.mark.parametrize(
    ("attempt_evidence", "expected"),
    [
        (
            attempt(severity_value=None, severity_policy_version=None, severity_reviewed=False),
            EvidenceStatus.UNCERTAIN,
        ),
        (attempt(severity_policy_version="unapproved-policy"), EvidenceStatus.POLICY_UNRESOLVED),
        (attempt(scorer_authorized=False), EvidenceStatus.POLICY_UNRESOLVED),
        (attempt(source_mapping_approved=False), EvidenceStatus.POLICY_UNRESOLVED),
    ],
)
def test_incomplete_or_unapproved_attempts_fail_closed(
    session: Session,
    attempt_evidence: AssessmentAttemptWrite,
    expected: EvidenceStatus,
) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction())
    repository.record_attempt(attempt_evidence)

    assert controlled_provider(repository).get_assessment_evidence(request()).status is expected


def test_default_real_provider_does_not_activate_proposed_policy(session: Session) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction())
    repository.record_attempt(attempt())
    provider = LedgerAssessmentEvidenceProvider(repository, valid_skill_ids={"MAT-FRC"})

    result = provider.get_assessment_evidence(request())

    assert result.status is EvidenceStatus.POLICY_UNRESOLVED
    assert provider.source.origin is EvidenceOrigin.REAL


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), EvidenceStatus.PROVIDER_UNAVAILABLE),
        (RuntimeError(), EvidenceStatus.PROVIDER_ERROR),
    ],
)
def test_repository_failures_are_sanitized_and_typed(
    error: Exception,
    expected: EvidenceStatus,
) -> None:
    class FailingRepository:
        def snapshot(self, interaction_id: UUID, *, as_of: datetime) -> None:
            raise error

    provider = LedgerAssessmentEvidenceProvider(
        FailingRepository(),  # type: ignore[arg-type]
        valid_skill_ids={"MAT-FRC"},
    )

    result = provider.get_assessment_evidence(request())

    assert result.status is expected
    assert result.attempt_count is None


def test_latest_accepted_attempt_and_distinct_count_use_server_sequence(
    session: Session,
) -> None:
    repository = SqlAlchemyTutorAssessmentRepository(session)
    repository.create_interaction(interaction())
    first, _ = repository.record_attempt(attempt())
    second, _ = repository.record_attempt(attempt(is_correct=True, severity_value=0.0))

    result = controlled_provider(repository).get_assessment_evidence(request())

    assert (first.attempt_sequence, second.attempt_sequence) == (1, 2)
    assert result.attempt_count == 2
    assert result.is_correct is True
    assert result.error_severity == 0.0


def test_contract_rejects_raw_answers_and_invalid_time_or_correct_severity() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        AssessmentAttemptWrite.model_validate(
            {**attempt().model_dump(), "raw_answer": "child response"}
        )
    with pytest.raises(ValidationError, match="observed_at"):
        attempt(accepted_at=AT + timedelta(seconds=3))
    with pytest.raises(ValidationError, match="zero severity"):
        attempt(is_correct=True, severity_value=0.2)
    with pytest.raises(ValidationError, match="all-or-none"):
        AssessmentEvidenceResult(
            status=EvidenceStatus.NOT_YET_OBSERVED,
            attempt_count=0,
            assessment_reference="interaction:incomplete-audit-metadata",
        )


def test_concurrent_attempts_receive_distinct_server_sequences(tmp_path: Path) -> None:
    database = tmp_path / "assessment-concurrency.db"
    engine = create_engine(f"sqlite:///{database}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        db.add(LearnerModel(id=LEARNER_ID, grade=5, preferred_language="si"))
        db.commit()
        SqlAlchemyTutorAssessmentRepository(db).create_interaction(interaction())

    writes = (attempt(), attempt())

    def record(item: AssessmentAttemptWrite) -> int:
        with sessions() as db:
            saved, _ = SqlAlchemyTutorAssessmentRepository(db).record_attempt(item)
            return saved.attempt_sequence

    with ThreadPoolExecutor(max_workers=2) as executor:
        sequences = tuple(executor.map(record, writes))

    assert set(sequences) == {1, 2}


def test_assessment_migration_upgrades_and_downgrades_on_sqlite(session: Session) -> None:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20261018_03_create_tutor_assessment_ledger.py"
    )
    namespace = run_path(str(migration_path))
    for table in ("tutor_assessment_attempts", "tutor_assessment_interactions"):
        Base.metadata.tables[table].drop(session.bind)
    context = MigrationContext.configure(session.connection())

    with Operations.context(context):
        namespace["upgrade"]()
        tables = inspect_database(session.bind).get_table_names()
        assert "tutor_assessment_interactions" in tables
        assert "tutor_assessment_attempts" in tables
        namespace["downgrade"]()

    tables = inspect_database(session.bind).get_table_names()
    assert "tutor_assessment_interactions" not in tables
    assert "tutor_assessment_attempts" not in tables

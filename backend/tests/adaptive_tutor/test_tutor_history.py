from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy import inspect as inspect_database
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.application import ContextEvidenceRequest, EvidenceStatus
from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode
from app.adaptive_tutor.infrastructure import (
    SqlAlchemyTutorHistoryRepository,
    TutorHistoryEvent,
    TutorHistoryEventStatus,
    TutorHistoryEventType,
    TutorHistoryProvider,
    TutorInteractionEventModel,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000081")
OTHER_LEARNER_ID = UUID("00000000-0000-4000-8000-000000000082")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000083")
OTHER_SESSION_ID = UUID("00000000-0000-4000-8000-000000000084")
AT = datetime(2026, 10, 18, 10, 0, tzinfo=UTC)


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


def event(
    event_type: TutorHistoryEventType,
    *,
    decision_id: UUID,
    event_sequence: int,
    interaction_sequence: int = 1,
    learner_id: UUID = LEARNER_ID,
    session_id: UUID = SESSION_ID,
    skill_id: str = "MAT-FRC",
    status: TutorHistoryEventStatus | None = None,
    idempotency_key: str | None = None,
    assessment_reference: str | None = None,
    occurred_at: datetime = AT,
) -> TutorHistoryEvent:
    selected = event_type is TutorHistoryEventType.ASSISTANCE_SELECTED
    return TutorHistoryEvent(
        event_id=uuid4(),
        idempotency_key=idempotency_key or f"event-{uuid4()}",
        decision_id=decision_id,
        learner_id=learner_id,
        skill_id=skill_id,
        session_id=session_id,
        interaction_id=f"question-{interaction_sequence}",
        interaction_sequence=interaction_sequence,
        event_sequence=event_sequence,
        event_type=event_type,
        occurred_at=occurred_at,
        provenance="test:authoritative-history",
        assistance_level=AssistanceLevel.CONCEPTUAL_HINT if selected else None,
        policy_version="reference-policy-v1" if selected else None,
        reason_codes=(DecisionReasonCode.MINIMUM_SUFFICIENT_ASSISTANCE,) if selected else (),
        status=status,
        assessment_reference=assessment_reference,
    )


def request(
    *,
    learner_id: UUID = LEARNER_ID,
    session_id: UUID = SESSION_ID,
    skill_id: str = "MAT-FRC",
    interaction_sequence: int = 2,
) -> ContextEvidenceRequest:
    return ContextEvidenceRequest(
        learner_id=learner_id,
        skill_id=skill_id,
        session_id=str(session_id),
        interaction_id=f"question-{interaction_sequence}",
        interaction_sequence=interaction_sequence,
        as_of=AT,
    )


def test_first_interaction_has_no_prior_assistance(session: Session) -> None:
    result = TutorHistoryProvider(SqlAlchemyTutorHistoryRepository(session)).get_assistance_history(
        request(interaction_sequence=1)
    )

    assert result.status is EvidenceStatus.NOT_YET_OBSERVED


@pytest.mark.parametrize(
    "lifecycle",
    [
        (),
        ((TutorHistoryEventType.RESPONSE_VERIFIED, TutorHistoryEventStatus.PASS),),
        (
            (TutorHistoryEventType.RESPONSE_VERIFIED, TutorHistoryEventStatus.PASS),
            (TutorHistoryEventType.DELIVERY_AUTHORIZED, TutorHistoryEventStatus.AUTHORIZED),
        ),
    ],
)
def test_selected_or_verified_but_undelivered_is_not_exposure(
    session: Session,
    lifecycle: tuple[tuple[TutorHistoryEventType, TutorHistoryEventStatus], ...],
) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    decision_id = uuid4()
    repository.append(
        event(TutorHistoryEventType.ASSISTANCE_SELECTED, decision_id=decision_id, event_sequence=1)
    )
    for sequence, (event_type, status) in enumerate(lifecycle, start=2):
        repository.append(
            event(event_type, decision_id=decision_id, event_sequence=sequence, status=status)
        )

    result = TutorHistoryProvider(repository).get_assistance_history(request())

    assert result.status is EvidenceStatus.NOT_DELIVERED
    assert result.previous_assistance_level is None


def test_delivered_assistance_is_returned_without_fabricated_effectiveness(
    session: Session,
) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    decision_id = uuid4()
    repository.append(
        event(TutorHistoryEventType.ASSISTANCE_SELECTED, decision_id=decision_id, event_sequence=1)
    )
    repository.append(
        event(
            TutorHistoryEventType.RESPONSE_DELIVERED,
            decision_id=decision_id,
            event_sequence=2,
            status=TutorHistoryEventStatus.DELIVERED,
        )
    )

    result = TutorHistoryProvider(repository).get_assistance_history(request())

    assert result.status is EvidenceStatus.AVAILABLE
    assert result.previous_assistance_level is AssistanceLevel.CONCEPTUAL_HINT
    assert result.previous_hint_effective is None


def test_unknown_delivery_fails_closed(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    decision_id = uuid4()
    repository.append(
        event(TutorHistoryEventType.ASSISTANCE_SELECTED, decision_id=decision_id, event_sequence=1)
    )
    repository.append(
        event(
            TutorHistoryEventType.RESPONSE_DELIVERED,
            decision_id=decision_id,
            event_sequence=2,
            status=TutorHistoryEventStatus.UNKNOWN,
        )
    )

    assert (
        TutorHistoryProvider(repository).get_assistance_history(request()).status
        is EvidenceStatus.DELIVERY_UNKNOWN
    )


def test_history_isolated_by_learner_skill_and_session(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    for learner_id, skill_id, session_id, interaction_sequence in (
        (OTHER_LEARNER_ID, "MAT-FRC", SESSION_ID, 1),
        (LEARNER_ID, "MAT-OPS", SESSION_ID, 2),
        (LEARNER_ID, "MAT-FRC", OTHER_SESSION_ID, 3),
    ):
        repository.append(
            event(
                TutorHistoryEventType.ASSISTANCE_SELECTED,
                decision_id=uuid4(),
                event_sequence=1,
                learner_id=learner_id,
                skill_id=skill_id,
                session_id=session_id,
                interaction_sequence=interaction_sequence,
            )
        )

    assert (
        TutorHistoryProvider(repository)
        .get_assistance_history(request(interaction_sequence=5))
        .status
        is EvidenceStatus.NOT_YET_OBSERVED
    )


def test_idempotent_append_and_conflicting_reuse(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    original = event(
        TutorHistoryEventType.ASSISTANCE_SELECTED,
        decision_id=uuid4(),
        event_sequence=1,
        idempotency_key="stable-key",
    )

    assert repository.append(original) == (original, True)
    assert repository.append(original) == (original, False)
    conflicting = original.model_copy(update={"event_id": uuid4()})
    with pytest.raises(ValueError, match="idempotency key"):
        repository.append(conflicting)


def test_duplicate_sequence_rolls_back_without_partial_write(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    repository.append(
        event(TutorHistoryEventType.ASSISTANCE_SELECTED, decision_id=uuid4(), event_sequence=1)
    )

    with pytest.raises(IntegrityError):
        repository.append(
            event(TutorHistoryEventType.ASSISTANCE_SELECTED, decision_id=uuid4(), event_sequence=1)
        )

    assert len(session.scalars(select(TutorInteractionEventModel)).all()) == 1


def test_event_contract_rejects_malformed_level_and_unapproved_effectiveness() -> None:
    with pytest.raises(ValidationError):
        event(TutorHistoryEventType.RESPONSE_DELIVERED, decision_id=uuid4(), event_sequence=1)
    with pytest.raises(ValidationError):
        TutorHistoryEvent.model_validate(
            event(
                TutorHistoryEventType.OUTCOME_OBSERVED,
                decision_id=uuid4(),
                event_sequence=1,
                status=TutorHistoryEventStatus.OBSERVED,
            ).model_dump()
        )
    assert "EFFECTIVE" not in TutorHistoryEventStatus.__members__


def test_repeated_assessment_link_rolls_back(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    decision_id = uuid4()
    repository.append(
        event(
            TutorHistoryEventType.OUTCOME_OBSERVED,
            decision_id=decision_id,
            event_sequence=1,
            status=TutorHistoryEventStatus.OBSERVED,
            assessment_reference="assessment-1",
        )
    )

    with pytest.raises(IntegrityError):
        repository.append(
            event(
                TutorHistoryEventType.OUTCOME_OBSERVED,
                decision_id=decision_id,
                event_sequence=2,
                status=TutorHistoryEventStatus.OBSERVED,
                assessment_reference="assessment-1",
            )
        )


def test_ordering_uses_interaction_sequence_not_insert_order(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    for interaction_sequence, level in (
        (2, AssistanceLevel.TARGETED_HINT),
        (1, AssistanceLevel.CONCEPTUAL_HINT),
    ):
        decision_id = uuid4()
        selection = event(
            TutorHistoryEventType.ASSISTANCE_SELECTED,
            decision_id=decision_id,
            event_sequence=1,
            interaction_sequence=interaction_sequence,
        ).model_copy(update={"assistance_level": level})
        repository.append(selection)
        repository.append(
            event(
                TutorHistoryEventType.RESPONSE_DELIVERED,
                decision_id=decision_id,
                event_sequence=2,
                interaction_sequence=interaction_sequence,
                status=TutorHistoryEventStatus.DELIVERED,
            )
        )

    result = TutorHistoryProvider(repository).get_assistance_history(
        request(interaction_sequence=3)
    )

    assert result.previous_assistance_level is AssistanceLevel.TARGETED_HINT


def test_future_history_is_invalid(session: Session) -> None:
    repository = SqlAlchemyTutorHistoryRepository(session)
    repository.append(
        event(
            TutorHistoryEventType.ASSISTANCE_SELECTED,
            decision_id=uuid4(),
            event_sequence=1,
            occurred_at=AT + timedelta(microseconds=1),
        )
    )

    assert (
        TutorHistoryProvider(repository).get_assistance_history(request()).status
        is EvidenceStatus.INVALID_EVIDENCE
    )


def test_missing_or_invalid_context_and_repository_failure_fail_closed(session: Session) -> None:
    provider = TutorHistoryProvider(SqlAlchemyTutorHistoryRepository(session))
    missing = ContextEvidenceRequest(learner_id=LEARNER_ID, skill_id="MAT-FRC")
    invalid = request().model_copy(update={"session_id": "not-a-uuid"})

    assert provider.get_assistance_history(missing).status is EvidenceStatus.CONTEXT_REQUIRED
    assert provider.get_assistance_history(invalid).status is EvidenceStatus.INVALID_EVIDENCE

    class BrokenRepository:
        def before(self, **_: object) -> tuple[()]:
            raise OperationalError("select", {}, RuntimeError("offline"))

    broken = TutorHistoryProvider(BrokenRepository())  # type: ignore[arg-type]
    assert broken.get_assistance_history(request()).status is EvidenceStatus.PROVIDER_UNAVAILABLE


def test_schema_stores_no_raw_child_or_generated_text_columns() -> None:
    columns = set(TutorInteractionEventModel.__table__.columns.keys())

    assert not columns & {"student_message", "answer_json", "prompt", "response_text", "draft"}


def test_tutor_history_migration_upgrades_and_downgrades_isolated_database() -> None:
    engine = create_engine("sqlite://")
    migration = run_path(
        Path(__file__).parents[2] / "alembic/versions/20261018_02_create_tutor_history.py"
    )
    with engine.begin() as connection:
        LearnerModel.__table__.create(connection)
        migration["upgrade"].__globals__["op"] = Operations(MigrationContext.configure(connection))
        migration["upgrade"]()
        assert "tutor_interaction_events" in inspect_database(connection).get_table_names()

        migration["downgrade"]()
        assert "tutor_interaction_events" not in inspect_database(connection).get_table_names()

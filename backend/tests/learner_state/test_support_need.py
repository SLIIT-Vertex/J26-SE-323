from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.learner_state.application.service import (
    LearnerStateEvaluation,
    SignalEvaluation,
)
from app.learner_state.application.support_need import (
    LearnerSkillState,
    StoredSupportNeedProvider,
    SupportNeedRequest,
    SupportNeedResult,
    SupportNeedStatus,
    skill_state_from_evaluation,
    support_need_from_confusion,
)
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.shared.database.base import Base
from app.shared.learner.domain import Learner
from app.shared.learner.repository import SqlAlchemyLearnerRepository

OBSERVED_AT = datetime(2026, 10, 14, 9, 30)


def signal(state: str, temporal_score: float = 0.7) -> SignalEvaluation:
    return SignalEvaluation(
        visual_probability=0.8,
        behavior_probability=0.6,
        visual_reliability=0.9,
        behavior_reliability=0.7,
        fused_evidence=0.65,
        confidence=0.8,
        temporal_score=temporal_score,
        average_confidence=0.8,
        persistent_count=2,
        state=state,
        support_need="request_tutor_support",
    )


def evaluation(
    learner_id: UUID,
    confusion_state: str = "intervention_worthy_confusion",
) -> LearnerStateEvaluation:
    return LearnerStateEvaluation(
        session_id="session-1",
        learner_id=learner_id,
        window_id=3,
        confusion=signal(confusion_state),
        disengagement=replace(
            signal("engaged", 0.2),
            support_need="none",
        ),
        recommended_action="request_tutor_support",
    )


class InMemoryRepository:
    def __init__(self) -> None:
        self.states: dict[tuple[UUID, str], LearnerSkillState] = {}

    def save(self, state: LearnerSkillState) -> None:
        self.states[(state.learner_id, state.skill_id)] = state

    def get(self, learner_id: UUID, skill_id: str) -> LearnerSkillState | None:
        return self.states.get((learner_id, skill_id))


def test_support_need_is_confusion_temporal_score() -> None:
    assert support_need_from_confusion(signal("intervention_worthy_confusion", 0.72)) == 0.72
    assert support_need_from_confusion(signal("no_confusion", 0.18)) == 0.18


def test_uncertain_confusion_has_no_support_need() -> None:
    assert support_need_from_confusion(signal("uncertain")) is None


def test_skill_state_copies_evaluation() -> None:
    learner_id = uuid4()

    state = skill_state_from_evaluation(
        evaluation(learner_id),
        skill_id="MAT-FRC",
        observed_at=OBSERVED_AT,
    )

    assert state.learner_id == learner_id
    assert state.skill_id == "MAT-FRC"
    assert state.window_id == 3
    assert state.confusion_state == "intervention_worthy_confusion"
    assert state.disengagement_state == "engaged"
    assert state.recommended_action == "request_tutor_support"
    assert state.support_need == 0.7
    assert state.observed_at == OBSERVED_AT


@pytest.mark.parametrize(
    ("confusion_state", "expected_status", "expected_value"),
    [
        ("intervention_worthy_confusion", SupportNeedStatus.AVAILABLE, 0.7),
        ("uncertain", SupportNeedStatus.UNCERTAIN, None),
    ],
)
def test_provider_reports_stored_state(
    confusion_state: str,
    expected_status: SupportNeedStatus,
    expected_value: float | None,
) -> None:
    learner_id = uuid4()
    repository = InMemoryRepository()
    repository.save(
        skill_state_from_evaluation(
            evaluation(learner_id, confusion_state),
            skill_id="MAT-FRC",
            observed_at=OBSERVED_AT,
        )
    )

    result = StoredSupportNeedProvider(repository).get_support_need(
        SupportNeedRequest(learner_id=learner_id, skill_id="MAT-FRC")
    )

    assert result.status is expected_status
    assert result.support_need == expected_value
    assert result.observed_at == OBSERVED_AT
    assert (result.learner_id, result.skill_id) == (learner_id, "MAT-FRC")


def test_provider_reports_not_found_without_fabricating_a_value() -> None:
    result = StoredSupportNeedProvider(InMemoryRepository()).get_support_need(
        SupportNeedRequest(learner_id=uuid4(), skill_id="MAT-FRC")
    )

    assert result.status is SupportNeedStatus.NOT_FOUND
    assert result.support_need is None
    assert result.observed_at is None


@pytest.mark.parametrize(
    "data",
    [
        {"skill_id": "   "},
        {"skill_id": "A" * 17},
        {"skill_id": "MAT-FRC", "extra": 1},
        {"skill_id": 12},
    ],
)
def test_request_validation(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SupportNeedRequest.model_validate({"learner_id": str(uuid4()), **data})


@pytest.mark.parametrize(
    "data",
    [
        {"status": "AVAILABLE", "observed_at": OBSERVED_AT},
        {"status": "UNCERTAIN", "support_need": 0.5, "observed_at": OBSERVED_AT},
        {"status": "NOT_FOUND", "observed_at": OBSERVED_AT},
        {"status": "AVAILABLE", "support_need": 1.2, "observed_at": OBSERVED_AT},
        {"status": "UNCERTAIN"},
    ],
)
def test_result_status_rules(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SupportNeedResult.model_validate(
            {"learner_id": str(uuid4()), "skill_id": "MAT-FRC", **data}
        )


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_repository_keeps_latest_state_per_learner_and_skill(session: Session) -> None:
    learner_id = uuid4()
    SqlAlchemyLearnerRepository(session).add(
        Learner(id=learner_id, grade=5, preferred_language="si")
    )
    repository = SqlAlchemyLearnerSkillStateRepository(session)
    first = skill_state_from_evaluation(
        evaluation(learner_id),
        skill_id="MAT-FRC",
        observed_at=OBSERVED_AT,
    )

    repository.save(first)
    repository.save(replace(first, window_id=4, support_need=None, confusion_state="uncertain"))
    repository.save(replace(first, skill_id="LAN-CMP"))

    latest = repository.get(learner_id, "MAT-FRC")

    assert latest is not None
    assert latest.window_id == 4
    assert latest.support_need is None
    assert latest.confusion_state == "uncertain"
    assert repository.get(learner_id, "LAN-CMP") == replace(first, skill_id="LAN-CMP")
    assert repository.get(learner_id, "ENV-PLT") is None

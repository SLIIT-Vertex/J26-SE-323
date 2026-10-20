from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.fraction_adventure_flow import FRACTION_SUPPORT_SEQUENCE
from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.fraction_adventure import ATOMIC_SKILLS
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.content.test_fraction_adventure import response_for

LEARNER = UUID("00000000-0000-4000-8000-000000000755")


@pytest.fixture
def service():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    publisher = RecordingEvidencePublisher()
    yield (
        LearningFlowOrchestrator(
            SqlAlchemyLearningFlowStore(session),
            probe_gateway=LocalProbeGateway(),
            evidence_publisher=publisher,
        ),
        publisher,
    )
    session.close()


def bind(item, payload):
    return payload | {
        "presentation_id": item["presentation_id"],
        "item_revision_id": item["revision_id"],
        "interaction_version": "constructed-response-v1",
    }


@pytest.mark.parametrize("skill", [row.skill_id for row in ATOMIC_SKILLS])
def test_all_fraction_activities_open_without_public_answers_and_use_exact_default_support(
    service, skill
) -> None:
    flow, publisher = service
    opened = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="proposed",
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-05",
        atomic_skill_id=skill,
        idempotency_key=f"open:{skill}",
    )
    assert opened["manifest"]["game"]["schema_version"] == "fraction-adventure-item-v1"
    assert "correct_response" not in opened["manifest"]["game"]
    episode = UUID(opened["episode_id"])
    item = flow.reconstruct(episode)["state"]["presentations"][0]
    wrong = response_for(type("Item", (), {"game_data": item["game_data"]})())
    if wrong["kind"] in {"fraction_shading", "tenths_representation"}:
        wrong["shaded_indices"] = []
        if wrong["kind"] == "tenths_representation":
            wrong["numerator"] = 0
    elif wrong["kind"] == "equal_grouping":
        wrong["assignments"] = [0] * len(wrong["assignments"])
    else:
        wrong["quarter_values"] = [0, 0, 0]
    result = flow.submit_before(
        episode,
        option_id=None,
        constructed_response=bind(item, wrong),
        response_time_ms=700,
        interaction_summary={
            "move_count": 2,
            "correction_count": 0,
            "first_action_ms": 100,
            "active_time_ms": 600,
            "attempt_count": 1,
            "evidence_quality": 0.8,
            "all_objects_placed": True,
        },
        idempotency_key=f"before:{skill}",
    )
    assert result["status"] == "support_active"
    assert result["support"]["scaffold_type"] == FRACTION_SUPPORT_SEQUENCE[skill][0]
    assert result["support"]["game_manifest"]["worked_example"]["mode"] == "exact_failed_activity"
    state = flow.reconstruct(episode)["state"]
    assert set(state["model1"]["probabilities"])
    assert state["universal_skill_id"] == "MAT-FRC"
    assert publisher.records[-1]["universal_skill_id"] == "MAT-FRC"

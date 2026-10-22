from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.information_station import correct_response
from app.gamification.infrastructure.db.learning_flow_store import (
    SqlAlchemyLearningFlowStore,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.support_loop_helpers import finish_help

LEARNER = UUID("00000000-0000-4000-8000-000000000815")


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
@pytest.mark.parametrize(
    "skill_id",
    ["G5-ENG-INFO-BILINGUAL-01", "G5-ENG-INFO-VISUAL-02"],
)
def test_complete_durable_lifecycle_for_each_skill_and_condition(condition, skill_id):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(
            id=LEARNER,
            grade=5,
            preferred_language="si",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    publisher = RecordingEvidencePublisher()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=LocalProbeGateway(),
        evidence_publisher=publisher,
    )
    key = skill_id[-2:]
    opened = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition=condition,
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-ENG-15",
        atomic_skill_id=skill_id,
        idempotency_key=f"open-{condition}-{key}",
    )
    episode_id = UUID(opened["episode_id"])
    before = next(
        item
        for item in flow.reconstruct(episode_id)["state"]["presentations"]
        if item["role"] == "unsupported_before"
    )
    wrong = correct_response(before["game_data"])
    rows = wrong.get("links", wrong.get("placements"))
    target_key = "sinhala_token" if "links" in wrong else "object_token"
    rows[0][target_key], rows[1][target_key] = rows[1][target_key], rows[0][target_key]
    wrong.update(
        presentation_id=before["presentation_id"],
        item_revision_id=before["revision_id"],
        interaction_version="constructed-response-v1",
    )
    summary = {
        "move_count": 2,
        "correction_count": 0,
        "first_action_ms": 1,
        "active_time_ms": 100,
        "attempt_count": 1,
        "invalid_drop_count": 0,
        "tap_alternative_used": True,
    }
    supported = flow.submit_before(
        episode_id,
        option_id=None,
        constructed_response=wrong,
        response_time_ms=100,
        interaction_summary=summary,
        idempotency_key=f"before-{condition}-{key}",
    )
    support = supported["support"]
    support_manifest = support["game_manifest"]
    assert support_manifest["schema_version"] == "support-round-v1"
    help_done = finish_help(flow, episode_id, supported)
    flow.withdraw_support(
        episode_id,
        **help_done,
        request_id=uuid4(),
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw-{condition}-{key}",)
    after = flow.present_after(episode_id, idempotency_key=f"present-{condition}-{key}")
    after_item = next(
        item
        for item in flow.reconstruct(episode_id)["state"]["presentations"]
        if item["role"] == "unsupported_after"
    )
    answer = correct_response(after_item["game_data"])
    answer.update(
        presentation_id=after["manifest"]["presentation_id"],
        item_revision_id=after["manifest"]["revision_id"],
        interaction_version="constructed-response-v1",
    )
    result = flow.submit_after(
        episode_id,
        option_id=None,
        constructed_response=answer,
        response_time_ms=100,
        idempotency_key=f"after-{condition}-{key}",
    )
    state = flow.reconstruct(episode_id)["state"]
    assert result["status"] == "completed"
    assert state["model1"] and state["model2"]
    assert state["raw_independence_gain"] == "1"
    assert state["withdrawal"]["input_handlers_cleared"]
    assert publisher.records
    session.close()

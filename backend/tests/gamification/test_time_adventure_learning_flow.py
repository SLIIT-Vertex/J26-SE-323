from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000757")


def test_time_episode_is_server_scored_and_opens_the_server_order():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    publisher = RecordingEvidencePublisher()
    flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher)
    skill = "G5-MAT-TIME-ANALOG-01"
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="proposed", environment="test", allow_draft=True, area_id="G5-AREA-MAT-07", atomic_skill_id=skill, idempotency_key="open-time")
    manifest = opened["manifest"]
    assert manifest["game"]["schema_version"] == "time-adventure-item-v1"
    assert "correct_response" not in manifest["game"]
    episode = UUID(opened["episode_id"])
    item = flow.reconstruct(episode)["state"]["presentations"][0]
    wrong_hour = int(item["game_data"]["target_hour"]) % 12 + 1
    wrong = {"kind": "analog_clock", "hour": wrong_hour, "minute": item["game_data"]["target_minute"], "presentation_id": item["presentation_id"], "item_revision_id": item["revision_id"], "interaction_version": "constructed-response-v1"}
    result = flow.submit_before(episode, option_id=None, constructed_response=wrong, response_time_ms=700, interaction_summary={"move_count": 2, "correction_count": 0, "first_action_ms": 100, "active_time_ms": 600, "attempt_count": 1, "evidence_quality": 0.8, "all_objects_placed": True}, idempotency_key="wrong-time")
    assert result["status"] == "support_active"
    assert result["support"]["scaffold_type"] == flow.reconstruct(episode)["state"]["model2"]["support_order"][0]
    state = flow.reconstruct(episode)["state"]
    assert state["universal_skill_id"] == "MAT-TIME"
    assert publisher.records[-1]["universal_skill_id"] == "MAT-TIME"
    session.close()

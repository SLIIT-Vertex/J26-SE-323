from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.distance_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000759")
def test_distance_episode_is_reused_and_support_is_withdrawn_before_fresh_probe():
    engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine); session = Session(engine); now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)); session.commit()
    publisher = RecordingEvidencePublisher(); flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher)
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="proposed", environment="test", allow_draft=True, area_id="G5-AREA-MAT-09", atomic_skill_id="G5-MAT-LENGTH-ADD-01", idempotency_key="open-distance")
    episode = UUID(opened["episode_id"]); state = flow.reconstruct(episode)["state"]; before = next(r for r in state["presentations"] if r["role"] == "unsupported_before")
    response = correct_response(before["game_data"]); response["result_metres"] += 1; response.update(presentation_id=before["presentation_id"], item_revision_id=before["revision_id"], interaction_version="constructed-response-v1")
    summary = {"move_count": 4, "correction_count": 0, "first_action_ms": 50, "active_time_ms": 500, "attempt_count": 1, "working_cell_count": 4, "exchange_count": 1}
    supported = flow.submit_before(episode, option_id=None, constructed_response=response, response_time_ms=600, interaction_summary=summary, idempotency_key="wrong-distance")
    assert supported["episode_id"] == opened["episode_id"]
    assert supported["server_score"]["feedback_column"] in {"metres", "kilometres"}
    assert supported["support"]["game_manifest"]["worked_example"]["correct_response"]["working_steps"]
    support = supported["support"]; manifest = support["game_manifest"]
    flow.complete_support(episode, duration_ms=900, steps_viewed=3, manifest_revision_id=manifest["revision_id"], grouped_count=0, group_sizes=(), interaction_summary={"completed": True, "renderer_id": manifest["renderer_id"], "parallel_example_id": manifest["parallel_example_id"], "support_actions": 3}, idempotency_key="complete-distance")
    flow.withdraw_support(episode, request_id=uuid4(), support_revision_id=support["revision_id"], manifest_revision_id=manifest["revision_id"], all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-distance")
    after = flow.present_after(episode, idempotency_key="present-distance")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    assert after["manifest"]["revision_id"] != before["revision_id"]
    assert flow.reconstruct(episode)["state"]["withdrawal"]["answer_revealing_state_cleared"] is True
    session.close()

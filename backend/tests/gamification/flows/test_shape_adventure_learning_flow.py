from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.shape_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.support_loop_helpers import finish_help

LEARNER = UUID("00000000-0000-4000-8000-000000000763")


def test_shape_episode_reuse_exact_worked_support_and_withdrawal():
    engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine); session = Session(engine)
    now = datetime.now(UTC); session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)); session.commit()
    flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=RecordingEvidencePublisher())
    args = {"learner_id": LEARNER, "session_id": uuid4(), "grade": 5, "medium": "si", "condition": "proposed", "environment": "test", "allow_draft": True, "area_id": "G5-AREA-MAT-13", "atomic_skill_id": "G5-MAT-SHAPE-TABLE-01", "idempotency_key": "open-shape"}
    opened = flow.open_episode(**args); repeated = flow.open_episode(**args)
    assert opened["episode_id"] == repeated["episode_id"]
    episode = UUID(opened["episode_id"]); state = flow.reconstruct(episode)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    response = correct_response(before["game_data"]); response["rows"][0]["faces"] = 1
    response.update(presentation_id=before["presentation_id"], item_revision_id=before["revision_id"], interaction_version="constructed-response-v1")
    summary = {"move_count": 12, "correction_count": 0, "first_action_ms": 30, "active_time_ms": 400, "attempt_count": 1, "working_cell_count": 12}
    supported = flow.submit_before(episode, option_id=None, constructed_response=response, response_time_ms=500, interaction_summary=summary, idempotency_key="wrong-shape")
    assert supported["support"]["scaffold_type"] == flow.reconstruct(episode)["state"]["model2"]["support_order"][0]
    assert flow._adaptive_flow(episode).support_solution(before)["correct_response"]["rows"][0]["faces"] == 6
    help_done = finish_help(flow, episode, supported)
    flow.withdraw_support(episode, **help_done, request_id=uuid4(), all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-shape")
    after = flow.present_after(episode, idempotency_key="after-shape")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    assert flow.reconstruct(episode)["state"]["withdrawal"]["answer_revealing_state_cleared"] is True
    session.close()


def test_shape_public_manifest_contains_no_answer_fields():
    engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine); session = Session(engine)
    now = datetime.now(UTC); session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)); session.commit()
    flow = LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=RecordingEvidencePublisher())
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="baseline", environment="test", allow_draft=True, area_id="G5-AREA-MAT-13", atomic_skill_id="G5-MAT-ORIENTATION-01", idempotency_key="open-orientation")
    game = opened["manifest"]["game"]
    assert "correct_orientations" not in game and "correct_response" not in game
    session.close()

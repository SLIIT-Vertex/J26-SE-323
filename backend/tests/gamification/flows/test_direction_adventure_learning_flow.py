from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.direction_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.support_loop_helpers import finish_help

LEARNER = UUID("00000000-0000-4000-8000-000000000764")


def _flow():
    engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine)
    session = Session(engine); now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)); session.commit()
    publisher = RecordingEvidencePublisher()
    return session, publisher, LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher)


def test_direction_episode_reuse_exact_failed_scene_support_and_independent_probe():
    session, publisher, flow = _flow()
    args = {"learner_id": LEARNER, "session_id": uuid4(), "grade": 5, "medium": "si", "condition": "proposed", "environment": "test", "allow_draft": True, "area_id": "G5-AREA-MAT-14", "atomic_skill_id": "G5-MAT-DIRECTION-SCENE-01", "idempotency_key": "open-direction"}
    opened = flow.open_episode(**args); repeated = flow.open_episode(**args)
    assert opened["episode_id"] == repeated["episode_id"]
    episode = UUID(opened["episode_id"]); state = flow.reconstruct(episode)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    wrong = correct_response(before["game_data"]); wrong["selections"][0]["selected_direction"] = "south"
    wrong.update(presentation_id=before["presentation_id"], item_revision_id=before["revision_id"], interaction_version="constructed-response-v1")
    summary = {"move_count": 8, "correction_count": 0, "first_action_ms": 20, "active_time_ms": 500, "attempt_count": 1, "working_cell_count": 8}
    supported = flow.submit_before(episode, option_id=None, constructed_response=wrong, response_time_ms=700, interaction_summary=summary, idempotency_key="wrong-direction")
    assert flow._adaptive_flow(episode).support_solution(before)["game"]["scene_id"] == before["game_data"]["scene_id"]
    assert flow._adaptive_flow(episode).support_solution(before)["correct_response"]["kind"] == "place_direction_scene"
    help_done = finish_help(flow, episode, supported)
    flow.withdraw_support(episode, **help_done, request_id=uuid4(), all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-direction")
    after = flow.present_after(episode, idempotency_key="after-direction")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    assert after["manifest"]["game"]["scene_id"] != before["game_data"]["scene_id"]
    after_response = correct_response(next(row for row in flow.reconstruct(episode)["state"]["presentations"] if row["role"] == "unsupported_after")["game_data"])
    after_response.update(presentation_id=after["manifest"]["presentation_id"], item_revision_id=after["manifest"]["revision_id"], interaction_version="constructed-response-v1")
    result = flow.submit_after(episode, option_id=None, constructed_response=after_response, response_time_ms=600, idempotency_key="answer-direction-after")
    assert result["status"] == "completed" and result["server_score"]["correct"] is True
    assert publisher.records
    session.close()


def test_direction_public_manifest_has_no_explicit_answer_map():
    session, _, flow = _flow()
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="baseline", environment="test", allow_draft=True, area_id="G5-AREA-MAT-14", atomic_skill_id="G5-MAT-DIRECTION-MAIN-01", idempotency_key="open-main-direction")
    assert "correct_response" not in opened["manifest"]["game"]
    assert "answers" not in opened["manifest"]["game"]
    session.close()

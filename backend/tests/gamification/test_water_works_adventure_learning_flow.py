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
from app.gamification.content.water_works_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000808")


def _flow():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    publisher = RecordingEvidencePublisher()
    return session, publisher, LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher)


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
def test_water_flow_support_withdrawal_and_gain(condition: str) -> None:
    session, publisher, flow = _flow()
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition=condition, environment="test", allow_draft=True, area_id="G5-AREA-ENG-08", atomic_skill_id="G5-ENG-WATER-ACTION-01", idempotency_key=f"open-water-{condition}")
    episode = UUID(opened["episode_id"])
    state = flow.reconstruct(episode)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    wrong = correct_response(before["game_data"])
    wrong["placements"][0]["scene_token"], wrong["placements"][1]["scene_token"] = wrong["placements"][1]["scene_token"], wrong["placements"][0]["scene_token"]
    wrong.update(presentation_id=before["presentation_id"], item_revision_id=before["revision_id"], interaction_version="constructed-response-v1")
    summary = {"move_count": 2, "correction_count": 0, "first_action_ms": 50, "active_time_ms": 500, "attempt_count": 1, "invalid_drop_count": 0, "tap_alternative_used": True}
    supported = flow.submit_before(episode, option_id=None, constructed_response=wrong, response_time_ms=500, interaction_summary=summary, idempotency_key=f"wrong-water-{condition}")
    support = supported["support"]
    manifest = support["game_manifest"]
    flow.complete_support(episode, duration_ms=500, steps_viewed=manifest["required_actions"], manifest_revision_id=manifest["revision_id"], grouped_count=0, group_sizes=(), interaction_summary={"completed": True, "renderer_id": manifest["renderer_id"], "parallel_example_id": manifest["parallel_example_id"], "support_actions": manifest["required_actions"]}, idempotency_key=f"support-water-{condition}")
    flow.withdraw_support(episode, request_id=uuid4(), support_revision_id=support["revision_id"], manifest_revision_id=manifest["revision_id"], all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key=f"withdraw-water-{condition}")
    after = flow.present_after(episode, idempotency_key=f"after-water-{condition}")
    state = flow.reconstruct(episode)["state"]
    item = next(row for row in state["presentations"] if row["role"] == "unsupported_after")
    response = correct_response(item["game_data"])
    response.update(presentation_id=after["manifest"]["presentation_id"], item_revision_id=after["manifest"]["revision_id"], interaction_version="constructed-response-v1")
    result = flow.submit_after(episode, option_id=None, constructed_response=response, response_time_ms=450, idempotency_key=f"answer-water-{condition}")
    assert result["status"] == "completed"
    assert result["server_score"]["correct"] is True
    assert publisher.records
    assert flow.reconstruct(episode)["state"]["policy_update_status"] == ("authorized_delayed" if condition == "proposed" else "not_authorized_baseline")
    session.close()

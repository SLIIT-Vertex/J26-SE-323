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
from app.gamification.content.workplace_link_city import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000811")


def _flow():
    engine = create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine); session = Session(engine); now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)); session.commit(); publisher = RecordingEvidencePublisher()
    return session, publisher, LearningFlowOrchestrator(SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher)


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
@pytest.mark.parametrize("skill_id", ["G5-ENG-WORK-VOCAB-01", "G5-ENG-WORK-PLACE-02"])
def test_workplace_link_city_full_lifecycle(condition: str, skill_id: str) -> None:
    session, publisher, flow = _flow(); suffix = skill_id.rsplit("-", 1)[-1].lower()
    opened = flow.open_episode(learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition=condition, environment="test", allow_draft=True, area_id="G5-AREA-ENG-11", atomic_skill_id=skill_id, idempotency_key=f"open-work-{condition}-{suffix}"); episode = UUID(opened["episode_id"])
    before = next(row for row in flow.reconstruct(episode)["state"]["presentations"] if row["role"] == "unsupported_before"); wrong = correct_response(before["game_data"]); rows = wrong["placements"] if "placements" in wrong else wrong["links"]; target = "representation_token" if "placements" in wrong else "place_token"; rows[0][target], rows[1][target] = rows[1][target], rows[0][target]
    wrong.update(presentation_id=before["presentation_id"], item_revision_id=before["revision_id"], interaction_version="constructed-response-v1"); summary = {"move_count": 4, "correction_count": 0, "first_action_ms": 50, "active_time_ms": 500, "attempt_count": 1, "invalid_drop_count": 0, "tap_alternative_used": True}
    supported = flow.submit_before(episode, option_id=None, constructed_response=wrong, response_time_ms=500, interaction_summary=summary, idempotency_key=f"wrong-work-{condition}-{suffix}"); support = supported["support"]; manifest = support["game_manifest"]
    flow.complete_support(episode, duration_ms=500, steps_viewed=manifest["required_actions"], manifest_revision_id=manifest["revision_id"], grouped_count=0, group_sizes=(), interaction_summary={"completed": True, "renderer_id": manifest["renderer_id"], "parallel_example_id": manifest["parallel_example_id"], "support_actions": manifest["required_actions"]}, idempotency_key=f"support-work-{condition}-{suffix}")
    flow.withdraw_support(episode, request_id=uuid4(), support_revision_id=support["revision_id"], manifest_revision_id=manifest["revision_id"], all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key=f"withdraw-work-{condition}-{suffix}"); after = flow.present_after(episode, idempotency_key=f"after-work-{condition}-{suffix}")
    item = next(row for row in flow.reconstruct(episode)["state"]["presentations"] if row["role"] == "unsupported_after"); answer = correct_response(item["game_data"]); answer.update(presentation_id=after["manifest"]["presentation_id"], item_revision_id=after["manifest"]["revision_id"], interaction_version="constructed-response-v1")
    result = flow.submit_after(episode, option_id=None, constructed_response=answer, response_time_ms=450, idempotency_key=f"answer-work-{condition}-{suffix}"); state = flow.reconstruct(episode)["state"]
    assert result["status"] == "completed" and result["server_score"]["correct"] is True; assert state["model1"] and state["model2"] and state["withdrawal"]["input_handlers_cleared"]; assert state["policy_update_status"] == ("authorized_delayed" if condition == "proposed" else "not_authorized_baseline"); assert publisher.records; session.close()

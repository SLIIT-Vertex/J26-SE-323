from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.application.money_adventure_flow import MoneyAdventureFlow
from app.gamification.content.money_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000760")


def test_money_episode_reuses_id_and_withdraws_exact_answers_before_probe():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    publisher = RecordingEvidencePublisher()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=LocalProbeGateway(), evidence_publisher=publisher,
    )
    opened = flow.open_episode(
        learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si",
        condition="proposed", environment="test", allow_draft=True,
        area_id="G5-AREA-MAT-10", atomic_skill_id="G5-MAT-MONEY-ADD-01",
        idempotency_key="open-money",
    )
    episode = UUID(opened["episode_id"])
    state = flow.reconstruct(episode)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    response = correct_response(before["game_data"])
    response["result_cents"] = (response["result_cents"] + 1) % 100
    response.update(presentation_id=before["presentation_id"], item_revision_id=before["revision_id"], interaction_version="constructed-response-v1")
    summary = {"move_count": 4, "correction_count": 0, "first_action_ms": 50, "active_time_ms": 500, "attempt_count": 1, "working_cell_count": 4, "exchange_count": 1, "overshoot_count": 0}
    supported = flow.submit_before(episode, option_id=None, constructed_response=response, response_time_ms=600, interaction_summary=summary, idempotency_key="wrong-money")
    assert supported["episode_id"] == opened["episode_id"]
    worked = supported["support"]["game_manifest"]["worked_example"]
    assert worked["prompt_si"] == before["prompt_si"]
    assert supported["support"]["scaffold_type"] == "visual_guidance"
    assert worked["correct_response"] is None
    exact_worked = MoneyAdventureFlow._worked_example(before, scaffold_type="worked_parallel_example")
    assert exact_worked["correct_response"]["working_steps"]
    support = supported["support"]; manifest = support["game_manifest"]
    flow.complete_support(episode, duration_ms=900, steps_viewed=manifest["required_actions"], manifest_revision_id=manifest["revision_id"], grouped_count=0, group_sizes=(), interaction_summary={"completed": True, "renderer_id": manifest["renderer_id"], "parallel_example_id": manifest["parallel_example_id"], "support_actions": manifest["required_actions"]}, idempotency_key="complete-money")
    flow.withdraw_support(episode, request_id=uuid4(), support_revision_id=support["revision_id"], manifest_revision_id=manifest["revision_id"], all_support_removed=True, answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="withdraw-money")
    after = flow.present_after(episode, idempotency_key="present-money")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    assert after["manifest"]["revision_id"] != before["revision_id"]
    assert flow.reconstruct(episode)["state"]["withdrawal"]["answer_revealing_state_cleared"] is True
    session.close()

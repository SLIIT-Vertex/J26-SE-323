"""Drive one durable Sinhala package episode end to end, the way the phone does."""

from __future__ import annotations

from datetime import UTC, datetime
from types import ModuleType
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.application.teardown_receipt import simulated_receipt
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

SUMMARY = {"move_count": 2, "correction_count": 0, "first_action_ms": 40, "active_time_ms": 900, "input_mode": "tap"}


def world():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    learner = uuid4()
    now = datetime.now(UTC)
    session.add(LearnerModel(id=learner, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    publisher = RecordingEvidencePublisher()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session), probe_gateway=LocalProbeGateway(), evidence_publisher=publisher
    )
    return flow, publisher, learner


def bind(answer, record):
    return {
        **answer,
        "presentation_id": record["presentation_id"],
        "item_revision_id": record["revision_id"],
        "interaction_version": "constructed-response-v1",
    }


def state(flow, episode):
    return flow.reconstruct(episode)["state"]


def play(flow, learner, content: ModuleType, skill, condition, wrong, *, after_correct=True, support_success=True):
    """Open, fail the before item, run every help round, withdraw with a receipt, answer after."""

    opened = flow.open_episode(
        learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition=condition,
        environment="test", allow_draft=True, area_id=content.AREA_ID, atomic_skill_id=skill,
        idempotency_key=f"open:{uuid4()}",
    )
    episode = UUID(opened["episode_id"])
    assert opened["manifest"]["game"]["opening_demonstration"]["unscored"] is True
    before = next(r for r in state(flow, episode)["presentations"] if r["role"] == "unsupported_before")
    response = flow.submit_before(
        episode, option_id=None, constructed_response=bind(wrong(before), before), response_time_ms=None,
        interaction_summary=SUMMARY, idempotency_key=f"before:{episode}",
    )
    seen = []
    step = 0
    while not response["support_round"]["withdrawal_allowed"]:
        status = response["support_round"]
        manifest = response["support"]["game_manifest"]
        seen.append(status["scaffold_type"])
        assert manifest["activity"] is None or manifest["activity"]["answer"] is None
        if status["stage_kind"] == "view":
            steps = len(manifest["worked_example"]["steps_si"])
            response = flow.complete_support(
                episode, duration_ms=3000, steps_viewed=steps, grouped_count=0, group_sizes=(),
                manifest_revision_id=status["manifest_revision_id"],
                interaction_summary={"completed": True, "next_presses": steps}, idempotency_key=f"view:{episode}:{step}",
            )
        else:
            item = flow._adaptive_flow(episode)._support_rounds.current_item(state(flow, episode))
            answer = content.correct_response(item["game_data"]) if support_success else wrong(item)
            response = flow.submit_supported(
                episode, constructed_response=bind(answer, item), response_time_ms=800,
                interaction_summary={"move_count": 1}, idempotency_key=f"help:{episode}:{step}",
            )
        step += 1
    status = response["support_round"]
    flow.withdraw_support(
        episode, request_id=uuid4(), support_revision_id=status["support_revision_id"],
        manifest_revision_id=status["manifest_revision_id"], all_support_removed=True,
        answer_revealing_state_cleared=True, input_handlers_cleared=True,
        idempotency_key=f"withdraw:{episode}",
        teardown_receipt=simulated_receipt(status["support_revision_id"], status["manifest_revision_id"]),
    )
    flow.present_after(episode, idempotency_key=f"present:{episode}")
    after = state(flow, episode)["presentations"][-1]
    answer = content.correct_response(after["game_data"]) if after_correct else wrong(after)
    final = flow.submit_after(
        episode, option_id=None, constructed_response=bind(answer, after), response_time_ms=None,
        idempotency_key=f"after:{episode}",
    )
    return episode, final, seen

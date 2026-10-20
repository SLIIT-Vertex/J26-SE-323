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
from app.gamification.content.conversation_street import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000818")
SKILLS = (
    "G5-ENG-CONV-PAIR-01",
    "G5-ENG-CONV-TURN-02",
    "G5-ENG-CONV-FRAME-03",
    "G5-ENG-CONV-DESCRIBE-04",
)


def _wrong_response(game):
    response = correct_response(game)
    if response["kind"] == "conversation_pair_links":
        rows = response["links"]
        rows[0]["response_token"], rows[1]["response_token"] = (
            rows[1]["response_token"],
            rows[0]["response_token"],
        )
    elif response["kind"] == "conversation_turn_sequence":
        response["ordered_turn_tokens"][0], response["ordered_turn_tokens"][1] = (
            response["ordered_turn_tokens"][1],
            response["ordered_turn_tokens"][0],
        )
    elif response["kind"] == "fictional_profile_reply":
        response["ordered_chunk_tokens"][0], response["ordered_chunk_tokens"][1] = (
            response["ordered_chunk_tokens"][1],
            response["ordered_chunk_tokens"][0],
        )
    else:
        response["response_token"] = next(
            row["response_token"]
            for row in game["responses"]
            if row["response_token"] != game["target_response"]
        )
    return response


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
@pytest.mark.parametrize("skill_id", SKILLS)
def test_complete_durable_lifecycle_for_every_skill_and_condition(condition, skill_id):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
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
        area_id="G5-AREA-ENG-18",
        atomic_skill_id=skill_id,
        idempotency_key=f"open-{condition}-{key}",
    )
    episode_id = UUID(opened["episode_id"])
    before = next(
        row
        for row in flow.reconstruct(episode_id)["state"]["presentations"]
        if row["role"] == "unsupported_before"
    )
    wrong = _wrong_response(before["game_data"])
    wrong.update(
        presentation_id=before["presentation_id"],
        item_revision_id=before["revision_id"],
        interaction_version="constructed-response-v1",
    )
    supported = flow.submit_before(
        episode_id,
        option_id=None,
        constructed_response=wrong,
        response_time_ms=100,
        interaction_summary={
            "move_count": 2,
            "correction_count": 0,
            "first_action_ms": 1,
            "active_time_ms": 100,
            "attempt_count": 1,
            "invalid_drop_count": 0,
            "tap_alternative_used": True,
        },
        idempotency_key=f"before-{condition}-{key}",
    )
    support = supported["support"]
    manifest = support["game_manifest"]
    assert manifest["schema_version"] == "conversation-street-support-v1"
    flow.complete_support(
        episode_id,
        duration_ms=100,
        steps_viewed=manifest["required_actions"],
        manifest_revision_id=manifest["revision_id"],
        grouped_count=0,
        group_sizes=(),
        interaction_summary={
            "completed": True,
            "renderer_id": manifest["renderer_id"],
            "parallel_example_id": manifest["parallel_example_id"],
            "support_actions": manifest["required_actions"],
        },
        idempotency_key=f"support-{condition}-{key}",
    )
    flow.withdraw_support(
        episode_id,
        request_id=uuid4(),
        support_revision_id=support["revision_id"],
        manifest_revision_id=manifest["revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw-{condition}-{key}",
    )
    after = flow.present_after(episode_id, idempotency_key=f"present-{condition}-{key}")
    after_item = next(
        row
        for row in flow.reconstruct(episode_id)["state"]["presentations"]
        if row["role"] == "unsupported_after"
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
    assert state["condition"] == condition and state["model1"] and state["model2"]
    assert state["raw_independence_gain"] == "1"
    assert state["withdrawal"]["input_handlers_cleared"] and publisher.records
    session.close()

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
from app.gamification.content.roman_adventure import correct_response
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.support_loop_helpers import finish_help

LEARNER = UUID("00000000-0000-4000-8000-000000000766")


def _flow():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    publisher = RecordingEvidencePublisher()
    return (
        session,
        publisher,
        LearningFlowOrchestrator(
            SqlAlchemyLearningFlowStore(session),
            probe_gateway=LocalProbeGateway(),
            evidence_publisher=publisher,
        ),
    )


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
def test_episode_reuse_exact_support_withdrawal_and_independent_success(condition):
    session, publisher, flow = _flow()
    args = {
        "learner_id": LEARNER,
        "session_id": uuid4(),
        "grade": 5,
        "medium": "si",
        "condition": condition,
        "environment": "test",
        "allow_draft": True,
        "area_id": "G5-AREA-MAT-16",
        "atomic_skill_id": "G5-MAT-ROMAN-MATCH-01",
        "idempotency_key": f"open-roman-{condition}",
    }
    opened = flow.open_episode(**args)
    repeated = flow.open_episode(**args)
    assert opened["episode_id"] == repeated["episode_id"]
    episode = UUID(opened["episode_id"])
    before = next(
        row
        for row in flow.reconstruct(episode)["state"]["presentations"]
        if row["role"] == "unsupported_before"
    )
    wrong = correct_response(before["game_data"])
    wrong["matches"][0]["selected_roman"] = (
        "i" if wrong["matches"][0]["selected_roman"] != "i" else "v"
    )
    wrong.update(
        presentation_id=before["presentation_id"],
        item_revision_id=before["revision_id"],
        interaction_version="constructed-response-v1",
    )
    summary = {
        "move_count": 2,
        "correction_count": 0,
        "first_action_ms": 20,
        "active_time_ms": 400,
        "attempt_count": 1,
        "working_cell_count": 0,
    }
    supported = flow.submit_before(
        episode,
        option_id=None,
        constructed_response=wrong,
        response_time_ms=500,
        interaction_summary=summary,
        idempotency_key=f"wrong-roman-{condition}",
    )
    assert (
        flow._adaptive_flow(episode).support_solution(before)["game"]["arabic_values"] == before["game_data"]["arabic_values"]
    )
    assert flow._adaptive_flow(episode).support_solution(before)["correct_response"]["matches"]
    help_done = finish_help(flow, episode, supported)
    flow.withdraw_support(
        episode,
        **help_done,
        request_id=uuid4(),
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw-roman-{condition}",)
    after = flow.present_after(episode, idempotency_key=f"after-roman-{condition}")
    assert after["manifest"]["measurement_role"] == "unsupported_after"
    after_item = next(
        row
        for row in flow.reconstruct(episode)["state"]["presentations"]
        if row["role"] == "unsupported_after"
    )
    response = correct_response(after_item["game_data"])
    response.update(
        presentation_id=after["manifest"]["presentation_id"],
        item_revision_id=after["manifest"]["revision_id"],
        interaction_version="constructed-response-v1",
    )
    result = flow.submit_after(
        episode,
        option_id=None,
        constructed_response=response,
        response_time_ms=600,
        idempotency_key=f"answer-roman-after-{condition}",
    )
    assert result["status"] == "completed"
    assert result["server_score"]["correct"] is True
    assert publisher.records
    assert (
        flow.reconstruct(episode)["state"]["withdrawal"]["answer_revealing_state_cleared"] is True
    )
    session.close()


def test_public_manifest_has_no_answer_payload():
    session, _, flow = _flow()
    opened = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="baseline",
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-16",
        atomic_skill_id="G5-MAT-ROMAN-COUNT-01",
        idempotency_key="open-roman-public",
    )
    assert "correct_response" not in opened["manifest"]["game"]
    assert "answer" not in opened["manifest"]["game"]
    session.close()

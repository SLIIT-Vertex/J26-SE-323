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
from app.gamification.content.number_patterns import ATOMIC_SKILLS
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.support_loop_helpers import finish_help

LEARNER = UUID("00000000-0000-4000-8000-000000000733")


@pytest.fixture
def service():
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
    yield flow, publisher
    session.close()


def _response(item, *, correct: bool):
    game = item["game_data"]
    terms = [game["sequence"][index] for index in game["missing_indices"]]
    if not correct:
        terms = [value + 1 for value in terms]
    payload = {"completed_terms": terms}
    if game["operation"] == "multiply":
        payload.update(kind="constant_ratio_pattern", multiplier=game["rule"])
    else:
        payload.update(
            kind="constant_difference_pattern", operation=game["operation"], difference=game["rule"]
        )
    return payload


@pytest.mark.parametrize("skill", [row.skill_id for row in ATOMIC_SKILLS])
def test_each_pattern_skill_runs_the_three_model_flow(service, skill) -> None:
    flow, publisher = service
    opened = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="proposed",
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-03",
        atomic_skill_id=skill,
        idempotency_key=f"open:{skill}",
    )
    episode = UUID(opened["episode_id"])
    before = flow.reconstruct(episode)["state"]["presentations"][0]
    wrong = _response(before, correct=False)
    wrong.update(
        presentation_id=before["presentation_id"],
        item_revision_id=before["revision_id"],
        interaction_version="constructed-response-v1",
    )
    support = flow.submit_before(
        episode,
        option_id=None,
        constructed_response=wrong,
        response_time_ms=900,
        interaction_summary={
            "move_count": 3,
            "correction_count": 1,
            "rule_changes": 1,
            "operation_changes": 1,
            "active_time_ms": 800,
            "evidence_quality": 0.9,
        },
        idempotency_key=f"before:{skill}",
    )
    assert flow._adaptive_flow(episode).support_solution(before)["mode"] == "exact_failed_activity"
    help_done = finish_help(flow, episode, support)
    flow.withdraw_support(
        episode,
        **help_done,
        request_id=uuid4(),
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw:{skill}",)
    shown = flow.present_after(episode, idempotency_key=f"present:{skill}")
    after = flow.reconstruct(episode)["state"]["presentations"][-1]
    correct = _response(after, correct=True)
    correct.update(
        presentation_id=after["presentation_id"],
        item_revision_id=after["revision_id"],
        interaction_version="constructed-response-v1",
    )
    result = flow.submit_after(
        episode,
        option_id=None,
        constructed_response=correct,
        response_time_ms=700,
        idempotency_key=f"after:{skill}",
    )
    final = flow.reconstruct(episode)["state"]
    assert shown["manifest"]["game"]["schema_version"] == "number-pattern-item-v1"
    assert result["status"] == "completed"
    assert final["raw_independence_gain"] == "1"
    assert final["measurement"]["supported_correctness_used_as_reward"] is False
    assert len(final["policy_updates"]) == 1
    assert {record["universal_skill_id"] for record in publisher.records} == {"APT-PAT"}

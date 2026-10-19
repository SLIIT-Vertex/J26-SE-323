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
from app.gamification.application.number_world_flow import _escalate_scaffold
from app.gamification.application.subtraction_adventure_flow import SUBTRACTION_SUPPORT_SEQUENCE
from app.gamification.content.subtraction_adventure import ATOMIC_SKILLS
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000744")
PRIVATE_KEYS = {
    "result",
    "result_digits",
    "exchanges",
    "minuend_terms",
    "subtrahend_terms",
    "adjusted_terms",
    "result_terms",
    "minuend_source",
    "subtrahend_source",
    "correct_option_id",
}


@pytest.fixture
def service():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
    session.commit()
    publisher = RecordingEvidencePublisher()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=LocalProbeGateway(),
        evidence_publisher=publisher,
    )
    yield flow, publisher
    session.close()


def _payload(item, *, correct: bool):
    game = item["game_data"]
    kind = game["response_kind"]
    if kind == "expanded_subtraction":
        payload = {
            "kind": kind,
            "minuend_terms": list(game["minuend_terms"]),
            "subtrahend_terms": list(game["subtrahend_terms"]),
            "adjusted_minuend_terms": list(game["adjusted_terms"]),
            "result_terms": list(game["result_terms"]),
            "result": game["result"] if correct else game["result"] + 1,
        }
    elif kind == "difference_story":
        payload = {
            "kind": kind,
            "relationship": game["relationship"],
            "minuend_source": game["minuend_source"] if correct else game["subtrahend_source"],
            "subtrahend_source": game["subtrahend_source"] if correct else game["minuend_source"],
            "result_digits": list(game["result_digits"]),
            "result": game["result"] if correct else game["first_value"] + game["second_value"],
        }
    else:
        digits = list(game["result_digits"])
        if not correct:
            digits = [(digit + 1) % 10 for digit in digits]
        payload = {
            "kind": "column_subtraction",
            "result_digits": digits,
            "exchanges": [dict(row) for row in game["exchanges"]],
        }
    return payload


def _bind(item, payload):
    payload.update(
        presentation_id=item["presentation_id"],
        item_revision_id=item["revision_id"],
        interaction_version="constructed-response-v1",
    )
    return payload


def _run(flow, skill, *, condition, correct_after, suffix):
    opened = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition=condition,
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-04",
        atomic_skill_id=skill,
        idempotency_key=f"open:{suffix}",
    )
    episode = UUID(opened["episode_id"])
    manifest_game = opened["manifest"]["game"]
    assert manifest_game["schema_version"] == "subtraction-adventure-item-v1"
    assert PRIVATE_KEYS.isdisjoint(manifest_game)
    before = flow.reconstruct(episode)["state"]["presentations"][0]
    flow.submit_before(
        episode,
        option_id=None,
        constructed_response=_bind(before, _payload(before, correct=False)),
        response_time_ms=800,
        interaction_summary={
            "digit_entry_count": 4,
            "exchange_count": 1,
            "invalid_exchange_count": 0,
            "column_corrections": 1,
            "cleared_digits": 0,
            "started_from_ones": True,
            "alignment_valid": True,
            "completion_order_consistent": True,
            "first_action_ms": 120,
            "active_time_ms": 700,
            "attempt_count": 1,
            "evidence_quality": 0.9,
        },
        idempotency_key=f"before:{suffix}",
    )
    state = flow.reconstruct(episode)["state"]
    exposure = state["scaffold_exposure"]
    support = state["model2"]["selected_action"]
    flow.complete_support(
        episode,
        duration_ms=1000,
        steps_viewed=6,
        manifest_revision_id=exposure["manifest_revision_id"],
        grouped_count=0,
        group_sizes=(),
        interaction_summary={
            "completed": True,
            "renderer_id": f"{state['chapter']}:{exposure['scaffold_type']}",
            "parallel_example_id": f"{skill}:parallel-support-v1",
            "support_actions": 6 if support != "visual_guidance" else 3,
        },
        idempotency_key=f"support:{suffix}",
    )
    flow.withdraw_support(
        episode,
        request_id=uuid4(),
        support_revision_id=exposure["revision_id"],
        manifest_revision_id=exposure["manifest_revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw:{suffix}",
    )
    flow.present_after(episode, idempotency_key=f"present:{suffix}")
    after = flow.reconstruct(episode)["state"]["presentations"][-1]
    result = flow.submit_after(
        episode,
        option_id=None,
        constructed_response=_bind(after, _payload(after, correct=correct_after)),
        response_time_ms=600,
        idempotency_key=f"after:{suffix}",
    )
    final = flow.reconstruct(episode)["state"]
    return opened, result, final, support


@pytest.mark.parametrize("skill", [row.skill_id for row in ATOMIC_SKILLS])
def test_each_subtraction_skill_records_valid_proposed_gain(service, skill) -> None:
    flow, publisher = service
    _opened, result, final, support = _run(
        flow, skill, condition="proposed", correct_after=True, suffix=skill
    )
    assert result["status"] == "completed"
    assert final["raw_independence_gain"] == "1"
    assert final["measurement"]["supported_correctness_used_as_reward"] is False
    assert len(final["policy_updates"]) == 1
    assert final["model1"]["probabilities"]
    assert "unknown_or_other" in final["model1"]["probabilities"]
    assert {record["universal_skill_id"] for record in publisher.records} == {"MAT-OPS"}
    assert all(record["measurement_role"] in {"unsupported_before", "unsupported_after"} for record in publisher.records)
    assert support == SUBTRACTION_SUPPORT_SEQUENCE[skill][0]
    worked = final["scaffold_exposure"]
    assert worked["fully_withdrawn"] is True


def test_baseline_never_updates_policy_and_retry_escalates(service) -> None:
    flow, _publisher = service
    skill = "G5-MAT-SUB-NO-REGROUP-01"
    _opened, _result, final, support = _run(
        flow, skill, condition="baseline", correct_after=True, suffix="baseline"
    )
    assert support == "visual_guidance"
    assert final["policy_updates"] == []
    assert final["policy_update_status"] == "not_authorized_baseline"
    _opened, _result, failed, first_support = _run(
        flow, skill, condition="proposed", correct_after=False, suffix="retry-1"
    )
    assert first_support == "visual_guidance"
    assert failed["validity"] == "valid"
    assert failed["policy_updates"]
    _opened, _result, _second, second_support = _run(
        flow, skill, condition="proposed", correct_after=True, suffix="retry-2"
    )
    assert second_support == "worked_parallel_example"
    repeated = flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="proposed",
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-04",
        atomic_skill_id=skill,
        idempotency_key="retry-2",
    )
    assert repeated["episode_id"] == flow.reconstruct(UUID(repeated["episode_id"]))["state"]["episode_id"]


def test_preference_is_exact_skill_specific(service) -> None:
    flow, _publisher = service
    _run(flow, "G5-MAT-C07-L01-O01", condition="proposed", correct_after=True, suffix="pref-one")
    _opened, _result, other, support = _run(
        flow, "G5-MAT-C07-L01-O02", condition="proposed", correct_after=False, suffix="pref-two"
    )
    assert support == "worked_parallel_example"
    assert other["model2"]["learner_activity_support_preference"]["supported_correctness_used"] is False


def test_authored_support_sequences_are_deterministic() -> None:
    assert _escalate_scaffold(
        "step_by_step_guidance",
        condition="proposed",
        attempt_count=1,
        skill_id="G5-MAT-SUB-NO-REGROUP-01",
        support_sequences=SUBTRACTION_SUPPORT_SEQUENCE,
    ) == ("visual_guidance", "activity_default")
    assert _escalate_scaffold(
        "visual_guidance",
        condition="proposed",
        attempt_count=2,
        skill_id="G5-MAT-C07-L01-O02",
        support_sequences=SUBTRACTION_SUPPORT_SEQUENCE,
    ) == ("visual_guidance", "activity_support_escalation")
    assert _escalate_scaffold(
        "visual_guidance",
        condition="baseline",
        attempt_count=3,
        skill_id="G5-MAT-C07-L01-O01",
        support_sequences=SUBTRACTION_SUPPORT_SEQUENCE,
    ) == ("visual_guidance", "baseline_fixed")

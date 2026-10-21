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
from app.gamification.content.subtraction_adventure import ATOMIC_SKILLS
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.support_loop_helpers import finish_help

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
    shown = flow.submit_before(
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
    # The first help type the server opened for this episode.
    support = shown["support"]["scaffold_type"]
    help_done = finish_help(flow, episode, shown)
    flow.withdraw_support(
        episode,
        request_id=uuid4(),
        **help_done,
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
    assert support == final["model2"]["support_order"][0]
    worked = final["scaffold_exposure"]
    assert worked["fully_withdrawn"] is True


def test_baseline_never_updates_policy_and_a_failed_episode_is_no_preference(service) -> None:
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
    assert first_support == failed["model2"]["support_order"][0]
    assert failed["validity"] == "valid"
    assert failed["policy_updates"]
    _opened, _result, second, second_support = _run(
        flow, skill, condition="proposed", correct_after=True, suffix="retry-2"
    )
    # Help escalates inside an episode; an earlier independent failure is not a preference.
    assert second_support == second["model2"]["support_order"][0]
    assert second["model2"]["support_selection_mode"] != "learned_post_withdrawal_preference"
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
    # Skill one's independent success says nothing about skill two.
    assert support == other["model2"]["support_order"][0]
    assert other["model2"]["support_selection_mode"] != "learned_post_withdrawal_preference"
    assert other["model2"]["learner_activity_support_preference"]["supported_correctness_used"] is False




def test_a_right_answer_that_equals_the_number_taken_away_is_right() -> None:
    # 82 − 41 = 41: the answer's digits are the subtrahend's, and it is still correct.
    from app.gamification.content.subtraction_adventure import (
        analyze_subtraction,
        validate_constructed_response,
    )

    analysed = analyze_subtraction(82, 41)
    item = {
        "skill_id": "G5-MAT-SUB-NO-REGROUP-01",
        "game_data": {
            "response_kind": "column_subtraction",
            "minuend": 82,
            "subtrahend": 41,
            "width": 2,
            "result_digits": list(analysed["result_digits"]),
            "exchanges": [],
        },
    }
    correct, code, _ = validate_constructed_response(
        item, {"kind": "column_subtraction", "result_digits": [4, 1], "exchanges": []}
    )
    assert (correct, code) == (True, "correct")

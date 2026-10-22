from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.content.addition_adventure import ATOMIC_SKILLS, MISCONCEPTIONS, SCAFFOLDS
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.support_loop_helpers import finish_help, watch_demonstrations, wrong_answer

LEARNER = UUID("00000000-0000-4000-8000-000000000732")


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
    probe = LocalProbeGateway()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=probe,
        evidence_publisher=publisher,
    )
    yield flow, publisher, probe
    session.close()


def _open(flow, skill_id: str, condition: str = "proposed"):
    return flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition=condition,
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-02",
        atomic_skill_id=skill_id,
        idempotency_key=f"addition-open:{skill_id}:{condition}",
    )


def _finish(flow, opened, *, after_correct: bool = True):
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(option for option, _ in before["options"] if option != before["correct_option_id"])
    support = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_500,
        interaction_summary={
            "column_actions": 4,
            "carry_actions": 2,
            "alignment_valid": True,
            "correction_count": 1,
            "undo_count": 0,
            "active_time_ms": 1_200,
            "evidence_quality": 0.9,
        },
        idempotency_key=f"addition-before:{episode_id}",
    )
    assert "probabilities" not in str(support)
    state = flow.reconstruct(episode_id)["state"]
    help_done = finish_help(flow, episode_id, support)
    flow.withdraw_support(
        episode_id,
        **help_done,
        request_id=uuid4(),
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"addition-withdraw:{episode_id}",)
    shown = flow.present_after(episode_id, idempotency_key=f"addition-present:{episode_id}")
    state = flow.reconstruct(episode_id)["state"]
    after = state["presentations"][-1]
    answer = after["correct_option_id"]
    if not after_correct:
        answer = next(option for option, _ in after["options"] if option != answer)
    result = flow.submit_after(
        episode_id,
        option_id=answer,
        response_time_ms=1_200,
        idempotency_key=f"addition-after:{episode_id}",
    )
    return episode_id, shown, result, flow.reconstruct(episode_id)["state"]


@pytest.mark.parametrize("skill", [skill.skill_id for skill in ATOMIC_SKILLS])
def test_each_addition_skill_runs_through_all_three_models(service, skill):
    flow, publisher, _ = service
    opened = _open(flow, skill)
    assert opened["manifest"]["options"] == []
    assert not {
        "make_ten",
        "decomposition",
        "carrying_count",
        "expanded_addends",
        "cumulative_totals",
        "selected_cells",
        "correct_option_id",
    }.intersection(opened["manifest"]["game"])
    episode_id, shown, result, state = _finish(flow, opened)
    assert shown["manifest"]["measurement_role"] == "unsupported_after"
    assert shown["manifest"]["game"]["schema_version"] == "addition-adventure-item-v1"
    assert result["status"] == "completed"
    assert state["raw_independence_gain"] == "1"
    assert state["measurement"]["supported_correctness_used_as_reward"] is False
    assert set(state["model1"]["probabilities"]) == set(MISCONCEPTIONS)
    assert state["model1"]["item_revision_id"] == state["presentations"][0]["revision_id"]
    assert state["model1"]["parallel_family_id"] == state["presentations"][0]["parallel_family_id"]
    assert state["model1"]["server_score"]["scoring_version"].startswith("g5-mat-addition")
    assert state["model1"]["pre_decision_only"] is True
    assert state["model1"]["immutable_provenance"] is True
    assert {row["scaffold_type"] for row in state["model2"]["reference_decision"]["candidates"]} == set(SCAFFOLDS)
    assert state["model2"]["reference_decision"]["uses_complete_model1_distribution"] is True
    assert state["scaffold_exposure"]["fully_withdrawn"] is True
    assert len(state["policy_updates"]) == 1
    assert {record["universal_skill_id"] for record in publisher.records} == {"MAT-OPS"}
    assert flow.export_manifest(episode_id)["contains_answers"] is False


def test_baseline_isolated_and_invalid_episode_never_updates(service):
    flow, _, _ = service
    episode_id, _, result, state = _finish(flow, _open(flow, ATOMIC_SKILLS[0].skill_id, "baseline"))
    assert result["status"] == "completed"
    assert state["model2"]["reference_decision"]["uses_complete_model1_distribution"] is False
    assert state["policy_update_status"] == "not_authorized_baseline"
    assert state["policy_updates"] == []
    flow.invalidate(episode_id, reason="RESEARCH_REVIEW", idempotency_key="invalidate-baseline")
    assert flow.reconstruct(episode_id)["state"]["policy_updates"] == []


def test_sparse_evidence_uses_unknown_safe_fallback(service):
    flow, _, _ = service
    opened = _open(flow, ATOMIC_SKILLS[1].skill_id)
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(option for option, _ in before["options"] if option != before["correct_option_id"])
    flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=None,
        interaction_summary=None,
        idempotency_key="addition-sparse",
    )
    state = flow.reconstruct(episode_id)["state"]
    assert state["model1"]["abstained"] is True
    assert state["model1"]["top_hypothesis"] == "unknown_or_other"
    assert state["model2"]["reference_decision"]["mode"] == "proposed_shadow_conservative_fallback"
    # An abstaining Model 1 names no reason, so the loop lowers the load first.
    assert state["model2"]["reason_family"] == "unclear"
    assert state["model2"]["selected_action"] == "simpler_same_game"


def test_a_second_failed_attempt_strengthens_help_inside_the_episode(service):
    flow, _, _ = service
    opened = _open(flow, ATOMIC_SKILLS[0].skill_id)
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(option for option, _ in before["options"] if option != before["correct_option_id"])

    response = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_000,
        interaction_summary={"attempt_count": 2},
        idempotency_key="addition-second-failed-attempt",
    )
    # A maths visual demonstration is watched, not answered; the answerable help comes next.
    response = watch_demonstrations(flow, episode_id, response)
    first = response["support"]["scaffold_type"]
    current = flow._area_flows["G5-AREA-MAT-02"]._support_rounds.current_item(
        flow.reconstruct(episode_id)["state"]
    )
    game_flow = flow._area_flows["G5-AREA-MAT-02"]
    second = flow.submit_supported(
        episode_id,
        constructed_response=wrong_answer(game_flow, current),
        response_time_ms=500,
        interaction_summary={},
        idempotency_key="addition-wrong-inside-help",
    )

    # The next help comes from the server's order for this episode, not from a phone count.
    order = flow.reconstruct(episode_id)["state"]["model2"]["support_order"]
    assert second["support"]["scaffold_type"] == order[order.index(first) + 1] != first


def test_before_interactions_reject_free_text_or_answer_data(service):
    flow, _, _ = service
    opened = _open(flow, ATOMIC_SKILLS[2].skill_id)
    with pytest.raises(LearningFlowOrchestrationError, match="PII_OR_ANSWER_DATA_REJECTED"):
        flow.submit_before(
            UUID(opened["episode_id"]),
            option_id="o1",
            interaction_summary={"answer": "secret"},
            idempotency_key="addition-private-data",
        )


def test_contaminated_probe_never_reaches_after_item_or_policy_update(service):
    flow, _, probe = service
    opened = _open(flow, ATOMIC_SKILLS[-1].skill_id)
    episode_id = UUID(opened["episode_id"])
    state = flow.reconstruct(episode_id)["state"]
    before = state["presentations"][0]
    wrong = next(option for option, _ in before["options"] if option != before["correct_option_id"])
    response = flow.submit_before(
        episode_id, option_id=wrong, response_time_ms=1, idempotency_key="addition-contam-before"
    )
    state = flow.reconstruct(episode_id)["state"]
    help_done = finish_help(flow, episode_id, response)
    flow.withdraw_support(
        episode_id,
        **help_done,
        request_id=uuid4(),
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key="addition-contam-withdraw",)
    probe.contaminate(state["probe_reservation_id"])
    result = flow.present_after(episode_id, idempotency_key="addition-contam-present")
    final = flow.reconstruct(episode_id)["state"]
    assert result["status"] == "invalidated"
    assert final["exclusion_reasons"] == ["PRIOR_PROBE_EXPOSURE"]
    assert final["policy_updates"] == []

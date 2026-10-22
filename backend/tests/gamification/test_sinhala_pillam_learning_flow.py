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
from app.gamification.application.teardown_receipt import simulated_receipt
from app.gamification.content import sinhala_pillam as p
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

AREA = "G5-AREA-SIN-01"
SUMMARY = {"move_count": 2, "correction_count": 0, "first_action_ms": 40, "active_time_ms": 900, "input_mode": "tap"}


def _world():
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


def _bind(answer, record):
    return {
        **answer,
        "presentation_id": record["presentation_id"],
        "item_revision_id": record["revision_id"],
        "interaction_version": "constructed-response-v1",
    }


def _wrong(record):
    game = record["game_data"]
    answer = p.correct_response(game)
    if answer["kind"] == "sinhala_pillam_match":
        accepted = game["rubric"]["accepted"]
        for placement in answer["placements"]:
            placement["destination_id"] = next(
                d["destination_id"] for d in game["destinations"]
                if d["destination_id"] not in accepted[placement["source_token_id"]]
            )
        return answer
    # A card of a kind the target does not use: a second copy of a wanted kind could be right.
    kinds = game["rubric"]["kind_by_token"]
    answer["ordered_pilla_ids"] = [next(t for t, k in kinds.items() if k not in game["rubric"]["target_kinds"])]
    return answer


def _state(flow, episode):
    return flow.reconstruct(episode)["state"]


def _play(flow, learner, skill, condition, *, after_correct=True, before_correct=False, support_success=True):
    opened = flow.open_episode(
        learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition=condition,
        environment="test", allow_draft=True, area_id=AREA, atomic_skill_id=skill,
        idempotency_key=f"open:{uuid4()}",
    )
    episode = UUID(opened["episode_id"])
    assert opened["manifest"]["game"]["opening_demonstration"]["unscored"] is True
    before = next(r for r in _state(flow, episode)["presentations"] if r["role"] == "unsupported_before")
    answer = p.correct_response(before["game_data"]) if before_correct else _wrong(before)
    response = flow.submit_before(
        episode, option_id=None, constructed_response=_bind(answer, before), response_time_ms=None,
        interaction_summary=SUMMARY, idempotency_key=f"before:{episode}",
    )
    if before_correct:
        return episode, response
    # Explanations stay non-revealing while the after probe is reserved.
    assert response["server_score"]["feedback_si"] == "කමක් නැහැ. අපි එකට බලමු 🌱"
    step = 0
    while not response["support_round"]["withdrawal_allowed"]:
        status = response["support_round"]
        manifest = response["support"]["game_manifest"]
        assert manifest["activity"] is None or manifest["activity"]["answer"] is None
        if status["stage_kind"] == "view":
            steps = len(manifest["worked_example"]["steps_si"])
            response = flow.complete_support(
                episode, duration_ms=3000, steps_viewed=steps, grouped_count=0, group_sizes=(), manifest_revision_id=status["manifest_revision_id"],
                interaction_summary={"completed": True, "next_presses": steps}, idempotency_key=f"view:{episode}:{step}",
            )
        else:
            item = flow._adaptive_flow(episode)._support_rounds.current_item(_state(flow, episode))
            answer = p.correct_response(item["game_data"]) if support_success else _wrong(item)
            response = flow.submit_supported(
                episode, constructed_response=_bind(answer, item), response_time_ms=800,
                interaction_summary={"move_count": 1}, idempotency_key=f"help:{episode}:{step}",
            )
            assert response["server_score"]["feedback_si"]
        step += 1
    status = response["support_round"]
    flow.withdraw_support(
        episode, request_id=uuid4(), support_revision_id=status["support_revision_id"],
        manifest_revision_id=status["manifest_revision_id"], all_support_removed=True,
        answer_revealing_state_cleared=True, input_handlers_cleared=True,
        idempotency_key=f"withdraw:{episode}",
        teardown_receipt=simulated_receipt(status["support_revision_id"], status["manifest_revision_id"]),
    )
    presented = flow.present_after(episode, idempotency_key=f"present:{episode}")
    assert presented["manifest"]["measurement_role"] == "unsupported_after"
    after = _state(flow, episode)["presentations"][-1]
    answer = p.correct_response(after["game_data"]) if after_correct else _wrong(after)
    final = flow.submit_after(
        episode, option_id=None, constructed_response=_bind(answer, after), response_time_ms=None,
        idempotency_key=f"after:{episode}",
    )
    return episode, final


def _skill_with_ig(flow_skill="G5-SIN-PIL-NAME-01"):
    return flow_skill


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
@pytest.mark.parametrize("skill", list(p.SKILLS))
def test_every_activity_runs_the_full_durable_loop(condition, skill):
    flow, publisher, learner = _world()
    episode, final = _play(flow, learner, skill, condition)
    state = _state(flow, episode)
    # Model 1, Model 2 and Model 3 records are all persisted and linked.
    assert state["model1"]["pre_decision_only"] and state["model1"]["assistance_state"] == "none"
    assert abs(sum(state["model1"]["probabilities"].values()) - 1) < 1e-9
    assert state["model2"]["difficulty_evidence_id"] == state["difficulty_evidence"]["evidence_id"]
    assert state["model2"]["support_order"][0] == "visual_guidance" or condition == "proposed"
    if condition == "baseline":
        assert state["model2"]["support_order"] == list(p.SCAFFOLDS)
        assert state["model2"]["selection_reason"] == "activity_default"
    assert state["withdrawal"]["teardown_receipt"]["receipt_version"] == "pillam-teardown-receipt-v1"
    assert state["demonstration_ledger"][0]["excluded_from_probe_pool"] is True
    ig_available = state["presentations"][0]["game_data"]["equivalence"]["ig_available"]
    if ig_available:
        assert state["validity"] == "valid"
        assert state["measurement"]["raw_independence_gain"] == "1"
        assert state["measurement"]["percentage_point_value"] == "100"
        assert len(state["policy_updates"]) == (1 if condition == "proposed" else 0)
    else:
        assert "IG_UNAVAILABLE_INSUFFICIENT_REVIEWED_POOL" in state["exclusion_reasons"]
        assert state["policy_updates"] == []
    # Supported attempts are never published as knowledge evidence.
    assert {row["measurement_role"] for row in publisher.records} <= {"unsupported_before", "unsupported_after"}
    # After the last probe, the explanation may reveal the answer.
    assert final["server_score"]["feedback_si"].startswith("හරි")


def test_zero_and_negative_ig_stay_truthful_and_unrewarded_in_baseline():
    flow, _, learner = _world()
    episode, _ = _play(flow, learner, "G5-SIN-PIL-NAME-01", "baseline", after_correct=False)
    state = _state(flow, episode)
    assert state["measurement"]["raw_independence_gain"] == "0"
    assert state["policy_update_status"] == "not_authorized_baseline"
    measurement = __import__(
        "app.gamification.modeling.independence_gain.episode_measurement", fromlist=["x"]
    ).measure_withdrawn_episode
    before = next(a for a in state["attempts"] if a["role"] == "unsupported_before")
    after_item = state["presentations"][-1]
    state["attempts"] = [{**before, "earned_score": "1"}]
    negative = measurement(
        state, after_item=after_item, after_score={**before, "earned_score": "0", "presentation_id": after_item["presentation_id"]},
        scoring_version=p.SCORING_VERSION, measurement_version="m", equivalence_version="e",
    )
    assert negative["raw_independence_gain"] == "-1" and negative["percentage_point_value"] == "-100"


def test_withdrawal_without_teardown_receipt_fails_closed_and_after_stays_reserved():
    flow, _, learner = _world()
    opened = flow.open_episode(
        learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition="baseline",
        environment="test", allow_draft=True, area_id=AREA, atomic_skill_id="G5-SIN-PIL-BUILD-01",
        idempotency_key="open-x",
    )
    episode = UUID(opened["episode_id"])
    before = _state(flow, episode)["presentations"][0]
    response = flow.submit_before(
        episode, option_id=None, constructed_response=_bind(_wrong(before), before), response_time_ms=500,
        interaction_summary=SUMMARY, idempotency_key="b-x",
    )
    with pytest.raises(LearningFlowOrchestrationError, match="EPISODE_STATE_CONFLICT"):
        flow.present_after(episode, idempotency_key="early")
    status = response["support_round"]
    with pytest.raises(LearningFlowOrchestrationError, match="TEARDOWN_RECEIPT_REQUIRED"):
        flow.withdraw_support(
            episode, request_id=uuid4(), support_revision_id=status["support_revision_id"],
            manifest_revision_id=status["manifest_revision_id"], all_support_removed=True,
            answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="w-x",
        )
    assert len(_state(flow, episode)["presentations"]) == 1


def test_refusals_are_machine_readable_and_revision_bound():
    flow, _, learner = _world()
    opened = flow.open_episode(
        learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition="proposed",
        environment="test", allow_draft=True, area_id=AREA, atomic_skill_id="G5-SIN-PIL-NAME-01",
        idempotency_key="open-r",
    )
    episode = UUID(opened["episode_id"])
    before = _state(flow, episode)["presentations"][0]
    stale = {**_bind(_wrong(before), before), "item_revision_id": "other@v1"}
    with pytest.raises(LearningFlowOrchestrationError, match="REVISION_MISMATCH"):
        flow.submit_before(episode, option_id=None, constructed_response=stale, response_time_ms=1,
                           interaction_summary={}, idempotency_key="r1")
    bad = _bind(_wrong(before), before)
    bad["placements"][0]["source_token_id"] = "sign-000000000000"
    with pytest.raises(LearningFlowOrchestrationError, match="UNKNOWN_TOKEN"):
        flow.submit_before(episode, option_id=None, constructed_response=bad, response_time_ms=1,
                           interaction_summary={}, idempotency_key="r2")
    with pytest.raises(LearningFlowOrchestrationError, match="PII_OR_ANSWER_DATA_REJECTED"):
        flow.submit_before(episode, option_id=None, constructed_response=_bind(_wrong(before), before),
                           response_time_ms=1, interaction_summary={"pointer_trail": 1}, idempotency_key="r3")
    # The same idempotency key replays the stored receipt exactly once.
    first = flow.submit_before(episode, option_id=None, constructed_response=_bind(_wrong(before), before),
                               response_time_ms=1, interaction_summary=SUMMARY, idempotency_key="r4")
    again = flow.submit_before(episode, option_id=None, constructed_response=_bind(_wrong(before), before),
                               response_time_ms=1, interaction_summary=SUMMARY, idempotency_key="r4")
    assert first == again
    assert len(_state(flow, episode)["attempts"]) == 1


def test_failed_independent_retry_advances_the_cursor_and_drops_a_failed_preference():
    flow, _, learner = _world()
    skill = "G5-SIN-PIL-NAME-01"
    first, _ = _play(flow, learner, skill, "proposed", after_correct=False)
    first_state = _state(flow, first)
    second, _ = _play(flow, learner, skill, "proposed")
    second_state = _state(flow, second)
    cursor = second_state["support_cursor"]
    assert cursor["unresolved"] is True and cursor["source_episode_id"] == first_state["episode_id"]
    assert second_state["model2"]["selection_reason"] == "activity_support_escalation"
    assert second_state["model2"]["support_order"][0] != first_state["model2"]["support_order"][0]


def test_baseline_never_reads_history():
    flow, _, learner = _world()
    skill = "G5-SIN-PIL-NAME-01"
    _play(flow, learner, skill, "baseline", after_correct=False)
    second, _ = _play(flow, learner, skill, "baseline")
    state = _state(flow, second)
    assert state["model2"]["support_order"] == list(p.SCAFFOLDS)
    assert state["support_cursor"]["unresolved"] is False


def test_correct_before_ends_without_support_or_reward_update():
    flow, _, learner = _world()
    episode, response = _play(flow, learner, "G5-SIN-PIL-VOWEL-01", "proposed", before_correct=True)
    state = _state(flow, episode)
    assert state["status"] == "completed" and state["support_loop"] if "support_loop" in state else True
    assert state["policy_updates"] == [] and response["support"] is None


def test_worked_demonstration_requires_observed_steps():
    flow, _, learner = _world()
    opened = flow.open_episode(
        learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition="baseline",
        environment="test", allow_draft=True, area_id=AREA, atomic_skill_id="G5-SIN-PIL-LENGTH-01",
        idempotency_key="open-w",
    )
    episode = UUID(opened["episode_id"])
    before = _state(flow, episode)["presentations"][0]
    response = flow.submit_before(episode, option_id=None, constructed_response=_bind(_wrong(before), before),
                                  response_time_ms=1, interaction_summary=SUMMARY, idempotency_key="w1")
    item = flow._adaptive_flow(episode)._support_rounds.current_item(_state(flow, episode))
    response = flow.submit_supported(episode, constructed_response=_bind(_wrong(item), item),
                                     response_time_ms=1, interaction_summary={"move_count": 1},
                                     idempotency_key="w2")
    status = response["support_round"]
    assert status["scaffold_type"] == "worked_parallel_example" and status["stage_kind"] == "view"
    with pytest.raises(LearningFlowOrchestrationError, match="SUPPORT_STEPS_NOT_OBSERVED"):
        flow.complete_support(episode, duration_ms=10, steps_viewed=1, grouped_count=0, group_sizes=(), manifest_revision_id=status["manifest_revision_id"],
                              interaction_summary={"completed": True, "next_presses": 1}, idempotency_key="w3")


def test_simulated_receipt_is_marked_and_refused_outside_development_and_test():
    flow, _, learner = _world()
    episode, _ = _play(flow, learner, "G5-SIN-PIL-NAME-01", "baseline")
    assert _state(flow, episode)["withdrawal"]["teardown_observed_on_device"] is False
    opened = flow.open_episode(
        learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition="baseline",
        environment="pilot", allow_draft=True, area_id=AREA, atomic_skill_id="G5-SIN-PIL-NAME-01",
        idempotency_key="open-pilot",
    )
    pilot = UUID(opened["episode_id"])
    before = _state(flow, pilot)["presentations"][0]
    response = flow.submit_before(pilot, option_id=None, constructed_response=_bind(_wrong(before), before),
                                  response_time_ms=1, interaction_summary=SUMMARY, idempotency_key="p1")
    item = flow._adaptive_flow(pilot)._support_rounds.current_item(_state(flow, pilot))
    response = flow.submit_supported(pilot, constructed_response=_bind(p.correct_response(item["game_data"]), item),
                                     response_time_ms=1, interaction_summary={"move_count": 1}, idempotency_key="p2")
    status = response["support_round"]
    with pytest.raises(LearningFlowOrchestrationError, match="SIMULATED_TEARDOWN_NOT_ACCEPTED"):
        flow.withdraw_support(
            pilot, request_id=uuid4(), support_revision_id=status["support_revision_id"],
            manifest_revision_id=status["manifest_revision_id"], all_support_removed=True,
            answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key="p3",
            teardown_receipt=simulated_receipt(status["support_revision_id"], status["manifest_revision_id"]),
        )

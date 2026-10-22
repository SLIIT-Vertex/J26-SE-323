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
from app.gamification.content.number_world import (
    ATOMIC_SKILLS,
    MISCONCEPTIONS,
    SCAFFOLDS,
    validate_constructed_response,
)
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.gamification.modeling.support_selection.support_order import credited_support
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.support_loop_helpers import finish_help

LEARNER = UUID("00000000-0000-4000-8000-000000000731")


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


def _open(flow, skill_id: str, condition: str = "proposed", key_suffix: str = ""):
    return flow.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition=condition,
        environment="test",
        allow_draft=True,
        area_id="G5-AREA-MAT-01",
        atomic_skill_id=skill_id,
        idempotency_key=f"open:{skill_id}:{condition}:{key_suffix}",
    )


def test_constructed_response_is_bound_to_exact_presentation_and_revision(service):
    flow, _ = service
    opened = _open(flow, "G5-MAT-NUM-POSITION-01")
    manifest = opened["manifest"]
    with pytest.raises(LearningFlowOrchestrationError, match="STALE_OR_INCOMPATIBLE_MANIFEST"):
        flow.submit_before(
            UUID(opened["episode_id"]),
            option_id=None,
            constructed_response={
                "kind": "drag_to_slot",
                "selected_place": 1,
                "presentation_id": "another-presentation",
                "item_revision_id": manifest["revision_id"],
                "interaction_version": "constructed-response-v1",
            },
            response_time_ms=100,
            idempotency_key="stale-constructed-response",
        )


def _finish(flow, opened, *, after_correct: bool = True, attempt_count: int = 1):
    episode_id = UUID(opened["episode_id"])
    state = flow.reconstruct(episode_id)["state"]
    before = state["presentations"][0]
    wrong = next(option for option, _ in before["options"] if option != before["correct_option_id"])
    support = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1500,
        interaction_summary={"attempt_count": attempt_count},
        idempotency_key=f"before:{episode_id}",
    )
    assert "probabilities" not in str(support)
    help_done = finish_help(flow, episode_id, support)
    flow.withdraw_support(
        episode_id,
        **help_done,
        request_id=uuid4(),
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw:{episode_id}",)
    shown = flow.present_after(episode_id, idempotency_key=f"present:{episode_id}")
    state = flow.reconstruct(episode_id)["state"]
    after = state["presentations"][-1]
    option = (
        after["correct_option_id"]
        if after_correct
        else next(value for value, _ in after["options"] if value != after["correct_option_id"])
    )
    result = flow.submit_after(
        episode_id, option_id=option, response_time_ms=1200, idempotency_key=f"after:{episode_id}"
    )
    return episode_id, shown, result, flow.reconstruct(episode_id)["state"]


@pytest.mark.parametrize("skill", [skill.skill_id for skill in ATOMIC_SKILLS])
def test_each_atomic_skill_runs_on_durable_three_model_path(service, skill):
    flow, publisher = service
    opened = _open(flow, skill)
    assert opened["manifest"]["options"] == []
    assert not {"place", "expanded", "correct_option_id", "rods", "terms"}.intersection(
        opened["manifest"]["game"]
    )
    episode_id, shown, result, state = _finish(flow, opened)
    assert shown["manifest"]["measurement_role"] == "unsupported_after"
    assert result["status"] == "completed"
    assert state["raw_independence_gain"] == "1"
    assert state["measurement"]["supported_correctness_used_as_reward"] is False
    assert set(state["model1"]["probabilities"]) == set(MISCONCEPTIONS)
    reference = state["model2"]["reference_decision"]
    assert {row["scaffold_type"] for row in reference["candidates"]} == set(SCAFFOLDS)
    assert reference["uses_complete_model1_distribution"] is True
    assert state["scaffold_exposure"]["fully_withdrawn"] is True
    assert len(state["policy_updates"]) == 1
    assert {record["universal_skill_id"] for record in publisher.records} == {"MAT-NUM"}
    assert flow.export_manifest(episode_id)["contains_answers"] is False


def test_baseline_does_not_use_model1_for_selection_or_update(service):
    flow, _ = service
    _, _, result, state = _finish(flow, _open(flow, ATOMIC_SKILLS[0].skill_id, "baseline"))
    assert result["status"] == "completed"
    assert state["model2"]["reference_decision"]["uses_complete_model1_distribution"] is False
    assert state["model2"]["reason_family"] is None
    assert state["policy_update_status"] == "not_authorized_baseline"
    assert state["policy_updates"] == []


def test_zero_and_negative_raw_ig_are_preserved(service):
    flow, _ = service
    _, _, _, zero = _finish(flow, _open(flow, ATOMIC_SKILLS[1].skill_id), after_correct=False)
    assert zero["raw_independence_gain"] == "0"
    assert len(zero["policy_updates"]) == 1


def test_sparse_model1_uses_conservative_fallback(service):
    flow, _ = service
    opened = _open(flow, ATOMIC_SKILLS[2].skill_id)
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])
    flow.submit_before(episode_id, option_id=wrong, response_time_ms=None, idempotency_key="sparse")
    state = flow.reconstruct(episode_id)["state"]
    assert state["model1"]["abstained"] is True
    assert state["model2"]["reference_decision"]["mode"] == "proposed_shadow_conservative_fallback"
    # An abstaining Model 1 names no reason, so the loop lowers the load first.
    assert state["model2"]["reason_family"] == "unclear"
    assert state["model2"]["selected_action"] == "simpler_same_game"


def test_a_client_attempt_count_never_changes_the_server_order(service):
    flow, _ = service
    opened = _open(flow, ATOMIC_SKILLS[0].skill_id)
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])

    response = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_000,
        interaction_summary={"attempt_count": 3},
        idempotency_key="third-failed-attempt",
    )

    # Help escalates inside the episode, round by round, not by a count the phone sends.
    state = flow.reconstruct(episode_id)["state"]
    assert response["support"]["scaffold_type"] == state["model2"]["support_order"][0]
    assert state["model2"]["support_selection_mode"] == "model1_reason_lead"
    assert "attempt_count" not in state["model2"]


def test_future_episode_starts_with_support_that_previously_led_to_independent_success(service):
    flow, _ = service
    skill = "G5-MAT-NUM-POSITION-01"
    _, _, _, learned_from = _finish(
        flow,
        _open(flow, skill, key_suffix="learn-preference"),
    )
    # Watching the visual demonstration led straight to withdrawal and the fresh item was
    # answered alone, so the demonstration is the help that is learned.
    winner, _failed = credited_support(learned_from)
    assert winner is not None
    learned = [winner]

    opened = _open(flow, skill, key_suffix="reuse-preference")
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])
    response = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_000,
        interaction_summary={"attempt_count": 1},
        idempotency_key="reuse-learned-preference",
    )
    state = flow.reconstruct(episode_id)["state"]
    assert response["support"]["scaffold_type"] == learned[0]
    assert state["model2"]["support_selection_mode"] == "learned_post_withdrawal_preference"
    assert state["model2"]["learner_activity_support_preference"]["preferred_support"] == (
        learned[0]
    )


def test_a_prior_independent_failure_is_not_a_preference(service):
    flow, _ = service
    skill = "G5-MAT-NUM-POSITION-01"
    _finish(
        flow,
        _open(flow, skill, key_suffix="failed-first-support"),
        after_correct=False,
    )

    opened = _open(flow, skill, key_suffix="resume-escalation")
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])
    response = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_000,
        interaction_summary={"attempt_count": 1},
        idempotency_key="server-resumes-escalation",
    )
    # Help that did not lead to independent success earns no place at the front.
    state = flow.reconstruct(episode_id)["state"]
    assert response["support"]["scaffold_type"] == state["model2"]["support_order"][0]
    assert state["model2"]["support_selection_mode"] == "model1_reason_lead"
    assert state["model2"]["learner_activity_support_preference"]["preferred_support"] is None


@pytest.mark.parametrize("skill", [skill.skill_id for skill in ATOMIC_SKILLS])
def test_server_solution_of_the_exact_failed_item_feeds_the_help(service, skill):
    flow, _ = service
    opened = _open(flow, skill)
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])

    response = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_000,
        interaction_summary={"attempt_count": 2},
        idempotency_key=f"exact-worked:{skill}",
    )

    # The builders read the failed item's server solution; the phone never receives it.
    assert "correct_response" not in str(response["support"])
    state = flow.reconstruct(episode_id)["state"]
    worked = flow._area_flows["G5-AREA-MAT-01"].support_solution(before)
    assert worked["mode"] == "exact_failed_activity"
    assert worked["prompt_si"] == before["prompt_si"]
    assert worked["game"] == {
        "schema_version": "number-world-item-v1",
        "skill_id": skill,
        **before["game_data"],
    }
    assert len(worked["steps_si"]) == 3
    correct, error_code, _ = validate_constructed_response(before, worked["correct_response"])
    assert correct is True
    assert error_code == "correct"
    # A worked example and the visual demonstration both show a solved board.
    assert state["scaffold_exposure"]["answer_revealing"] is (
        state["scaffold_exposure"]["scaffold_type"]
        in {"worked_parallel_example", "visual_guidance"}
    )


def test_baseline_support_stays_fixed_when_attempt_count_increases(service):
    flow, _ = service
    opened = _open(flow, ATOMIC_SKILLS[1].skill_id, "baseline")
    episode_id = UUID(opened["episode_id"])
    before = flow.reconstruct(episode_id)["state"]["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])

    response = flow.submit_before(
        episode_id,
        option_id=wrong,
        response_time_ms=1_000,
        interaction_summary={"attempt_count": 4},
        idempotency_key="baseline-fourth-attempt",
    )

    assert response["support"]["scaffold_type"] == "visual_guidance"


def test_contaminated_probe_is_auditable_and_never_updates_policy():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    probe = LocalProbeGateway()
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=probe,
        evidence_publisher=RecordingEvidencePublisher(),
    )
    opened = _open(flow, ATOMIC_SKILLS[-1].skill_id)
    episode_id = UUID(opened["episode_id"])
    state = flow.reconstruct(episode_id)["state"]
    before = state["presentations"][0]
    wrong = next(value for value, _ in before["options"] if value != before["correct_option_id"])
    response = flow.submit_before(
        episode_id, option_id=wrong, response_time_ms=1, idempotency_key="contam-before"
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
        idempotency_key="contam-withdraw",)
    probe.contaminate(state["probe_reservation_id"])
    result = flow.present_after(episode_id, idempotency_key="contam-present")
    final = flow.reconstruct(episode_id)["state"]
    assert result["status"] == "invalidated"
    assert final["exclusion_reasons"] == ["PRIOR_PROBE_EXPOSURE"]
    assert final["policy_updates"] == []
    session.close()


def test_starting_a_skill_again_draws_a_fresh_after_item_instead_of_refusing(service):
    """A child who gets it wrong and starts the same skill again must not be refused because
    the new episode drew the after item the unfinished one still holds."""

    flow, _ = service
    game_flow = flow._area_flows["G5-AREA-MAT-01"]
    # Force every open onto the same first seed, as one session replaying one skill does.
    game_flow._episode_seed = lambda **_: 12_345
    skill = ATOMIC_SKILLS[0].skill_id
    first = flow.reconstruct(UUID(_open(flow, skill, key_suffix="first")["episode_id"]))["state"]
    second = flow.reconstruct(UUID(_open(flow, skill, key_suffix="second")["episode_id"]))[
        "state"
    ]

    assert second["seed"] != first["seed"]
    after = game_flow.generate_item(skill, role="unsupported_after", seed=second["seed"])
    held = game_flow.generate_item(skill, role="unsupported_after", seed=first["seed"])
    assert after.revision_id != held.revision_id

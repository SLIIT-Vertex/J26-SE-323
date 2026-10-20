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
from app.gamification.application.number_world_flow import (
    _escalate_scaffold,
    _next_support_attempt_from_history,
    _preferred_support_from_history,
)
from app.gamification.content.number_world import (
    ATOMIC_SKILLS,
    MISCONCEPTIONS,
    SCAFFOLDS,
    validate_constructed_response,
)
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

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
    state = flow.reconstruct(episode_id)["state"]
    exposure = state["scaffold_exposure"]
    flow.complete_support(
        episode_id,
        duration_ms=900,
        steps_viewed=2,
        manifest_revision_id=exposure["manifest_revision_id"],
        grouped_count=0,
        group_sizes=(),
        interaction_summary={
            "completed": True,
            "renderer_id": f"{state['chapter']}:{exposure['scaffold_type']}",
            "parallel_example_id": f"{state['skill_id']}:parallel-support-v1",
            "support_actions": 3,
        },
        idempotency_key=f"support:{episode_id}",
    )
    flow.withdraw_support(
        episode_id,
        request_id=uuid4(),
        support_revision_id=exposure["revision_id"],
        manifest_revision_id=exposure["manifest_revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw:{episode_id}",
    )
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
    assert {row["scaffold_type"] for row in state["model2"]["candidates"]} == set(SCAFFOLDS)
    assert state["model2"]["uses_complete_model1_distribution"] is True
    assert state["scaffold_exposure"]["fully_withdrawn"] is True
    assert len(state["policy_updates"]) == 1
    assert {record["universal_skill_id"] for record in publisher.records} == {"MAT-NUM"}
    assert flow.export_manifest(episode_id)["contains_answers"] is False


def test_baseline_does_not_use_model1_for_selection_or_update(service):
    flow, _ = service
    _, _, result, state = _finish(flow, _open(flow, ATOMIC_SKILLS[0].skill_id, "baseline"))
    assert result["status"] == "completed"
    assert state["model2"]["uses_complete_model1_distribution"] is False
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
    assert state["model2"]["mode"] == "proposed_shadow_conservative_fallback"
    assert state["model2"]["selected_action"] == "visual_guidance"


def test_repeated_failures_escalate_proposed_support_to_step_by_step(service):
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

    state = flow.reconstruct(episode_id)["state"]
    assert response["support"]["scaffold_type"] == "step_by_step_guidance"
    assert state["model2"]["attempt_count"] == 3
    assert state["model2"]["support_selection_mode"] == "activity_support_escalation"


@pytest.mark.parametrize(
    ("skill", "first_support", "second_support"),
    (
        ("G5-MAT-NUM-POSITION-01", "visual_guidance", "worked_parallel_example"),
        ("G5-MAT-NUM-REPRESENTED-01", "worked_parallel_example", "visual_guidance"),
        ("G5-MAT-NUM-100000-01", "visual_guidance", "worked_parallel_example"),
        ("G5-MAT-NUM-ABACUS-01", "worked_parallel_example", "visual_guidance"),
        ("G5-MAT-NUM-EXPAND-01", "worked_parallel_example", "visual_guidance"),
        ("G5-MAT-NUM-EXTREME-01", "visual_guidance", "worked_parallel_example"),
        ("G5-MAT-NUM-LEADING-ZERO-01", "visual_guidance", "worked_parallel_example"),
        ("G5-MAT-NUM-ORDER-01", "visual_guidance", "worked_parallel_example"),
    ),
)
def test_each_activity_has_a_stable_default_then_a_different_support(
    skill, first_support, second_support
):
    first, first_mode = _escalate_scaffold(
        "step_by_step_guidance", condition="proposed", attempt_count=1, skill_id=skill
    )
    second, second_mode = _escalate_scaffold(
        "step_by_step_guidance", condition="proposed", attempt_count=2, skill_id=skill
    )
    third, third_mode = _escalate_scaffold(
        "visual_guidance", condition="proposed", attempt_count=3, skill_id=skill
    )
    assert (first, first_mode) == (first_support, "activity_default")
    assert (second, second_mode) == (second_support, "activity_support_escalation")
    assert (third, third_mode) == ("step_by_step_guidance", "activity_support_escalation")


def test_only_valid_independent_success_can_become_a_support_preference():
    preferred, analysis = _preferred_support_from_history(
        (
            {
                "condition": "proposed",
                "validity": "valid",
                "model2": {"selected_action": "visual_guidance"},
                "measurement": {
                    "after_earned": 0,
                    "after_maximum": 1,
                    "raw_independence_gain": "0",
                },
            },
            {
                "condition": "proposed",
                "validity": "valid",
                "model2": {"selected_action": "worked_parallel_example"},
                "measurement": {
                    "after_earned": 1,
                    "after_maximum": 1,
                    "raw_independence_gain": "1",
                },
            },
        )
    )
    assert preferred == "worked_parallel_example"
    assert analysis["basis"] == "valid_unsupported_after_outcomes"
    assert analysis["supported_correctness_used"] is False


def test_retry_cursor_resumes_after_independent_failure_and_resets_after_success():
    failed = {
        "condition": "proposed",
        "validity": "valid",
        "measurement": {"after_earned": 0, "after_maximum": 1},
    }
    passed = {
        "condition": "proposed",
        "validity": "valid",
        "measurement": {"after_earned": 1, "after_maximum": 1},
    }
    assert _next_support_attempt_from_history((failed,)) == 2
    assert _next_support_attempt_from_history((failed, failed)) == 3
    assert _next_support_attempt_from_history((failed, passed)) == 1


def test_future_episode_starts_with_support_that_previously_led_to_independent_success(service):
    flow, _ = service
    skill = "G5-MAT-NUM-POSITION-01"
    _, _, _, learned_from = _finish(
        flow,
        _open(flow, skill, key_suffix="learn-preference"),
        attempt_count=2,
    )
    assert learned_from["model2"]["selected_action"] == "worked_parallel_example"

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
    assert response["support"]["scaffold_type"] == "worked_parallel_example"
    assert state["model2"]["support_selection_mode"] == "learned_activity_preference"
    assert state["model2"]["learner_activity_support_preference"]["preferred_support"] == (
        "worked_parallel_example"
    )


def test_new_episode_resumes_escalation_after_prior_independent_failure(service):
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
    state = flow.reconstruct(episode_id)["state"]
    assert response["support"]["scaffold_type"] == "worked_parallel_example"
    assert state["model2"]["client_attempt_count"] == 1
    assert state["model2"]["attempt_count"] == 2
    assert state["model2"]["support_selection_mode"] == "activity_support_escalation"


@pytest.mark.parametrize("skill", [skill.skill_id for skill in ATOMIC_SKILLS])
def test_support_animates_the_exact_failed_item_and_server_solution(service, skill):
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

    state = flow.reconstruct(episode_id)["state"]
    worked = response["support"]["game_manifest"]["worked_example"]
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
    assert state["scaffold_exposure"]["answer_revealing"] is True


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
    flow.submit_before(
        episode_id, option_id=wrong, response_time_ms=1, idempotency_key="contam-before"
    )
    state = flow.reconstruct(episode_id)["state"]
    exposure = state["scaffold_exposure"]
    flow.complete_support(
        episode_id,
        duration_ms=1,
        steps_viewed=1,
        manifest_revision_id=exposure["manifest_revision_id"],
        grouped_count=0,
        group_sizes=(),
        interaction_summary={
            "completed": True,
            "renderer_id": f"{state['chapter']}:{exposure['scaffold_type']}",
            "parallel_example_id": f"{state['skill_id']}:parallel-support-v1",
            "support_actions": 3,
        },
        idempotency_key="contam-support",
    )
    flow.withdraw_support(
        episode_id,
        request_id=uuid4(),
        support_revision_id=exposure["revision_id"],
        manifest_revision_id=exposure["manifest_revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key="contam-withdraw",
    )
    probe.contaminate(state["probe_reservation_id"])
    result = flow.present_after(episode_id, idempotency_key="contam-present")
    final = flow.reconstruct(episode_id)["state"]
    assert result["status"] == "invalidated"
    assert final["exclusion_reasons"] == ["PRIOR_PROBE_EXPOSURE"]
    assert final["policy_updates"] == []
    session.close()

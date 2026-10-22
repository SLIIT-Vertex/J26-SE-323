from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.gamification.application.research_accuracy import accuracy_report, wilson
from app.gamification.application.research_glossary import STATUS_NAMES, plain_status
from app.gamification.infrastructure.gateways.research_learning_state import read_learning_state
from app.gamification.modeling.misconception_inference.learner_prior import (
    apply_learner_prior,
    prior_errors,
)
from app.gamification.modeling.support_selection.support_order import (
    MATHEMATICS_ORDER,
    choose_support_order,
    rank_support_history,
)


def history(*, success=True, exhausted=False, condition="proposed", validity="valid"):
    return {
        "condition": condition,
        "validity": validity,
        "measurement": {
            "raw_independence_gain": "1" if success else "0",
            "after_earned": int(success),
            "after_maximum": 1,
        },
        "support_loop": {
            "stop_reason": "order_exhausted" if exhausted else "supported_success",
            "types_used": ["visual_guidance", "step_by_step_guidance"],
            "rounds": [
                {"scaffold_type": "visual_guidance", "outcome": "failed"},
                {
                    "scaffold_type": "step_by_step_guidance",
                    "outcome": "failed" if exhausted else "succeeded",
                },
            ],
        },
    }


def choose(**kwargs):
    return choose_support_order(
        subject="MAT",
        condition="proposed",
        model1_label="wrong_column",
        model1_uncertain=False,
        eligible=MATHEMATICS_ORDER,
        renderable=MATHEMATICS_ORDER,
        **kwargs,
    )


def test_only_the_successful_round_receives_the_independent_result():
    ranking = rank_support_history([history()])
    assert ranking.preferred == "step_by_step_guidance"
    assert ranking.by_support["visual_guidance"]["independent_successes"] == 0
    assert ranking.by_support["visual_guidance"]["episodes"] == 0
    assert ranking.by_support["visual_guidance"]["did_not_help"] == 1
    assert ranking.by_support["step_by_step_guidance"]["independent_successes"] == 1
    assert rank_support_history([history(exhausted=True)]).preferred is None
    assert (
        rank_support_history([history(condition="baseline"), history(validity="invalid")]).preferred
        is None
    )


def test_ranking_uses_failed_round_count_before_subject_tie_break():
    a = history()
    b = history()
    b["support_loop"]["rounds"] = [{"scaffold_type": "visual_guidance", "outcome": "succeeded"}]
    ranking = rank_support_history([a, b])
    assert ranking.preferred == "step_by_step_guidance"


def test_legacy_single_help_keeps_its_one_type():
    h = history()
    del h["support_loop"]
    h["model2"] = {"selected_action": "visual_guidance"}
    assert rank_support_history([h]).preferred == "visual_guidance"


def test_fresh_state_changes_order_but_two_proven_successes_win():
    reading = {"status": "available", "state": "disengaged"}
    assert choose(learning_state_input=reading).first == "simpler_same_game"
    assert choose(history=[history()], learning_state_input=reading).first == "simpler_same_game"
    decision = choose(history=[history(), history()], learning_state_input=reading)
    assert decision.first == "step_by_step_guidance"
    assert not decision.learning_state_input["changed_first_help"]
    assert (
        choose(learning_state_input={"status": "not_available", "reason": "STALE"}).first
        == "visual_guidance"
    )
    confused = choose(learning_state_input={"status": "available", "state": "confused"})
    assert confused.order[0] == "visual_guidance"
    assert confused.order.index("worked_parallel_example") == 3


def test_state_specific_history_is_used_only_with_enough_evidence():
    calm = history()
    calm["model2"] = {"learning_state_input": {"state": "calm"}}
    confused = history()
    confused["support_loop"]["rounds"] = [
        {"scaffold_type": "simpler_same_game", "outcome": "succeeded"}
    ]
    confused["model2"] = {"learning_state_input": {"state": "confused"}}
    decision = choose(
        history=[calm, calm, calm, confused, confused],
        learning_state_input={"status": "available", "state": "confused"},
    )
    assert decision.first == "simpler_same_game"


def test_prior_only_uses_last_five_unsupported_answers_and_records_replay_inputs():
    attempts = [
        {"role": "unsupported_before", "correct": False, "structured_error_code": "a"}
        for _ in range(8)
    ]
    attempts += [{"role": "supported_practice", "correct": False, "structured_error_code": "b"}]
    errors = prior_errors([{"attempts": attempts}])
    assert errors == ["a"] * 5
    belief = {"probabilities": {"a": 0.58, "b": 0.42}, "predicted_label": "a"}
    posterior = apply_learner_prior(belief, errors)
    assert posterior["prior_counts"] == {"a": 5, "b": 0}
    assert posterior["confidence"] > 0.58
    assert sum(posterior["probabilities"].values()) == pytest.approx(1)
    assert posterior["likelihood"] == belief["probabilities"]
    assert not apply_learner_prior({"probabilities": {"a": 0.51, "b": 0.49}}, [])[
        "learner_prior_used"
    ]
    assert apply_learner_prior({"probabilities": {"a": 0.51, "b": 0.49}}, [])["low_confidence"]


def test_learning_state_rejects_old_and_other_session_readings():
    now, learner = datetime.now(UTC), uuid4()
    result = SimpleNamespace(
        status="AVAILABLE",
        support_need=0.8,
        observed_at=now - timedelta(seconds=20),
        session_id="current",
        recommended_action="request_reengagement_support",
    )

    class Provider:
        def get_support_need(self, request):
            assert request.session_id == "current"
            assert request.max_age_ms == 60000
            return result

    values = {"learner_id": learner, "skill_id": "MATH_01", "session_id": "current", "at": now}
    assert read_learning_state(Provider(), **values)["state"] == "disengaged"
    result.session_id = "previous"
    assert read_learning_state(Provider(), **values)["reason"] == "STALE"
    result.session_id, result.observed_at = "current", now - timedelta(minutes=2)
    assert read_learning_state(Provider(), **values)["reason"] == "STALE"


def run(index, *, seeded=False):
    state = history()
    state.update(
        episode_id=str(uuid4()),
        skill_id="skill-a",
        area_id="G5-AREA-MAT-01",
        status="completed",
        model1={"probabilities": {"a": 0.7, "b": 0.3}},
        events=[{"occurred_at": f"2026-10-{index + 1:02}T00:00:00"}],
        attempts=[
            {"role": "unsupported_before", "correct": False, "structured_error_code": "a"},
            {"role": "unsupported_after", "correct": False, "structured_error_code": "a"},
        ],
    )
    if seeded:
        state["seed_source"] = "demo-seed-v1"
    return {"state": state, "status": "completed", "updated_at": datetime.now(UTC)}


def test_accuracy_known_answers_thresholds_and_scripted_data_exclusion():
    # A small sample is shown, flagged as an early sign rather than hidden.
    short = accuracy_report([run(i) for i in range(19)])
    agreement = short["models"][0]["metrics"][0]
    assert agreement["count"] == 19 and agreement["value"] == 1
    assert agreement["small_sample"] is True and agreement["interval"] is not None
    enough = accuracy_report([run(i) for i in range(20)] + [run(21, seeded=True)])
    assert enough["models"][0]["metrics"][0]["value"] == 1
    assert enough["models"][0]["metrics"][0]["small_sample"] is False
    assert enough["models"][0]["metrics"][0]["count"] == 20
    assert enough["models"][0]["metrics"][1]["small_sample"] is True
    assert accuracy_report([])["models"][0]["metrics"][0]["value"] is None
    calibrated = accuracy_report([run(i) for i in range(30)])
    assert calibrated["models"][0]["metrics"][1]["value"] == pytest.approx(0.18)
    assert len(calibrated["models"][0]["calibration"]) == 1
    assert wilson(0, 0) is None
    assert wilson(10, 20) == pytest.approx([0.299298, 0.700702], abs=1e-5)


def test_status_glossary_never_exposes_a_code():
    for code in STATUS_NAMES:
        assert "_" not in plain_status(code)
    assert plain_status("future_internal_code") == "This step needs a technical review"


def test_glossary_covers_every_fair_test_exclusion_written_by_the_meter():
    import ast
    import inspect

    from app.gamification.application.research_glossary import EXCLUSIONS
    from app.gamification.modeling.independence_gain import episode_measurement

    tree = ast.parse(inspect.getsource(episode_measurement))
    codes = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert codes <= set(EXCLUSIONS)


def test_learning_state_can_request_focus_help_when_confusion_is_uncertain():
    now = datetime.now(UTC)

    class Provider:
        def get_support_need(self, request):
            return SimpleNamespace(
                status="UNCERTAIN",
                support_need=None,
                observed_at=now,
                session_id="current",
                recommended_action="request_reengagement_support",
            )

    reading = read_learning_state(
        Provider(), learner_id=uuid4(), skill_id="MAT-NUM", session_id="current", at=now
    )
    assert reading["state"] == "disengaged" and reading["status"] == "available"

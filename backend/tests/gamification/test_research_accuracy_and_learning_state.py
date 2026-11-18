"""The research accuracy checks, the dashboard glossary and the Learning State reading."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.gamification.application.research_dashboard.accuracy import (
    accuracy_report,
    model_check,
    wilson,
)
from app.gamification.application.research_dashboard.glossary import STATUS_NAMES, plain_status
from app.gamification.infrastructure.gateways.research_learning_state import read_learning_state


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

    from app.gamification.application.research_dashboard.glossary import EXCLUSIONS
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


def test_model_check_passes_only_when_the_low_end_beats_the_reference():
    def check(values, reference, reference_count=None):
        return model_check(
            "q",
            "r",
            values,
            reference=reference,
            reference_label="x",
            reference_count=reference_count,
        )["status"]

    assert check([1] * 19, 0.5) == "not_enough_data"
    assert check([1] * 18 + [0] * 2, 0.5) == "passing"
    assert check([1] * 10 + [0] * 10, 0.5) == "not_passing"
    assert check([1] * 20, None) == "not_enough_data"
    assert check([1] * 20, 0.2, reference_count=5) == "not_enough_data"
    # Guessing between two reasons is 50%, so twenty confirmed reasons pass.
    report = accuracy_report([run(i) for i in range(20)])
    misconception, support, gain = report["models"]
    assert misconception["check"]["reference"] == 0.5
    assert misconception["check"]["status"] == "passing"
    assert support["check"]["status"] == "not_enough_data"
    assert gain["kind"] == "measurement" and "check" not in gain

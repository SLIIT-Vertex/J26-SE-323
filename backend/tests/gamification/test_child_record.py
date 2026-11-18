"""This child's record with each help, as the research views describe it."""

from app.gamification.application.research_dashboard.child_record import child_record
from app.gamification.modeling.support_selection.baseline_order import MATHEMATICS_ORDER


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


def record(states):
    return child_record(states, order=MATHEMATICS_ORDER)


def test_only_the_successful_round_receives_the_independent_result():
    ranking = record([history()])
    assert ranking.preferred == "step_by_step_guidance"
    assert ranking.by_support["visual_guidance"]["independent_successes"] == 0
    assert ranking.by_support["visual_guidance"]["episodes"] == 0
    assert ranking.by_support["visual_guidance"]["did_not_help"] == 1
    assert ranking.by_support["step_by_step_guidance"]["independent_successes"] == 1
    assert record([history(exhausted=True)]).preferred is None
    assert record([history(condition="baseline"), history(validity="invalid")]).preferred is None


def test_fewer_failed_rounds_break_a_tie_before_the_subject_order():
    a = history()
    b = history()
    b["support_loop"]["rounds"] = [{"scaffold_type": "visual_guidance", "outcome": "succeeded"}]
    assert record([a, b]).preferred == "step_by_step_guidance"


def test_an_older_single_help_episode_credits_its_one_help():
    single = history()
    del single["support_loop"]
    single["model2"] = {"selected_action": "visual_guidance"}
    assert record([single]).preferred == "visual_guidance"
    assert (
        record([single]).as_record()["by_support"]["visual_guidance"]["mean_independence_gain"]
        == "1"
    )

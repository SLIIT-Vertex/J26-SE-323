from app.gamification.application.research_dashboard.explain import (
    episode_summary,
    explain_follow_up,
    explain_rounds,
)
from app.gamification.application.research_dashboard.history import _help_given


def _round(number, support, outcome):
    return {"round_number": number, "scaffold_type": support, "outcome": outcome, "stages": []}


def _followed_state():
    return {
        "episode_id": "e1",
        "skill_id": "G5-MAT-NUM-POSITION-01",
        "support_loop": {"rounds": [_round(1, "visual_guidance", "viewed")]},
        "follow_up": {
            "status": "finished",
            "finish_reason": "independent_success",
            "support_loop": {
                "rounds": [
                    _round(1, "step_by_step_guidance", "failed"),
                    _round(2, "conceptual_reexplanation", "succeeded"),
                ]
            },
            "attempts": [{"role": "follow_up_practice", "correct": True}],
        },
        "events": [],
    }


def test_rounds_include_the_help_given_after_a_failed_after_question():
    rounds = explain_rounds(_followed_state())

    assert [(r["position"], r["phase"], r["scaffold_type"]) for r in rounds] == [
        (1, "measured", "visual_guidance"),
        (2, "follow_up", "step_by_step_guidance"),
        (3, "follow_up", "conceptual_reexplanation"),
    ]
    assert rounds[1]["rule"] == "This help was not enough, so the next help was tried."


def test_follow_up_is_explained_and_counted_in_the_summary():
    state = _followed_state()

    follow_up = explain_follow_up(state)
    summary = episode_summary({"state": state, "status": "completed"})

    assert follow_up["finish_reason"] == "independent_success"
    assert follow_up["practice"] == [{"correct": True, "error": None}]
    assert summary["help_types"] == [
        "visual_guidance",
        "step_by_step_guidance",
        "conceptual_reexplanation",
    ]
    assert summary["follow_up_result"] == "independent_success"


def test_a_single_help_game_from_before_the_help_loop_still_shows_its_round():
    state = {
        "scaffold_exposure": {
            "scaffold_type": "worked_parallel_example",
            "presented_at": "2026-10-19T21:16:40+00:00",
            "completed_at": "2026-10-19T21:16:46+00:00",
        },
        "supported_correctness": None,
    }

    rounds = explain_rounds(state)

    assert [(r["phase"], r["scaffold_type"], r["outcome"]) for r in rounds] == [
        ("measured", "worked_parallel_example", "viewed")
    ]
    assert explain_follow_up(state) is None


def test_support_history_says_which_helps_were_actually_given():
    lines = _help_given(_followed_state())

    assert len(lines) == 2
    assert lines[0].startswith("Help given: ")
    assert lines[1].startswith("More help after the try alone: ")
    assert " → " in lines[1]

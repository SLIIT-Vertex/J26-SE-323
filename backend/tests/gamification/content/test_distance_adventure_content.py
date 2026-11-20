import pytest

from app.gamification.content.distance_adventure import (
    canonical_arithmetic,
    correct_response,
    format_metres_component,
    generate_item,
    normalize_distance,
    split_metres,
    validate_constructed_response,
)


def test_distance_integer_conversion_and_zero_padding():
    assert split_metres(4075) == (4, 75)
    assert normalize_distance(3, 1125) == (4, 125)
    assert format_metres_component(75) == "075"

def test_addition_trace_requires_regrouping_and_complete_working():
    item = generate_item("G5-MAT-LENGTH-ADD-01", role="unsupported_before", seed=4)
    expected = correct_response(item.game_data)
    assert expected["exchange_or_regrouping_used"] is True
    assert expected["carried_or_borrowed_kilometres"] == 1
    correct, _, _ = validate_constructed_response(item, expected)
    assert correct is True
    wrong = {**expected, "working_steps": ["final only"]}
    assert validate_constructed_response(item, wrong)[0] is False

def test_subtraction_trace_borrows_one_thousand_metres():
    row = canonical_arithmetic("subtract", 8, 125, 3, 460)
    assert row["carried_or_borrowed_kilometres"] == 1
    assert row["result_kilometres"] == 4
    assert row["result_metres"] == 665
    assert "metres:1125-460=665" in row["working_steps"]

def test_story_context_is_backend_authoritative():
    item = generate_item("G5-MAT-LENGTH-PROBLEM-01", role="unsupported_before", seed=2)
    expected = correct_response(item.game_data)
    assert validate_constructed_response(item, expected)[0]
    wrong = {**expected, "contextual_answer": "distance_remaining:0:0"}
    assert validate_constructed_response(item, wrong)[0] is False

def test_negative_distance_is_rejected():
    with pytest.raises(ValueError, match="NEGATIVE_DISTANCE"):
        canonical_arithmetic("subtract", 1, 0, 2, 0)


def test_market_road_missions_and_garden_help():
    from app.gamification.content.distance_adventure import SKILLS

    chapters = {skill_id: skill.chapter for skill_id, skill in SKILLS.items()}
    assert chapters["G5-MAT-LENGTH-RELATION-01"] == "tikki_garden"
    assert chapters["G5-MAT-LENGTH-CONVERT-01"] == "tikki_garden"
    for skill_id in ("G5-MAT-LENGTH-ADD-01", "G5-MAT-LENGTH-SUBTRACT-01", "G5-MAT-LENGTH-PROBLEM-01"):
        assert chapters[skill_id] == "market_road"
    for seed in range(12):
        item = generate_item("G5-MAT-LENGTH-SUBTRACT-01", role="unsupported_after", seed=seed)
        assert correct_response(item.game_data)["exchange_or_regrouping_used"] is True
        assert "පොළ" in item.prompt_si


def test_a_story_with_the_other_operation_is_scored_wrong_not_rejected():
    item = next(
        candidate
        for seed in range(40)
        if (candidate := generate_item("G5-MAT-LENGTH-PROBLEM-01", role="unsupported_before", seed=seed)).game_data["operation"] == "add"
    )
    game = item.game_data
    working = canonical_arithmetic("subtract", game["left_kilometres"], game["left_metres"], game["right_kilometres"], game["right_metres"])
    arithmetic = {
        "kind": "distance_arithmetic",
        "left_kilometres": game["left_kilometres"],
        "left_metres": game["left_metres"],
        "right_kilometres": game["right_kilometres"],
        "right_metres": game["right_metres"],
        **working,
    }
    response = {
        "kind": "distance_story",
        "problem_id": game["problem_id"],
        "operation": "subtract",
        "working_steps": arithmetic,
        "result_kilometres": working["result_kilometres"],
        "result_metres": working["result_metres"],
        "contextual_answer": f"distance_remaining:{working['result_kilometres']}:{working['result_metres']}",
    }
    correct, error, _ = validate_constructed_response(item, response)
    assert correct is False
    assert error == "wrong_story_operation"

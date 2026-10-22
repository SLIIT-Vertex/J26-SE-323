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

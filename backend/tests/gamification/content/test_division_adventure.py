import pytest

from app.gamification.content.division_adventure import (
    canonical_long_division,
    correct_response,
    generate_item,
    quotient_and_remainder,
    validate_constructed_response,
    validate_operands,
)


def test_canonical_long_division_without_remainder_contains_every_paper_step():
    steps = canonical_long_division(84, 4)
    assert steps == [
        {"step_index": 0, "partial_dividend": 8, "quotient_digit": 2, "quotient_column": 0, "partial_product": 8, "subtraction_result": 0, "brought_down_digit": 4},
        {"step_index": 1, "partial_dividend": 4, "quotient_digit": 1, "quotient_column": 1, "partial_product": 4, "subtraction_result": 0, "brought_down_digit": None},
    ]
    assert quotient_and_remainder(84, 4) == (21, 0)


def test_canonical_long_division_preserves_zero_quotient_digit_and_remainder():
    steps = canonical_long_division(408, 4)
    assert [step["quotient_digit"] for step in steps] == [1, 0, 2]
    assert [step["quotient_column"] for step in steps] == [0, 1, 2]
    remainder_steps = canonical_long_division(157, 4)
    assert remainder_steps[-1]["subtraction_result"] == 1
    assert quotient_and_remainder(157, 4) == (39, 1)


def test_divisor_and_remainder_rules_reject_invalid_values():
    with pytest.raises(ValueError, match="DIVISION_OPERANDS_OUT_OF_RANGE"):
        validate_operands(20, 0)
    quotient, remainder = quotient_and_remainder(997, 9)
    assert 0 <= remainder < 9
    assert quotient * 9 + remainder == 997


def test_written_trace_is_authoritative_not_only_final_quotient():
    item = generate_item("G5-MAT-DIV-WRITTEN-01", role="unsupported_before", seed=721)
    response = correct_response(item.game_data)
    assert validate_constructed_response(item, response)[0] is True
    response["working_steps"][0]["partial_product"] += 1
    assert validate_constructed_response(item, response)[:2] == (False, "incorrect_multiplication_fact")


def test_story_requires_contextual_quotient_and_leftover_meaning():
    item = generate_item("G5-MAT-DIV-STORY-01", role="unsupported_before", seed=721)
    response = correct_response(item.game_data)
    assert validate_constructed_response(item, response)[0] is True
    response["contextual_interpretation"] = "leftover_is_quotient"
    assert validate_constructed_response(item, response)[:2] == (False, "incorrect_contextual_interpretation")


def test_equal_sharing_evidence_contains_actual_group_quantities():
    item = generate_item("G5-MAT-DIV-SHARE-01", role="unsupported_before", seed=721)
    response = correct_response(item.game_data)
    correct, _, normalized = validate_constructed_response(item, response)
    assert correct is True
    assert sum(normalized["group_quantities"]) == normalized["dividend"]
    assert len(set(normalized["group_quantities"])) == 1

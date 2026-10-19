import pytest

from app.gamification.content.capacity_adventure import (
    canonical_arithmetic,
    correct_response,
    format_capacity,
    generate_item,
    validate_constructed_response,
)


def test_integer_capacity_format_and_valid_graduated_vessel():
    assert format_capacity(3600) == "3 l 600 ml"
    item = generate_item("G5-MAT-CAPACITY-READ-01", role="unsupported_before", seed=17)
    response = correct_response(item.game_data)
    assert response["capacity_ml"] % 100 == 0
    assert validate_constructed_response(item, response)[0] is True


def test_multiple_one_litre_compositions_and_overflow():
    item = generate_item("G5-MAT-CAPACITY-COMPOSE-01", role="unsupported_before", seed=7)
    for selected in ([500, 500], [250, 250, 250, 250], [200] * 5, [100] * 10, [1000]):
        response = {"kind": "capacity_composition", "target_ml": 1000, "selected_portions_ml": selected, "portion_counts": {str(value): selected.count(value) for value in sorted(set(selected))}, "constructed_total_ml": 1000, "overflow_ml": 0}
        assert validate_constructed_response(item, response)[0] is True
    overflow = [500, 500, 100]
    response = {"kind": "capacity_composition", "target_ml": 1000, "selected_portions_ml": overflow, "portion_counts": {"100": 1, "500": 2}, "constructed_total_ml": 1100, "overflow_ml": 100}
    assert validate_constructed_response(item, response)[:2] == (False, "overflowed_target")


def test_conversion_and_compound_arithmetic_with_exchange_and_borrow():
    conversion = generate_item("G5-MAT-CAPACITY-CONVERT-01", role="unsupported_after", seed=11)
    answer = correct_response(conversion.game_data)
    assert answer["source_total_ml"] == answer["result_litres"] * 1000 + answer["result_millilitres"]
    added = canonical_arithmetic("add", 8, 250, 4, 750)
    assert (added["result_litres"], added["result_millilitres"], added["exchange_used"]) == (13, 0, True)
    subtracted = canonical_arithmetic("subtract", 14, 600, 5, 750)
    assert (subtracted["result_litres"], subtracted["result_millilitres"], subtracted["exchange_used"]) == (8, 850, True)
    with pytest.raises(ValueError, match="NEGATIVE_CAPACITY"):
        canonical_arithmetic("subtract", 1, 0, 2, 0)


def test_ordered_working_and_delivery_are_server_validated():
    arithmetic = generate_item("G5-MAT-CAPACITY-ARITHMETIC-01", role="unsupported_before", seed=19)
    response = correct_response(arithmetic.game_data)
    response["working_steps"] = list(reversed(response["working_steps"]))
    assert validate_constructed_response(arithmetic, response)[:2] == (False, "correct_result_invalid_working")
    delivery = generate_item("G5-MAT-CAPACITY-PROBLEM-01", role="unsupported_before", seed=23)
    assert validate_constructed_response(delivery, correct_response(delivery.game_data))[0] is True

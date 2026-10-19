import pytest

from app.gamification.content.money_adventure import (
    canonical_arithmetic,
    correct_response,
    denomination_total,
    format_money,
    generate_item,
    normalize_money,
    shopping_totals,
    split_money,
    validate_constructed_response,
)


def test_integer_cent_normalization_and_formatting():
    assert split_money(16505) == (165, 5)
    assert normalize_money(165, 125) == (166, 25)
    assert format_money(16500) == "165.00"
    assert format_money(16505) == "165.05"


def test_addition_without_and_with_carrying():
    plain = canonical_arithmetic("add", 16520, 24230)
    assert plain["exchange_used"] is False
    assert plain["result_in_cents"] == 40750
    carried = canonical_arithmetic("add", 16575, 24250)
    assert carried["cent_subtotal_or_adjustment"] == 125
    assert carried["carried_or_borrowed_rupees"] == 1
    assert carried["result_in_cents"] == 40825


def test_subtraction_without_and_with_borrowing():
    plain = canonical_arithmetic("subtract", 50075, 16525)
    assert plain["exchange_used"] is False
    borrowed = canonical_arithmetic("subtract", 50000, 16575)
    assert borrowed["carried_or_borrowed_rupees"] == 1
    assert borrowed["result_in_cents"] == 33425
    assert "adjust:500->499:0->100" in borrowed["working_steps"]


def test_amount_construction_accepts_multiple_valid_combinations():
    item = generate_item("G5-MAT-MONEY-COMPOSE-01", role="unsupported_before", seed=2)
    target = int(item.game_data["target_in_cents"])
    expected = correct_response(item.game_data)
    assert validate_constructed_response(item, expected)[0]
    alternative = ["coin-1"] * (target // 100)
    response = {
        "kind": "amount_construction",
        "target_in_cents": target,
        "selected_denominations": alternative,
        "denomination_counts": {"coin-1": len(alternative)},
        "constructed_total_in_cents": denomination_total(alternative),
    }
    assert validate_constructed_response(item, response)[0]


def test_recognition_requires_classification_and_ordering():
    item = generate_item("G5-MAT-MONEY-DENOMINATION-01", role="unsupported_before", seed=1)
    expected = correct_response(item.game_data)
    assert validate_constructed_response(item, expected)[0]
    wrong = {**expected, "placements": list(reversed(expected["placements"]))}
    assert validate_constructed_response(item, wrong)[1] == "incorrect_value_ordering"


def test_price_quantity_total_change_and_working_trace():
    lines, total = shopping_totals(["lime-1kg", "papaya-1kg"], [2, 1])
    assert lines == [33000, 26000]
    assert total == 59000
    item = generate_item("G5-MAT-MONEY-SHOP-01", role="unsupported_before", seed=4)
    expected = correct_response(item.game_data)
    assert validate_constructed_response(item, expected)[0]
    invalid = {**expected, "working_steps": ["final only"]}
    assert validate_constructed_response(item, invalid)[1] == "correct_result_invalid_working"


def test_negative_money_is_rejected():
    with pytest.raises(ValueError, match="NEGATIVE_MONEY"):
        canonical_arithmetic("subtract", 100, 200)

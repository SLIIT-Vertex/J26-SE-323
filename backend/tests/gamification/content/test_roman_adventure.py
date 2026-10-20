import pytest

from app.gamification.content.roman_adventure import (
    ROMANS,
    correct_response,
    evaluate_roman,
    generate_item,
    int_to_roman,
    roman_to_int,
    validate_constructed_response,
)


def test_canonical_round_trip_for_one_to_twenty() -> None:
    for value, roman in ROMANS.items():
        assert int_to_roman(value) == roman
        assert roman_to_int(roman) == value


@pytest.mark.parametrize("value", ["iiii", "viv", "vx", "iix", ""])
def test_noncanonical_forms_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="NONCANONICAL"):
        roman_to_int(value)


def test_match_and_emoji_require_complete_constructed_evidence() -> None:
    for skill in ("G5-MAT-ROMAN-MATCH-01", "G5-MAT-ROMAN-COUNT-01"):
        item = generate_item(skill, role="unsupported_before", seed=41)
        response = correct_response(item.game_data)
        correct, code, _ = validate_constructed_response(item, response)
        assert correct is True
        assert code == "correct"


def test_arithmetic_uses_numeric_values_then_canonical_result() -> None:
    assert evaluate_roman("vii", "subtract", "iv") == 3
    item = generate_item("G5-MAT-ROMAN-ARITHMETIC-01", role="unsupported_before", seed=9)
    response = correct_response(item.game_data)
    assert validate_constructed_response(item, response)[0] is True


def test_public_item_contains_no_answer() -> None:
    item = generate_item("G5-MAT-ROMAN-MATCH-01", role="unsupported_before", seed=4)
    assert "correct_response" not in item.game_data
    assert "answer" not in item.game_data

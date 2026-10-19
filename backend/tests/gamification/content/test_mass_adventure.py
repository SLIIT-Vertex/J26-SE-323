import pytest

from app.gamification.content.mass_adventure import (
    ATOMIC_SKILLS,
    balance_difference,
    canonical_arithmetic,
    correct_response,
    format_mass,
    generate_item,
    normalize_mass,
    split_mass,
    validate_constructed_response,
)


def test_mass_package_has_exactly_five_ordered_activities_and_fresh_probes():
    assert [skill.response_kind for skill in ATOMIC_SKILLS] == [
        "mass_instrument", "mass_balance", "mass_conversion", "mass_arithmetic", "mass_market_mission",
    ]
    before = generate_item("G5-MAT-MASS-BALANCE-01", role="unsupported_before", seed=42)
    after = generate_item("G5-MAT-MASS-BALANCE-01", role="unsupported_after", seed=42)
    assert before.revision_id != after.revision_id
    assert before.parallel_family_id == after.parallel_family_id


def test_integer_mass_logic_regroups_borrows_and_formats_three_gram_places():
    assert split_mass(3600) == (3, 600)
    assert normalize_mass(2, 1750) == (3, 750)
    assert format_mass(3000) == "3 kg 000 g"
    assert canonical_arithmetic("add", 8, 250, 7, 750)["result_kilograms"] == 16
    assert canonical_arithmetic("subtract", 14, 600, 5, 750)["result_grams"] == 850
    with pytest.raises(ValueError, match="NEGATIVE_MASS"):
        canonical_arithmetic("subtract", 1, 0, 2, 0)


def test_balance_accepts_multiple_standard_mass_combinations_and_removal_state():
    item = generate_item("G5-MAT-MASS-BALANCE-01", role="unsupported_before", seed=42)
    item.game_data["target_mass_g"] = 1000
    first = correct_response(item.game_data)
    alternative = {**first, "selected_mass_denominations_g": [500, 500], "denomination_counts": {"500": 2}}
    assert validate_constructed_response(item, first)[0] is True
    assert validate_constructed_response(item, alternative)[0] is True
    removed = {**alternative, "selected_mass_denominations_g": [500], "denomination_counts": {"500": 1}, "selected_total_g": 500, "balance_difference_g": -500, "balanced": False}
    assert validate_constructed_response(item, removed)[0] is False
    assert balance_difference(1000, [500]) == -500


def test_instrument_conversion_arithmetic_and_market_payloads_are_server_scored():
    for skill in ATOMIC_SKILLS:
        item = generate_item(skill.skill_id, role="unsupported_before", seed=9)
        response = correct_response(item.game_data)
        correct, _, normalized = validate_constructed_response(item, response)
        assert correct is True
        assert normalized["kind"] == skill.response_kind
    arithmetic = generate_item("G5-MAT-MASS-ARITHMETIC-01", role="unsupported_before", seed=3)
    invalid = correct_response(arithmetic.game_data)
    invalid["working_steps"] = list(reversed(invalid["working_steps"]))
    assert validate_constructed_response(arithmetic, invalid)[:2] == (False, "correct_result_invalid_working")

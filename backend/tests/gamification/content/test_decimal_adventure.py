from copy import deepcopy

import pytest

from app.gamification.content.decimal_adventure import (
    ATOMIC_SKILLS,
    MISCONCEPTIONS,
    correct_response,
    decimal_to_tenths,
    generate_item,
    generate_reading_matches,
    infer_belief,
    tenths_to_decimal,
    validate_constructed_response,
    validate_selected_sections,
    validate_tenths,
)


def test_decimal_package_has_exactly_four_activities():
    assert [skill.response_kind for skill in ATOMIC_SKILLS] == [
        "decimal_reading_match", "decimal_tenths_shading",
        "tenths_fraction_to_decimal", "decimal_to_tenths_fraction",
    ]


@pytest.mark.parametrize("tenths", range(1, 10))
def test_all_tenths_convert_both_directions(tenths):
    assert validate_tenths(tenths) == tenths
    assert tenths_to_decimal(tenths) == f"0.{tenths}"
    assert decimal_to_tenths(f"0.{tenths}") == (tenths, 10)


def test_reading_round_has_unique_one_to_one_matches():
    digits, tiles = generate_reading_matches(seed=15, role="unsupported_before")
    assert len(digits) == len(set(digits)) == 4
    assert len({tile["reading_id"] for tile in tiles}) == 4
    assert {tile["reading_id"] for tile in tiles} == {f"reading-{digit}" for digit in digits}


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_all_decimal_responses_are_server_scored(skill):
    item = generate_item(skill.skill_id, role="unsupported_before", seed=15)
    assert validate_constructed_response(item, correct_response(item.game_data))[0] is True


def test_any_equivalent_set_of_requested_equal_parts_is_accepted():
    item = generate_item("G5-MAT-DECIMAL-SHADE-01", role="unsupported_before", seed=8)
    response = correct_response(item.game_data)
    wanted = item.game_data["decimal_tenths"]
    response["selected_part_indices"] = list(range(10 - wanted, 10))
    response["selected_count"] = wanted
    assert validate_constructed_response(item, response)[0] is True


def test_duplicate_and_out_of_range_sections_are_rejected():
    with pytest.raises(ValueError, match="INVALID_TENTHS_SELECTION"):
        validate_selected_sections([1, 1])
    with pytest.raises(ValueError, match="INVALID_TENTHS_SELECTION"):
        validate_selected_sections([10])


def test_fraction_structure_and_first_error_are_authoritative():
    item = generate_item("G5-MAT-DECIMAL-TO-TENTHS-01", role="unsupported_before", seed=3)
    response = correct_response(item.game_data)
    response["entered_denominator"] = 100
    correct, error, normalized = validate_constructed_response(item, response)
    assert correct is False and error == "denominator_hundred"
    assert normalized["_feedback_column"] == "fraction"
    belief = infer_belief(error)
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert sum(belief["probabilities"].values()) == pytest.approx(1)


def test_public_items_have_no_answer_fields_and_parallel_revisions_are_immutable():
    for skill in ATOMIC_SKILLS:
        before = generate_item(skill.skill_id, role="unsupported_before", seed=22)
        after = generate_item(skill.skill_id, role="unsupported_after", seed=22)
        assert "correct_response" not in before.game_data and "answers" not in before.game_data
        assert before.revision_id != after.revision_id
        assert before.parallel_family_id == after.parallel_family_id


def test_decimal_reading_duplicate_match_is_not_accepted():
    item = generate_item("G5-MAT-DECIMAL-READ-01", role="unsupported_before", seed=6)
    response = deepcopy(correct_response(item.game_data))
    response["matches"][1]["reading_id"] = response["matches"][0]["reading_id"]
    assert validate_constructed_response(item, response)[:2] == (False, "incomplete_or_duplicate_matching")

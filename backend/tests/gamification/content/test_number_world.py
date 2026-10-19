from math import isclose

import pytest

from app.gamification.content.number_world import (
    ATOMIC_SKILLS,
    MISCONCEPTIONS,
    SCAFFOLDS,
    abacus_digits,
    construct_extreme,
    expanded_form,
    expanded_terms,
    generate_item,
    infer_belief,
    order_numbers,
    scaffold_decision,
    validate_constructed_response,
)


def test_atomic_skills_cover_requested_number_outcomes_without_cross_skill_pairs():
    assert len(ATOMIC_SKILLS) == 8
    assert {skill.chapter for skill in ATOMIC_SKILLS} == {
        "place_value_harbour",
        "firefly_abacus",
        "kite_workshop",
        "river_route_rally",
    }
    for skill in ATOMIC_SKILLS:
        before = generate_item(skill.skill_id, role="unsupported_before", seed=31)
        after = generate_item(skill.skill_id, role="unsupported_after", seed=31)
        assert before.parallel_family_id == after.parallel_family_id
        assert before.skill_id == after.skill_id == skill.skill_id
        assert before.revision_id != after.revision_id


def test_item_generation_is_deterministic_and_distractors_have_structured_errors():
    for skill in ATOMIC_SKILLS:
        first = generate_item(skill.skill_id, role="unsupported_before", seed=91)
        second = generate_item(skill.skill_id, role="unsupported_before", seed=91)
        assert first == second
        assert len(first.options) == 4
        assert first.correct_option_id in first.error_codes
        assert first.error_codes[first.correct_option_id] == "correct"
        assert all(
            code == "correct" or code in MISCONCEPTIONS for code in first.error_codes.values()
        )


def test_place_value_expansion_abacus_extremes_and_ordering():
    assert expanded_terms(42_305) == (40_000, 2_000, 300, 5)
    assert expanded_form(42_305) == "40000 + 2000 + 300 + 5"
    assert abacus_digits(40_205) == (0, 4, 0, 2, 0, 5)
    assert construct_extreme((0, 7, 2, 5), greatest=True) == 7520
    assert construct_extreme((0, 7, 2, 5), greatest=False) == 2057
    assert order_numbers((40_105, 40_015, 40_150), ascending=True) == (40_015, 40_105, 40_150)
    with pytest.raises(ValueError, match="LEADING_ZERO_ONLY"):
        construct_extreme((0, 0, 0), greatest=False)


def test_hundred_thousand_item_uses_the_textbook_successor_pattern():
    item = generate_item("G5-MAT-NUM-100000-01", role="unsupported_before", seed=19)

    assert "99 999 ට 1ක්" in item.prompt_si
    assert item.game_data["milestone_steps"] == (10, 100, 1_000, 10_000, 100_000)
    assert item.game_data["milestone_choices"] == (10_000, 100_000, 1_000_000)


@pytest.mark.parametrize(
    "skill_id",
    ("G5-MAT-NUM-POSITION-01", "G5-MAT-NUM-REPRESENTED-01"),
)
def test_place_value_target_digit_is_present_exactly_once(skill_id):
    for seed in range(100):
        item = generate_item(skill_id, role="unsupported_before", seed=seed)
        number = str(item.game_data["number"])
        digit = str(item.game_data["digit"])
        place = int(item.game_data["place"])

        assert number.count(digit) == 1
        assert number[-place - 1] == digit


def test_abacus_and_expansion_prompts_match_the_constructed_actions():
    abacus = generate_item("G5-MAT-NUM-ABACUS-01", role="unsupported_before", seed=4)
    expanded = generate_item("G5-MAT-NUM-EXPAND-01", role="unsupported_before", seed=4)

    assert "සාදන්න" in abacus.prompt_si
    assert "rods" in abacus.game_data
    assert "විහිදුවන්න" in expanded.prompt_si
    assert "rods" not in expanded.game_data


def test_extreme_number_digits_are_unique():
    for seed in range(100):
        item = generate_item(
            "G5-MAT-NUM-EXTREME-01", role="unsupported_before", seed=seed
        )
        digits = item.game_data["digits"]

        assert len(digits) == len(set(digits))


def test_third_game_pair_targets_largest_then_smallest():
    largest = generate_item(
        "G5-MAT-NUM-EXTREME-01", role="unsupported_before", seed=7
    )
    smallest = generate_item(
        "G5-MAT-NUM-LEADING-ZERO-01", role="unsupported_before", seed=7
    )

    assert largest.game_data["greatest"] is True
    assert smallest.game_data["greatest"] is False


def test_ordering_game_uses_four_distinct_four_digit_numbers():
    for seed in range(50):
        item = generate_item("G5-MAT-NUM-ORDER-01", role="unsupported_before", seed=seed)
        values = item.game_data["values"]

        assert len(values) == len(set(values)) == 4
        assert all(1_000 <= value <= 9_999 for value in values)


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_direct_manipulation_response_is_scored_from_server_item(skill):
    item = generate_item(skill.skill_id, role="unsupported_before", seed=19)
    game = item.game_data
    if skill.skill_id.endswith("POSITION-01"):
        response = {"kind": "drag_to_slot", "selected_place": game["place"]}
    elif skill.skill_id.endswith("REPRESENTED-01"):
        response = {"kind": "drag_to_slot", "represented_value": game["digit"] * 10 ** game["place"]}
    elif skill.skill_id.endswith("100000-01"):
        response = {"kind": "constructed_number", "constructed_number": game["number"]}
    elif "ABACUS" in skill.skill_id:
        response = {"kind": "bead_placement", "rods": list(game["rods"])}
    elif "EXPAND" in skill.skill_id:
        response = {"kind": "expanded_form", "terms": list(expanded_terms(game["number"]))}
    elif "EXTREME" in skill.skill_id or "LEADING" in skill.skill_id:
        response = {"kind": "digit_order", "digits": list(map(int, str(construct_extreme(tuple(game["digits"]), greatest=game["greatest"]))))}
    else:
        response = {"kind": "number_order", "order": list(order_numbers(tuple(game["values"]), ascending=game["ascending"]))}
    assert validate_constructed_response(item, response)[0] is True
    assert validate_constructed_response(item, {**response, "kind": "combine_quantities"})[0] is False
    assert validate_constructed_response(item, {"kind": response["kind"]})[0] is False
    field = next(key for key in response if key != "kind")
    malformed = {**response, field: [] if isinstance(response[field], list) else True}
    assert validate_constructed_response(item, malformed)[0] is False


def test_model1_distribution_is_complete_normalized_and_abstains_when_sparse():
    belief = infer_belief("leading_zero_first")
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert isclose(sum(belief["probabilities"].values()), 1.0)
    assert belief["top_hypothesis"] == "leading_zero_first"
    sparse = infer_belief("leading_zero_first", sparse=True)
    assert sparse["abstained"] is True
    assert sparse["top_hypothesis"] == "unknown_or_other"


def test_model2_baseline_ignores_belief_and_proposed_consumes_complete_distribution():
    belief = infer_belief("ascending_descending_reversed")
    baseline = scaffold_decision(ATOMIC_SKILLS[-1].skill_id, "baseline", belief, seed=31)
    proposed = scaffold_decision(ATOMIC_SKILLS[-1].skill_id, "proposed", belief, seed=31)
    assert baseline["uses_complete_model1_distribution"] is False
    assert baseline["selected_action"] == "visual_guidance"
    assert proposed["uses_complete_model1_distribution"] is True
    assert proposed["objective"] == "predicted_raw_independence_gain"
    assert {row["scaffold_type"] for row in proposed["candidates"]} == set(SCAFFOLDS)
    assert isclose(sum(row["propensity"] for row in proposed["candidates"]), 1.0)

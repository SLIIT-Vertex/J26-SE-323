import pytest

from app.gamification.content.number_world import (
    ATOMIC_SKILLS,
    MISCONCEPTIONS,
    abacus_digits,
    generate_item,
    order_numbers,
    validate_constructed_response,
)


def test_four_skills_one_toy_each_with_the_parade_last_and_hard():
    assert [(skill.skill_id, skill.chapter) for skill in ATOMIC_SKILLS] == [
        ("G5-MAT-NUM-POSITION-01", "costume_shop"),
        ("G5-MAT-NUM-REPRESENTED-01", "costume_shop"),
        ("G5-MAT-NUM-ABACUS-01", "bead_bounce"),
        ("G5-MAT-NUM-ORDER-01", "toy_parade"),
    ]
    assert ATOMIC_SKILLS[-1].difficulty == "hard"
    for skill in ATOMIC_SKILLS:
        before = generate_item(skill.skill_id, role="unsupported_before", seed=31)
        after = generate_item(skill.skill_id, role="unsupported_after", seed=31)
        assert before.parallel_family_id == after.parallel_family_id
        assert before.skill_id == after.skill_id == skill.skill_id
        assert before.revision_id != after.revision_id


@pytest.mark.parametrize(
    "skill_id",
    (
        "G5-MAT-NUM-100000-01",
        "G5-MAT-NUM-EXPAND-01",
        "G5-MAT-NUM-EXTREME-01",
        "G5-MAT-NUM-LEADING-ZERO-01",
    ),
)
def test_dropped_skills_are_not_playable(skill_id):
    with pytest.raises(ValueError):
        generate_item(skill_id, role="unsupported_before", seed=1)


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


def test_abacus_digits_and_ordering():
    assert abacus_digits(40_205) == (0, 4, 0, 2, 0, 5)
    assert order_numbers((40_105, 40_015, 40_150), ascending=True) == (40_015, 40_105, 40_150)


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


def test_bead_toy_prompt_matches_the_rods():
    abacus = generate_item("G5-MAT-NUM-ABACUS-01", role="unsupported_before", seed=4)
    assert "සාදන්න" in abacus.prompt_si
    assert abacus.game_data["rods"] == abacus_digits(abacus.game_data["number"])


def test_parade_uses_four_distinct_four_digit_numbers():
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
        response = {
            "kind": "drag_to_slot",
            "represented_value": game["digit"] * 10 ** game["place"],
        }
    elif "ABACUS" in skill.skill_id:
        response = {"kind": "bead_placement", "rods": list(game["rods"])}
    else:
        response = {
            "kind": "number_order",
            "order": list(order_numbers(tuple(game["values"]), ascending=game["ascending"])),
        }
    assert validate_constructed_response(item, response)[0] is True
    assert (
        validate_constructed_response(item, {**response, "kind": "combine_quantities"})[0] is False
    )
    assert validate_constructed_response(item, {"kind": response["kind"]})[0] is False
    field = next(key for key in response if key != "kind")
    malformed = {**response, field: [] if isinstance(response[field], list) else True}
    assert validate_constructed_response(item, malformed)[0] is False

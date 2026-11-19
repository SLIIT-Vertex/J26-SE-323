from __future__ import annotations

import pytest

from app.gamification.content.addition_adventure import (
    ATOMIC_SKILLS,
    EQUIVALENCE_VERSION,
    MISCONCEPTIONS,
    SCAFFOLDS,
    TEXTBOOK_FACTS,
    carrying_count,
    expanded_form,
    generate_item,
    generate_simpler_item,
    validate_constructed_response,
)


def test_textbook_facts_preserve_the_photographed_examples() -> None:
    assert TEXTBOOK_FACTS == ((8, 3), (11, 5), (17, 5), (3, 6), (2, 3), (4, 3))


def test_three_skills_one_per_place_in_the_story() -> None:
    assert [(row.skill_id, row.chapter) for row in ATOMIC_SKILLS] == [
        ("G5-MAT-ADD-MENTAL-01", "crystal_flight"),
        ("G5-MAT-C06-L01-O01", "number_factory"),
        ("G5-MAT-C06-L01-O03", "sky_city"),
    ]
    assert {row.source_node_id for row in ATOMIC_SKILLS}.issuperset(
        {"G5-MAT-C06-L01-O01", "G5-MAT-C06-L01-O03"}
    )
    assert "unknown_or_other" in MISCONCEPTIONS
    assert "carry_omitted" in MISCONCEPTIONS
    assert SCAFFOLDS == (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )


def test_dropped_skills_are_not_playable() -> None:
    for skill_id in (
        "G5-MAT-C06-L01-O02",
        "G5-MAT-ADD-RUNNING-TOTAL-01",
        "G5-MAT-ADD-TABLE-TOTAL-01",
    ):
        with pytest.raises(ValueError, match="ADDITION_SKILL_NOT_FOUND"):
            generate_item(skill_id, role="unsupported_before", seed=1)


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_items_are_deterministic_fresh_and_parallel(skill) -> None:
    before = generate_item(skill.skill_id, role="unsupported_before", seed=41)
    replay = generate_item(skill.skill_id, role="unsupported_before", seed=41)
    after = generate_item(skill.skill_id, role="unsupported_after", seed=41)
    assert before == replay
    assert before.revision_id != after.revision_id
    assert before.parallel_family_id == after.parallel_family_id
    assert EQUIVALENCE_VERSION in before.parallel_family_id
    assert len(before.options) == 4
    assert before.correct_option_id in dict(before.options)
    assert before.error_codes[before.correct_option_id] == "correct"
    assert all(code == "correct" or code in MISCONCEPTIONS for code in before.error_codes.values())


@pytest.mark.parametrize("seed", range(12))
def test_factory_and_city_use_three_digit_numbers_with_matching_carries(seed: int) -> None:
    factory = generate_item("G5-MAT-C06-L01-O01", role="unsupported_before", seed=seed)
    city = generate_item("G5-MAT-C06-L01-O03", role="unsupported_before", seed=seed)
    city_after = generate_item("G5-MAT-C06-L01-O03", role="unsupported_after", seed=seed)
    assert len(factory.game_data["addends"]) == 2
    assert factory.game_data["carrying_count"] == 2
    assert len(city.game_data["addends"]) == 3
    assert city.game_data["carrying_count"] in {2, 3}
    assert city_after.game_data["carrying_count"] == city.game_data["carrying_count"]
    for item in (factory, city, city_after):
        assert all(100 <= value <= 999 for value in item.game_data["addends"])
    simpler = generate_simpler_item("G5-MAT-C06-L01-O03", seed=seed)
    assert len(simpler.game_data["addends"]) == 3
    assert simpler.game_data["carrying_count"] == 1


def test_carrying_and_expanded_arithmetic() -> None:
    assert carrying_count((382, 728, 298)) == 3
    assert carrying_count((458, 379)) == 2
    assert carrying_count((1_234, 1_111)) == 0
    assert expanded_form(4_205) == (4_000, 200, 5)


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_direct_manipulation_response_is_scored_from_server_item(skill) -> None:
    item = generate_item(skill.skill_id, role="unsupported_before", seed=13)
    game = item.game_data
    if skill.skill_id.endswith("MENTAL-01"):
        response = {"kind": "combine_quantities", "combined": True, "total": sum(game["addends"])}
    else:
        response = {
            "kind": "regroup_carry",
            "total": sum(game["addends"]),
            "carry_count": game["carrying_count"],
            "aligned": True,
        }
    assert validate_constructed_response(item, response)[0] is True
    assert validate_constructed_response(item, {**response, "kind": "drag_to_slot"})[0] is False
    assert validate_constructed_response(item, {"kind": response["kind"]})[0] is False
    assert validate_constructed_response(item, {**response, "total": True})[0] is False


def test_a_missed_carry_is_scored_as_carry_omitted() -> None:
    item = generate_item("G5-MAT-C06-L01-O03", role="unsupported_before", seed=5)
    game = item.game_data
    response = {
        "kind": "regroup_carry",
        "total": sum(game["addends"]),
        "carry_count": game["carrying_count"] - 1,
        "aligned": True,
    }
    assert validate_constructed_response(item, response)[:2] == (False, "carry_omitted")

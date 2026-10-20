from __future__ import annotations

import math

import pytest

from app.gamification.content.fraction_adventure import (
    ATOMIC_SKILLS,
    MISCONCEPTIONS,
    generate_item,
    infer_belief,
    validate_constructed_response,
)


def response_for(item):
    game = item.game_data
    kind = game["response_kind"]
    if kind == "fraction_shading":
        return {
            "kind": kind,
            "representation": game["representation"],
            "denominator": game["denominator"],
            "shaded_indices": [0],
        }
    if kind == "equal_grouping":
        return {
            "kind": kind,
            "denominator": game["denominator"],
            "assignments": [index % game["denominator"] for index in range(game["total"])],
        }
    if kind == "fraction_quantity_table":
        total = game["total"]
        return {
            "kind": kind,
            "total": total,
            "quarter_values": [total // 4, total // 2, total * 3 // 4],
        }
    target = game.get("requested_numerator", len(game["stimulus_shaded_indices"]))
    return {
        "kind": kind,
        "representation": game["representation"],
        "numerator": target,
        "denominator": 10,
        "shaded_indices": list(game.get("stimulus_shaded_indices") or range(target)),
    }


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_items_are_deterministic_parallel_solvable_and_answer_free(skill) -> None:
    before = generate_item(skill.skill_id, role="unsupported_before", seed=31)
    after = generate_item(skill.skill_id, role="unsupported_after", seed=31)
    assert before == generate_item(skill.skill_id, role="unsupported_before", seed=31)
    assert before.revision_id != after.revision_id
    assert before.parallel_family_id == after.parallel_family_id
    assert before.options == after.options == ()
    assert validate_constructed_response(before, response_for(before))[0] is True
    assert "correct_response" not in before.game_data
    assert "answer" not in before.game_data


def test_every_equivalent_shaded_region_and_balanced_grouping_is_accepted() -> None:
    half = generate_item("G5-MAT-FRC-HALF-WHOLE-01", role="unsupported_before", seed=4)
    for index in range(2):
        payload = response_for(half)
        payload["shaded_indices"] = [index]
        assert validate_constructed_response(half, payload)[0] is True
    groups = generate_item("G5-MAT-C03-L01-O01", role="unsupported_before", seed=4)
    payload = response_for(groups)
    assert validate_constructed_response(groups, payload)[0] is True
    payload["assignments"] = [1 - value for value in payload["assignments"]]
    assert validate_constructed_response(groups, payload)[0] is True


@pytest.mark.parametrize(
    "mutation",
    [
        {"extra": True},
        {"kind": "bead_placement"},
    ],
)
def test_strict_payload_rejects_unknown_fields_and_discriminators(mutation) -> None:
    item = generate_item("G5-MAT-FRC-HALF-WHOLE-01", role="unsupported_before", seed=2)
    payload = response_for(item) | mutation
    with pytest.raises(ValueError):
        validate_constructed_response(item, payload)


def test_complete_normalized_misconception_distribution() -> None:
    belief = infer_belief("unequal_group_sizes", evidence_quality=0.9)
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert math.isclose(sum(belief["probabilities"].values()), 1.0)

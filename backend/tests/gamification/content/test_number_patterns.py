from __future__ import annotations

from itertools import pairwise

import pytest

from app.gamification.content.number_patterns import (
    ATOMIC_SKILLS,
    EQUIVALENCE_VERSION,
    TEXTBOOK_FAMILIES,
    generate_item,
    validate_constructed_response,
)


def _correct(item):
    game = item.game_data
    terms = [game["sequence"][index] for index in game["missing_indices"]]
    if game["operation"] == "multiply":
        return {"kind": "constant_ratio_pattern", "multiplier": game["rule"], "completed_terms": terms}
    return {"kind": "constant_difference_pattern", "operation": game["operation"], "difference": game["rule"], "completed_terms": terms}


def test_four_bubble_rush_patterns_keep_their_textbook_rows() -> None:
    assert [(row.skill_id, row.chapter) for row in ATOMIC_SKILLS] == [
        ("G5-MAT-PAT-DIFF-ASC-01", "bubble_rush"),
        ("G5-MAT-PAT-DIFF-DESC-01", "bubble_rush"),
        ("G5-MAT-PAT-RATIO-2-01", "bubble_rush"),
        ("G5-MAT-PAT-RATIO-5-01", "bubble_rush"),
    ]
    assert (1, 3, 5, 7, 9, 11) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[0].skill_id]
    assert (12, 10, 8, 6, 4, 2) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[1].skill_id]
    assert (5, 10, 20, 40, 80) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[2].skill_id]
    assert (8, 40, 200, 1000) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[3].skill_id]


@pytest.mark.parametrize("skill_id", ("G5-MAT-PAT-RATIO-3-01", "G5-MAT-PAT-RATIO-4-01"))
def test_dropped_patterns_are_not_playable(skill_id) -> None:
    with pytest.raises(ValueError):
        generate_item(skill_id, role="unsupported_before", seed=1)


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_items_are_deterministic_fresh_parallel_and_answer_free(skill) -> None:
    before = generate_item(skill.skill_id, role="unsupported_before", seed=41)
    replay = generate_item(skill.skill_id, role="unsupported_before", seed=41)
    after = generate_item(skill.skill_id, role="unsupported_after", seed=41)
    assert before == replay
    assert before.revision_id != after.revision_id
    assert before.parallel_family_id == after.parallel_family_id
    assert EQUIVALENCE_VERSION in before.parallel_family_id
    assert before.options == ()
    assert before.game_data["missing_indices"] == after.game_data["missing_indices"]
    assert all(value >= 0 for value in before.game_data["sequence"])
    assert max(before.game_data["sequence"]) <= 1000


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_constructed_responses_are_server_authoritative_and_strict(skill) -> None:
    item = generate_item(skill.skill_id, role="unsupported_before", seed=13)
    response = _correct(item)
    assert validate_constructed_response(item, response)[0] is True
    assert validate_constructed_response(item, {**response, "kind": "drag_to_slot"})[0] is False
    assert validate_constructed_response(item, {"kind": response["kind"]})[0] is False
    wrong = dict(response)
    wrong["completed_terms"] = [999]
    assert validate_constructed_response(item, wrong)[0] is False


def test_steps_are_two_and_multipliers_two_or_five() -> None:
    for skill in ATOMIC_SKILLS:
        for seed in range(30):
            for role in ("unsupported_before", "unsupported_after"):
                game = generate_item(skill.skill_id, role=role, seed=seed).game_data
                values = game["sequence"]
                assert game["rule"] == skill.rule
                if skill.operation == "subtract":
                    assert all(left - right == 2 for left, right in pairwise(values))
                elif skill.operation == "add":
                    assert all(right - left == 2 for left, right in pairwise(values))
                else:
                    assert all(right == left * skill.rule for left, right in pairwise(values))
    assert {row.rule for row in ATOMIC_SKILLS if row.operation == "multiply"} == {2, 5}


def test_a_rule_of_the_other_kind_is_an_additive_multiplicative_confusion() -> None:
    times = generate_item("G5-MAT-PAT-RATIO-5-01", role="unsupported_before", seed=3)
    plus = generate_item("G5-MAT-PAT-DIFF-ASC-01", role="unsupported_before", seed=3)
    added = {
        "kind": "constant_difference_pattern",
        "operation": "add",
        "difference": 2,
        "completed_terms": [1, 2],
    }
    doubled = {"kind": "constant_ratio_pattern", "multiplier": 2, "completed_terms": [1, 2]}
    assert validate_constructed_response(times, added)[:2] == (
        False,
        "additive_multiplicative_confusion",
    )
    assert validate_constructed_response(plus, doubled)[:2] == (
        False,
        "additive_multiplicative_confusion",
    )


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_each_pattern_has_many_fresh_after_races(skill) -> None:
    # A learner sees each after item once, and a race can be replayed many times.
    afters = set()
    for seed in range(300):
        before = generate_item(skill.skill_id, role="unsupported_before", seed=seed)
        after = generate_item(skill.skill_id, role="unsupported_after", seed=seed)
        assert after.game_data["sequence"] != before.game_data["sequence"]
        assert len(after.game_data["sequence"]) == len(before.game_data["sequence"])
        afters.add(after.game_data["sequence"])
    assert len(afters) >= 7

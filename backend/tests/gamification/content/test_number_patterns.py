from __future__ import annotations

import math
from itertools import pairwise

import pytest

from app.gamification.content.number_patterns import (
    ATOMIC_SKILLS,
    EQUIVALENCE_VERSION,
    MISCONCEPTIONS,
    SCAFFOLDS,
    TEXTBOOK_FAMILIES,
    generate_item,
    infer_belief,
    scaffold_decision,
    validate_constructed_response,
)


def _correct(item):
    game = item.game_data
    terms = [game["sequence"][index] for index in game["missing_indices"]]
    if game["operation"] == "multiply":
        return {"kind": "constant_ratio_pattern", "multiplier": game["rule"], "completed_terms": terms}
    return {"kind": "constant_difference_pattern", "operation": game["operation"], "difference": game["rule"], "completed_terms": terms}


def test_textbook_examples_and_atomic_order_are_preserved() -> None:
    assert [row.skill_id for row in ATOMIC_SKILLS] == [
        "G5-MAT-PAT-DIFF-ASC-01", "G5-MAT-PAT-DIFF-DESC-01",
        "G5-MAT-PAT-RATIO-2-01", "G5-MAT-PAT-RATIO-3-01",
        "G5-MAT-PAT-RATIO-4-01", "G5-MAT-PAT-RATIO-5-01",
    ]
    assert (1, 3, 5, 7, 9, 11) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[0].skill_id]
    assert (25, 21, 17, 13, 9) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[1].skill_id]
    assert (1, 3, 9, 27, 81) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[3].skill_id]
    assert (8, 40, 200, 1000) in TEXTBOOK_FAMILIES[ATOMIC_SKILLS[5].skill_id]


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


def test_decreasing_and_multiplier_limits_match_the_photographs() -> None:
    for seed in range(30):
        descending = generate_item("G5-MAT-PAT-DIFF-DESC-01", role="unsupported_before", seed=seed)
        values = descending.game_data["sequence"]
        assert all(left > right >= 0 for left, right in pairwise(values))
        assert descending.game_data["rule"] in {2, 4}
    assert {row.rule for row in ATOMIC_SKILLS if row.operation == "multiply"} == {2, 3, 4, 5}


def test_models_record_complete_catalogues_and_isolate_baseline() -> None:
    belief = infer_belief("wrong_multiplier", evidence_quality=0.9)
    assert math.isclose(sum(belief["probabilities"].values()), 1.0)
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert belief["top_hypothesis"] == "wrong_multiplier"
    baseline = scaffold_decision(ATOMIC_SKILLS[2].skill_id, "baseline", belief, seed=2)
    proposed = scaffold_decision(ATOMIC_SKILLS[2].skill_id, "proposed", belief, seed=2)
    assert baseline["uses_complete_model1_distribution"] is False
    assert proposed["uses_complete_model1_distribution"] is True
    assert {row["scaffold_type"] for row in proposed["candidates"]} == set(SCAFFOLDS)
    assert proposed["reward_source"] == "valid_post_withdrawal_raw_ig_only"

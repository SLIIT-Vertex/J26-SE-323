from __future__ import annotations

import math

import pytest

from app.gamification.content.subtraction_adventure import (
    ATOMIC_SKILLS,
    EQUIVALENCE_VERSION,
    MISCONCEPTIONS,
    SCAFFOLDS,
    TEXTBOOK_PAIRS,
    analyze_subtraction,
    apply_interaction_evidence,
    generate_item,
    infer_belief,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)


def _column(item, *, digits=None, exchanges=None):
    game = item.game_data
    return {
        "kind": "column_subtraction",
        "result_digits": list(game["result_digits"] if digits is None else digits),
        "exchanges": [dict(row) for row in (game["exchanges"] if exchanges is None else exchanges)],
    }


def _expanded(item, **overrides):
    game = item.game_data
    payload = {
        "kind": "expanded_subtraction",
        "minuend_terms": list(game["minuend_terms"]),
        "subtrahend_terms": list(game["subtrahend_terms"]),
        "adjusted_minuend_terms": list(game["adjusted_terms"]),
        "result_terms": list(game["result_terms"]),
        "result": game["result"],
    }
    payload.update(overrides)
    return payload


def _story(item, **overrides):
    game = item.game_data
    payload = {
        "kind": "difference_story",
        "relationship": game["relationship"],
        "minuend_source": game["minuend_source"],
        "subtrahend_source": game["subtrahend_source"],
        "result_digits": list(game["result_digits"]),
        "result": game["result"],
    }
    payload.update(overrides)
    return payload


def test_textbook_place_value_examples_are_preserved_and_distinguished() -> None:
    regrouped = analyze_subtraction(685, 339)
    assert regrouped["result"] == 346
    assert regrouped["exchanges"] == ({"from_place": "tens", "to_place": "ones"},)
    assert regrouped["adjusted_terms"] == (600, 70, 15)
    assert regrouped["result_terms"] == (300, 40, 6)
    expanded = analyze_subtraction(7828, 2506)
    assert expanded["result"] == 5322
    assert expanded["regroup_count"] == 0
    assert expanded["minuend_terms"] == (7000, 800, 20, 8)
    assert expanded["subtrahend_terms"] == (2000, 500, 0, 6)
    assert expanded["result_terms"] == (5000, 300, 20, 2)
    assert analyze_subtraction(4497, 2359)["result"] == 2138
    assert analyze_subtraction(720, 512)["result"] == 208
    assert analyze_subtraction(425, 319)["result"] == 106
    across = analyze_subtraction(1000, 1)
    assert across["borrow_across_zero"] is True
    assert [row.skill_id for row in ATOMIC_SKILLS] == [
        "G5-MAT-SUB-NO-REGROUP-01",
        "G5-MAT-SUB-EXPANDED-01",
        "G5-MAT-C07-L01-O01",
        "G5-MAT-C07-L01-O02",
        "G5-MAT-SUB-DIFF-BETWEEN-01",
        "G5-MAT-SUB-HOW-MANY-MORE-01",
    ]
    assert ATOMIC_SKILLS[3].source_status == "draft_medium_confidence_repository_not_photograph"
    steps = worked_steps({"minuend": 685, "subtrahend": 339, "response_kind": "column_subtraction"}, "worked_parallel_example")
    assert "15 − 9 = 6." in steps
    assert "6 − 3 = 3." in steps
    visual = worked_steps({"minuend": 685, "subtrahend": 339}, "visual_guidance")
    assert all("346" not in step and "15 − 9" not in step for step in visual)


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_items_are_deterministic_equivalent_and_answer_free(skill) -> None:
    before = generate_item(skill.skill_id, role="unsupported_before", seed=11)
    replay = generate_item(skill.skill_id, role="unsupported_before", seed=11)
    after = generate_item(skill.skill_id, role="unsupported_after", seed=11)
    assert before == replay
    assert before.parallel_family_id == after.parallel_family_id
    assert EQUIVALENCE_VERSION in before.parallel_family_id
    assert before.revision_id != after.revision_id
    assert before.options == ()
    for item in (before, after):
        game = item.game_data
        assert game["minuend"] >= game["subtrahend"] >= 0
        assert game["borrow_across_zero"] is False
        assert (game["minuend"], game["subtrahend"]) not in TEXTBOOK_PAIRS
        assert game["result"] == game["minuend"] - game["subtrahend"]
        assert len(game["result_digits"]) == game["width"]
        if 0 in game["subtrahend_terms"]:
            assert game["subtrahend_terms"].count(0) >= 1
            assert len(game["subtrahend_terms"]) == game["width"]
    assert before.game_data["regroup_positions"] == after.game_data["regroup_positions"]
    assert before.game_data["zero_mask"] == after.game_data["zero_mask"]
    assert before.game_data["width"] == after.game_data["width"]
    assert (before.game_data["minuend"], before.game_data["subtrahend"]) != (
        after.game_data["minuend"],
        after.game_data["subtrahend"],
    )
    if skill.relationship:
        assert before.game_data["relationship"] == after.game_data["relationship"] == skill.relationship
        assert before.game_data["context_id"] != after.game_data["context_id"]


def test_regroup_counts_and_zero_borrowing_are_exact() -> None:
    for seed in range(25):
        plain = generate_item("G5-MAT-SUB-NO-REGROUP-01", role="unsupported_before", seed=seed)
        expanded = generate_item("G5-MAT-SUB-EXPANDED-01", role="unsupported_before", seed=seed)
        one = generate_item("G5-MAT-C07-L01-O01", role="unsupported_before", seed=seed)
        two = generate_item("G5-MAT-C07-L01-O02", role="unsupported_before", seed=seed)
        assert plain.game_data["regroup_count"] == expanded.game_data["regroup_count"] == 0
        assert one.game_data["regroup_count"] == 1
        assert two.game_data["regroup_count"] == 2
        for item in (plain, expanded, one, two):
            analysed = analyze_subtraction(item.game_data["minuend"], item.game_data["subtrahend"])
            assert analysed["borrow_across_zero"] is False
            assert analysed["regroup_count"] == item.game_data["regroup_count"]
            assert analysed["exchanges"] == tuple(item.game_data["exchanges"])


def test_constructed_payloads_reject_malformed_evidence() -> None:
    column = generate_item("G5-MAT-C07-L01-O01", role="unsupported_before", seed=4)
    expanded = generate_item("G5-MAT-SUB-EXPANDED-01", role="unsupported_before", seed=4)
    story = generate_item("G5-MAT-SUB-DIFF-BETWEEN-01", role="unsupported_before", seed=4)
    assert validate_constructed_response(column, _column(column))[0] is True
    assert validate_constructed_response(expanded, _expanded(expanded))[0] is True
    assert validate_constructed_response(story, _story(story))[0] is True
    wrong_kind = _column(column)
    wrong_kind["kind"] = "regroup_carry"
    assert validate_constructed_response(column, wrong_kind)[1] == "unknown_or_other"
    extra = _column(column)
    extra["total"] = 1
    assert validate_constructed_response(column, extra)[1] == "unknown_or_other"
    missing = {"kind": "column_subtraction", "result_digits": [1]}
    assert validate_constructed_response(column, missing)[1] == "unknown_or_other"
    boolean_digit = _column(column, digits=[True, False, True, False][: column.game_data["width"]])
    assert validate_constructed_response(column, boolean_digit)[1] == "unknown_or_other"
    out_of_range = _column(column, digits=[12] * column.game_data["width"])
    assert validate_constructed_response(column, out_of_range)[1] == "unknown_or_other"
    reversed_exchange = _column(
        column,
        exchanges=[{"from_place": "ones", "to_place": "tens"}],
    )
    assert validate_constructed_response(column, reversed_exchange)[1] == "unknown_or_other"
    no_exchange = generate_item("G5-MAT-SUB-NO-REGROUP-01", role="unsupported_before", seed=2)
    unnecessary = _column(no_exchange, exchanges=[{"from_place": "tens", "to_place": "ones"}])
    assert validate_constructed_response(no_exchange, unnecessary)[1] == "unnecessary_exchange"
    two = generate_item("G5-MAT-C07-L01-O02", role="unsupported_before", seed=2)
    only_one = _column(two, exchanges=list(two.game_data["exchanges"][:1]))
    assert validate_constructed_response(two, only_one)[1] == "only_one_of_two_exchanges"
    reversed_digits = _column(column, digits=list(reversed(column.game_data["result_digits"])))
    if reversed_digits["result_digits"] != list(column.game_data["result_digits"]):
        assert validate_constructed_response(column, reversed_digits)[1] == "digits_wrong_order"
    swapped = _story(story, minuend_source=story.game_data["subtrahend_source"], subtrahend_source=story.game_data["minuend_source"])
    assert validate_constructed_response(story, swapped)[1] == "smaller_quantity_as_minuend"
    total = _story(story, result=story.game_data["first_value"] + story.game_data["second_value"])
    assert validate_constructed_response(story, total)[1] == "calculates_total_for_difference"
    short = _expanded(expanded, subtrahend_terms=list(expanded.game_data["subtrahend_terms"])[:-1])
    assert validate_constructed_response(expanded, short)[0] is False


def test_public_belief_catalogue_and_support_defaults() -> None:
    belief = infer_belief("fails_to_exchange", evidence_quality=0.9)
    assert math.isclose(sum(belief["probabilities"].values()), 1)
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert belief["top_hypothesis"] == "fails_to_exchange"
    refined = apply_interaction_evidence("unknown_or_other", {"started_from_ones": False})
    assert refined == "starts_from_left"
    assert apply_interaction_evidence("fails_to_exchange", {"started_from_ones": False}) == "fails_to_exchange"
    for skill in ATOMIC_SKILLS:
        decision = scaffold_decision(skill.skill_id, "baseline", belief, seed=3)
        proposed = scaffold_decision(skill.skill_id, "proposed", belief, seed=3)
        assert decision["uses_complete_model1_distribution"] is False
        assert proposed["uses_complete_model1_distribution"] is True
        assert {row["scaffold_type"] for row in proposed["candidates"]} == set(SCAFFOLDS)
        if skill.skill_id in {"G5-MAT-C07-L01-O01", "G5-MAT-C07-L01-O02"}:
            assert decision["selected_action"] == "worked_parallel_example"
        else:
            assert decision["selected_action"] == "visual_guidance"

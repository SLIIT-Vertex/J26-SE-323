from __future__ import annotations

import math

import pytest

from app.gamification.content.addition_adventure import (
    ATOMIC_SKILLS,
    EQUIVALENCE_VERSION,
    MISCONCEPTIONS,
    SCAFFOLDS,
    TEXTBOOK_COLUMN_EXAMPLES,
    TEXTBOOK_CONTEXT_EXAMPLES,
    TEXTBOOK_FACTS,
    TEXTBOOK_SCHOOL_TABLE,
    TEXTBOOK_SEEDLING_TABLE,
    TEXTBOOK_TRAIL_ADDENDS,
    TEXTBOOK_TRAIL_START,
    carrying_count,
    cumulative_totals,
    expanded_form,
    generate_item,
    infer_belief,
    scaffold_decision,
    table_total,
    validate_constructed_response,
)


def test_textbook_evidence_fixtures_preserve_the_photographed_examples() -> None:
    assert TEXTBOOK_FACTS == ((8, 3), (11, 5), (17, 5), (3, 6), (2, 3), (4, 3))
    assert TEXTBOOK_TRAIL_START == 82
    assert cumulative_totals(TEXTBOOK_TRAIL_ADDENDS, start=TEXTBOOK_TRAIL_START) == (
        109,
        121,
        141,
        398,
        970,
        2_202,
        4_032,
    )
    assert tuple(sum(values) for values in TEXTBOOK_COLUMN_EXAMPLES) == (7_620, 9_695, 9_110)
    assert tuple(sum(values) for values in TEXTBOOK_CONTEXT_EXAMPLES) == (11_549, 2_158)
    assert TEXTBOOK_SEEDLING_TABLE == (
        (382, 728, 298),
        (527, 541, 754),
        (892, 824, 997),
    )
    assert tuple(sum(row) for row in TEXTBOOK_SEEDLING_TABLE[:2]) == (1_408, 1_822)
    assert sum(row[0] for row in TEXTBOOK_SEEDLING_TABLE) == 1_801
    assert sum(row[2] for row in TEXTBOOK_SEEDLING_TABLE) == 2_049
    assert tuple(sum(row) for row in TEXTBOOK_SCHOOL_TABLE) == (873, 946, 918)
    assert sum(row[0] for row in TEXTBOOK_SCHOOL_TABLE) == 922
    assert abs(
        sum(row[1] for row in TEXTBOOK_SCHOOL_TABLE)
        - sum(row[2] for row in TEXTBOOK_SCHOOL_TABLE)
    ) == 5


def test_addition_catalogue_is_distinct_complete_and_draft_source_linked() -> None:
    assert len(ATOMIC_SKILLS) == 9
    assert len({row.skill_id for row in ATOMIC_SKILLS}) == 9
    assert {row.source_node_id for row in ATOMIC_SKILLS}.issuperset(
        {"G5-MAT-C06-L01-O01", "G5-MAT-C06-L01-O02", "G5-MAT-C06-L01-O03"}
    )
    assert "unknown_or_other" in MISCONCEPTIONS
    assert "place_shift_left" not in MISCONCEPTIONS
    assert "maximum_row_aggregation_error" in MISCONCEPTIONS
    assert SCAFFOLDS == (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )


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


def test_exact_carrying_complexities_and_addend_counts() -> None:
    exactly_two = generate_item("G5-MAT-C06-L01-O01", role="unsupported_before", seed=3)
    multi = generate_item("G5-MAT-C06-L01-O02", role="unsupported_before", seed=3)
    three = generate_item("G5-MAT-C06-L01-O03", role="unsupported_before", seed=3)
    assert exactly_two.game_data["carrying_count"] == 2
    assert multi.game_data["carrying_count"] > 2
    assert three.game_data["addend_count"] == 3
    assert three.game_data["carrying_count"] >= 2
    assert carrying_count((1_234, 1_111)) == 0


def test_expanded_cumulative_and_table_arithmetic() -> None:
    assert expanded_form(4_205) == (4_000, 200, 5)
    assert cumulative_totals((12, 18, 30)) == (12, 30, 60)
    assert cumulative_totals((27, 12, 20), start=82) == (109, 121, 141)
    table = ((10, 20), (30, 40))
    assert table_total(table, ((0, 1), (1, 1))) == 60


def test_word_problem_and_table_answer_keys_are_server_derivable() -> None:
    context = generate_item("G5-MAT-ADD-CONTEXT-01", role="unsupported_before", seed=7)
    expected = sum(context.game_data["addends"])
    assert dict(context.options)[context.correct_option_id] == str(expected)

    table = generate_item("G5-MAT-ADD-TABLE-TOTAL-01", role="unsupported_before", seed=7)
    matrix = tuple(tuple(row) for row in table.game_data["table"])
    cells = tuple(tuple(cell) for cell in table.game_data["selected_cells"])
    assert dict(table.options)[table.correct_option_id] == str(table_total(matrix, cells))


@pytest.mark.parametrize("skill", ATOMIC_SKILLS, ids=lambda row: row.skill_id)
def test_direct_manipulation_response_is_scored_from_server_item(skill) -> None:
    item = generate_item(skill.skill_id, role="unsupported_before", seed=13)
    game = item.game_data
    if skill.skill_id.endswith("MENTAL-01"):
        response = {"kind": "combine_quantities", "combined": True, "total": sum(game["addends"])}
    elif "C06" in skill.skill_id:
        response = {"kind": "regroup_carry", "total": sum(game["addends"]), "carry_count": game["carrying_count"], "aligned": True}
    elif skill.skill_id.endswith("RUNNING-TOTAL-01"):
        response = {"kind": "route_progression", "totals": list(game["cumulative_totals"])}
    elif skill.skill_id.endswith("CONTEXT-01"):
        response = {"kind": "cargo_loading", "selected_indices": list(range(len(game["addends"]))), "total": sum(game["addends"])}
    else:
        matrix = tuple(tuple(row) for row in game["table"])
        if game["target_type"] == "difference":
            left, right = game["comparison_rows"]
            total = abs(sum(matrix[left]) - sum(matrix[right]))
        elif game["target_type"] == "maximum_row":
            total = max(sum(row) for row in matrix)
        else:
            total = table_total(matrix, tuple(tuple(cell) for cell in game["selected_cells"]))
        response = {"kind": "data_cell_selection", "selected_cells": [f"r{row}c{column}" for row, column in game["selected_cells"]], "total": total}
    assert validate_constructed_response(item, response)[0] is True
    assert validate_constructed_response(item, {**response, "kind": "drag_to_slot"})[0] is False
    assert validate_constructed_response(item, {"kind": response["kind"]})[0] is False
    malformed = dict(response)
    numeric = next((key for key in ("total", "carry_count") if key in malformed), None)
    if numeric:
        malformed[numeric] = True
    else:
        list_field = next(key for key in ("totals", "selected_cells") if key in malformed)
        malformed[list_field] = [*malformed[list_field], *malformed[list_field][:1]]
    assert validate_constructed_response(item, malformed)[0] is False


def test_model1_normalizes_unknown_and_abstains_for_sparse_evidence() -> None:
    belief = infer_belief("carry_omitted", sparse=False, evidence_quality=0.9)
    assert math.isclose(sum(belief["probabilities"].values()), 1.0)
    assert set(belief["probabilities"]) == set(MISCONCEPTIONS)
    assert belief["top_hypothesis"] == "carry_omitted"
    assert not belief["abstained"]

    sparse = infer_belief("carry_omitted", sparse=True, evidence_quality=0.2)
    assert sparse["top_hypothesis"] == "unknown_or_other"
    assert sparse["abstained"]
    assert sparse["low_confidence"]


def test_model2_isolated_baseline_logs_all_candidates_and_safe_fallback() -> None:
    belief = infer_belief("carry_omitted", evidence_quality=1.0)
    baseline = scaffold_decision("G5-MAT-C06-L01-O01", "baseline", belief, seed=2)
    proposed = scaffold_decision("G5-MAT-C06-L01-O01", "proposed", belief, seed=2)
    assert baseline["uses_complete_model1_distribution"] is False
    assert proposed["uses_complete_model1_distribution"] is True
    assert len(proposed["candidates"]) == 3
    assert math.isclose(sum(row["propensity"] for row in proposed["candidates"]), 1.0)
    assert {row["scaffold_type"] for row in proposed["candidates"]} == set(SCAFFOLDS)
    assert proposed["objective"] == "predicted_raw_independence_gain"
    assert proposed["reward_source"] == "valid_post_withdrawal_raw_ig_only"

    sparse = infer_belief("unknown_or_other", sparse=True, evidence_quality=0.0)
    fallback = scaffold_decision("G5-MAT-C06-L01-O01", "proposed", sparse, seed=2)
    assert fallback["mode"] == "proposed_shadow_conservative_fallback"
    assert fallback["selected_action"] == "visual_guidance"

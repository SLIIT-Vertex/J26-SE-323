"""Draft, source-linked Addition Adventure content for Grade 5 Sinhala mathematics.

Only the three carrying outcomes are direct curriculum outcomes.  The remaining targets are
provisional activity mappings retained for educator review.  This module is deterministic and
contains no HTTP, persistence, learner identity, or client-trusted scoring code.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-02"
UNIVERSAL_SKILL_ID = "MAT-OPS"
PACKAGE_VERSION = "g5-mat-addition-adventure-draft-v1"
CATALOGUE_VERSION = "g5-mat-addition-misconceptions-v1"
FEATURE_VERSION = "g5-mat-addition-features-v1"
MAPPING_VERSION = "g5-mat-addition-mapping-v1"
MODEL_VERSION = "g5-mat-addition-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-addition-raw-ig-shadow-v1"
SCORING_VERSION = "g5-mat-addition-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-addition-parallel-v1"
SCAFFOLD_VERSION = "g5-mat-addition-scaffolds-v1"

# Source-page examples are kept as auditable content fixtures. Runtime items use
# deterministic parallel variants so the unsupported-after probe is fresh.
TEXTBOOK_FACTS = ((8, 3), (11, 5), (17, 5), (3, 6), (2, 3), (4, 3))
TEXTBOOK_TRAIL_START = 82
TEXTBOOK_TRAIL_ADDENDS = (27, 12, 20, 257, 572, 1_232, 1_830)
TEXTBOOK_COLUMN_EXAMPLES = ((4_597, 3_023), (6_237, 3_458), (5_321, 3_789))
TEXTBOOK_CONTEXT_EXAMPLES = ((2_521, 3_218, 5_810), (720, 725, 713))
TEXTBOOK_SEEDLING_TABLE = (
    (382, 728, 298),
    (527, 541, 754),
    (892, 824, 997),
)
TEXTBOOK_SCHOOL_TABLE = (
    (281, 288, 304),
    (344, 306, 296),
    (297, 311, 310),
)

Chapter = Literal[
    "fruit_catch",
    "tuk_tuk_journey",
    "carrying_crane",
    "market_delivery_planner",
    "festival_data_detective",
]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    source_node_id: str
    source_page: str
    outcome_provenance: str


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-MAT-ADD-MENTAL-01",
        "fruit_catch",
        "මානසික එකතු කිරීම හා කොටස් කිරීම",
        "G5-MAT-U103-A001",
        "8",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-C06-L01-O01",
        "carrying_crane",
        "ගෙනයාම අවස්ථා දෙකක් සහිත සංඛ්‍යා දෙකක් එකතු කිරීම",
        "G5-MAT-C06-L01-O01",
        "12",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-C06-L01-O02",
        "carrying_crane",
        "ගෙනයාම අවස්ථා දෙකකට වැඩි සංඛ්‍යා දෙකක් එකතු කිරීම",
        "G5-MAT-C06-L01-O02",
        "12",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-C06-L01-O03",
        "carrying_crane",
        "ගෙනයාම සහිත සංඛ්‍යා තුනක් එකතු කිරීම",
        "G5-MAT-C06-L01-O03",
        "12",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-ADD-RUNNING-TOTAL-01",
        "tuk_tuk_journey",
        "පියවරෙන් පියවර සමුච්චිත එකතුව තබා ගැනීම",
        "G5-MAT-U103-A004",
        "11",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-ADD-CONTEXT-01",
        "market_delivery_planner",
        "එකතු කිරීමේ වාක්‍ය ගැටලු විසඳීම",
        "G5-MAT-U103-A006",
        "13",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-ADD-TABLE-TOTAL-01",
        "festival_data_detective",
        "වගුවක අදාළ අගයන් තෝරා එකතුව සෙවීම",
        "G5-MAT-U103-A002",
        "9",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-ADD-TABLE-DIFFERENCE-01",
        "festival_data_detective",
        "වගු එකතු දෙකක් සසඳා වෙනස සෙවීම",
        "G5-MAT-U103-A002",
        "9",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-ADD-TABLE-MAX-01",
        "festival_data_detective",
        "වගුවක පේළි එකතු සසඳා විශාලතම එකතුව හඳුනා ගැනීම",
        "G5-MAT-U103-A002",
        "65",
        "draft_activity_mapping_requires_educator_review",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

MISCONCEPTIONS = (
    "fact_recall_or_decomposition_error",
    "place_alignment_error",
    "carry_omitted",
    "carry_added_to_wrong_column",
    "carry_not_included_in_next_column",
    "column_total_digit_reversal",
    "partial_sums_concatenated",
    "third_addend_omitted",
    "running_total_reset",
    "wrong_table_cells_selected",
    "operation_selection_error",
    "maximum_row_aggregation_error",
    "unknown_or_other",
)

SCAFFOLDS: tuple[ScaffoldType, ...] = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)

SCAFFOLD_CATALOGUE = {
    scaffold: {
        "supported_atomic_skills": tuple(SKILLS),
        "accessibility": {
            "semantic_equivalent": True,
            "colour_independent": True,
            "keyboard_operable": True,
            "reduced_motion": True,
        },
        "estimated_interaction_budget": 6 if scaffold == "step_by_step_guidance" else 4,
        "eligibility_constraints": ["grade5", "sinhala", "development_or_test", "draft_opt_in"],
        "answer_leakage_rule": "parallel_example_only_active_probe_hidden",
        "withdrawal_behavior": "remove_values_highlights_carries_announcements_and_handlers",
        "version": SCAFFOLD_VERSION,
        "review_status": "unreviewed_blocked",
    }
    for scaffold in SCAFFOLDS
}


@dataclass(frozen=True, slots=True)
class AdditionItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: Literal["unsupported_before", "unsupported_after"]
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def carrying_count(addends: tuple[int, ...]) -> int:
    """Count concrete exchanges from one decimal column into the next."""

    if len(addends) not in {2, 3} or any(value < 0 or value > 9_999 for value in addends):
        raise ValueError("INVALID_ADDENDS")
    carries = 0
    carry = 0
    width = max(1, max(len(str(value)) for value in addends))
    for place in range(width):
        column = carry + sum((value // (10**place)) % 10 for value in addends)
        carry = column // 10
        if carry:
            carries += 1
    return carries


def expanded_form(value: int) -> tuple[int, ...]:
    if value < 0 or value > 99_999:
        raise ValueError("NUMBER_OUT_OF_RANGE")
    return tuple(
        digit * (10**place)
        for place, digit in enumerate(reversed(tuple(int(part) for part in str(value))))
        if digit
    )[::-1]


def cumulative_totals(values: tuple[int, ...], *, start: int = 0) -> tuple[int, ...]:
    if not 2 <= len(values) <= 7 or any(value < 0 or value > 9_999 for value in values):
        raise ValueError("INVALID_CUMULATIVE_VALUES")
    if start < 0 or start > 99_999:
        raise ValueError("INVALID_CUMULATIVE_START")
    running = start
    result = []
    for value in values:
        running += value
        result.append(running)
    return tuple(result)


def table_total(table: tuple[tuple[int, ...], ...], cells: tuple[tuple[int, int], ...]) -> int:
    if not table or not cells:
        raise ValueError("EMPTY_TABLE_SELECTION")
    width = len(table[0])
    if width == 0 or any(len(row) != width for row in table):
        raise ValueError("INVALID_TABLE")
    try:
        return sum(table[row][column] for row, column in cells)
    except IndexError as error:
        raise ValueError("INVALID_TABLE_CELL") from error


def _cell_ids(cells: tuple[tuple[int, int], ...]) -> tuple[str, ...]:
    return tuple(f"r{row}c{column}" for row, column in cells)


def validate_constructed_response(
    item: AdditionItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    """Validate direct manipulation evidence with server-owned arithmetic."""

    game = item.game_data if isinstance(item, AdditionItem) else item.get("game_data")
    skill_id = item.skill_id if isinstance(item, AdditionItem) else item.get("skill_id")
    if not isinstance(game, Mapping) or not isinstance(skill_id, str):
        raise TypeError("INVALID_ITEM")
    kind = response.get("kind")
    normalized: dict[str, object] = {"kind": str(kind)}

    if skill_id == "G5-MAT-ADD-MENTAL-01":
        total = response.get("total")
        combined = response.get("combined") is True
        correct = type(total) is int and combined and total == sum(game["addends"])
        normalized.update(total=total, combined=combined)
        error = "fact_recall_or_decomposition_error"
        expected_kind = "combine_quantities"
    elif skill_id in {"G5-MAT-C06-L01-O01", "G5-MAT-C06-L01-O02", "G5-MAT-C06-L01-O03"}:
        total = response.get("total")
        carries = response.get("carry_count")
        aligned = response.get("aligned") is True
        correct = (
            type(total) is int
            and type(carries) is int
            and aligned
            and total == sum(game["addends"])
            and carries == game["carrying_count"]
        )
        normalized.update(total=total, carry_count=carries, aligned=aligned)
        if not aligned:
            error = "place_alignment_error"
        elif carries != game["carrying_count"]:
            error = "carry_omitted"
        else:
            error = "carry_not_included_in_next_column"
        expected_kind = "regroup_carry"
    elif skill_id == "G5-MAT-ADD-RUNNING-TOTAL-01":
        totals = response.get("totals")
        expected = list(
            cumulative_totals(
                tuple(int(value) for value in game["stops"]),
                start=int(game.get("start", 0)),
            )
        )
        valid = isinstance(totals, list) and all(type(value) is int for value in totals)
        correct = valid and totals == expected
        normalized["totals"] = totals if valid else []
        error = "running_total_reset"
        expected_kind = "route_progression"
    elif skill_id == "G5-MAT-ADD-CONTEXT-01":
        total = response.get("total")
        selected = response.get("selected_indices")
        expected_indices = list(range(len(game["addends"])))
        valid_selection = (
            isinstance(selected, list)
            and all(type(value) is int for value in selected)
            and sorted(selected) == expected_indices
        )
        correct = type(total) is int and valid_selection and total == sum(game["addends"])
        normalized.update(total=total, selected_indices=selected if valid_selection else [])
        error = "third_addend_omitted" if not valid_selection else "carry_omitted"
        expected_kind = "cargo_loading"
    else:
        selected = response.get("selected_cells")
        total = response.get("total")
        expected_cells = _cell_ids(tuple(tuple(cell) for cell in game["selected_cells"]))
        valid_selection = (
            isinstance(selected, list)
            and all(isinstance(value, str) and len(value) <= 8 for value in selected)
            and sorted(selected) == sorted(expected_cells)
        )
        table = tuple(tuple(int(value) for value in row) for row in game["table"])
        if game["target_type"] == "difference":
            left, right = tuple(int(value) for value in game["comparison_rows"])
            expected_total = abs(sum(table[left]) - sum(table[right]))
        elif game["target_type"] == "maximum_row":
            expected_total = max(sum(row) for row in table)
        else:
            expected_total = table_total(table, tuple(tuple(cell) for cell in game["selected_cells"]))
        correct = type(total) is int and valid_selection and total == expected_total
        normalized.update(total=total, selected_cells=selected if isinstance(selected, list) else [])
        if not valid_selection and game["target_type"] == "maximum_row":
            error = "maximum_row_aggregation_error"
        else:
            error = "wrong_table_cells_selected" if not valid_selection else "operation_selection_error"
        expected_kind = "data_cell_selection"

    if kind != expected_kind:
        return False, "unknown_or_other", normalized
    return bool(correct), "correct" if correct else error, normalized


def _seed(skill_id: str, role: str, seed: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")


def _family_seed(skill_id: str, seed: int) -> random.Random:
    value = int.from_bytes(hashlib.sha256(f"{skill_id}:family:{seed}".encode()).digest()[:8], "big")
    return random.Random(value)


def _addends_with_carries(
    rng: random.Random, *, count: int, minimum_carries: int, maximum_carries: int
) -> tuple[int, ...]:
    for _ in range(20_000):
        values = tuple(rng.randint(1_000, 4_999 if count == 3 else 8_999) for _ in range(count))
        carries = carrying_count(values)
        if minimum_carries <= carries <= maximum_carries:
            return values
    raise RuntimeError("ADDITION_ITEM_GENERATION_EXHAUSTED")


def _options(
    rng: random.Random, answer: int, distractors: list[tuple[int, str]]
) -> tuple[tuple[tuple[str, str], ...], str, dict[str, str]]:
    unique: list[tuple[int, str]] = [(answer, "correct")]
    for value, code in distractors:
        if value >= 0 and value not in {row[0] for row in unique}:
            unique.append((value, code))
    while len(unique) < 4:
        value = max(0, answer + rng.choice((-200, -20, -2, 2, 20, 200)))
        if value not in {row[0] for row in unique}:
            unique.append((value, "unknown_or_other"))
    rng.shuffle(unique)
    rendered = tuple((f"option-{index + 1}", str(value)) for index, (value, _) in enumerate(unique))
    codes = {option_id: unique[index][1] for index, (option_id, _) in enumerate(rendered)}
    correct = next(option_id for option_id, value in rendered if value == str(answer))
    return rendered, correct, codes


def generate_item(skill_id: str, *, role: str, seed: int) -> AdditionItem:
    if skill_id not in SKILLS:
        raise ValueError("ADDITION_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    rng = random.Random(_seed(skill_id, role, seed))
    family_rng = _family_seed(skill_id, seed)
    skill = SKILLS[skill_id]
    suffix = "B" if role == "unsupported_before" else "A"
    game: dict[str, object] = {"chapter": skill.chapter}

    if skill_id == "G5-MAT-ADD-MENTAL-01":
        first, second = TEXTBOOK_FACTS[rng.randrange(len(TEXTBOOK_FACTS))]
        bridge = min(second, 10 - (first % 10) if first % 10 else min(5, second))
        addends = (first, second)
        answer = sum(addends)
        prompt = f"{first} + {second} මානසිකව එකතු කරන්න."
        distractors = [
            (answer - bridge, "fact_recall_or_decomposition_error"),
            (int(f"{first % 10}{second % 10}"), "partial_sums_concatenated"),
            (answer + 10, "carry_not_included_in_next_column"),
        ]
        game.update(addends=addends, make_ten=bridge, decomposition=(bridge, second - bridge))
        signature = "mental-make-ten"
    elif skill_id in {"G5-MAT-C06-L01-O01", "G5-MAT-C06-L01-O02", "G5-MAT-C06-L01-O03"}:
        if skill_id.endswith("O01"):
            addend_count, low, high, signature = 2, 2, 2, "two-addends-two-carries"
        elif skill_id.endswith("O02"):
            target_carries = family_rng.choice((3, 4))
            addend_count, low, high = 2, target_carries, target_carries
            signature = f"two-addends-{target_carries}-carries"
        else:
            target_carries = family_rng.choice((2, 3, 4))
            addend_count, low, high = 3, target_carries, target_carries
            signature = f"three-addends-{target_carries}-carries"
        source_pair = TEXTBOOK_COLUMN_EXAMPLES[0]
        if skill_id.endswith("O01") and role == "unsupported_before" and seed % 3 == 0:
            addends = source_pair
        else:
            addends = _addends_with_carries(
                rng, count=addend_count, minimum_carries=low, maximum_carries=high
            )
        answer = sum(addends)
        carries = carrying_count(addends)
        prompt = f"{' + '.join(map(str, addends))} නිවැරදිව එකතු කරන්න."
        distractors = [
            (answer - 10, "carry_omitted"),
            (answer + 90, "carry_added_to_wrong_column"),
            (
                sum(addends[:2]),
                "third_addend_omitted" if addend_count == 3 else "place_alignment_error",
            ),
        ]
        game.update(
            addends=addends,
            addend_count=addend_count,
            carrying_count=carries,
            columns=("දහස්", "සිය", "දහය", "එක"),
            expanded_addends=tuple(expanded_form(value) for value in addends),
            representation="column_and_expanded",
        )
    elif skill_id == "G5-MAT-ADD-RUNNING-TOTAL-01":
        variant = family_rng.randrange(4)
        role_shift = 0 if role == "unsupported_before" else 3
        start = TEXTBOOK_TRAIL_START + variant * 10 + role_shift
        values = tuple(
            value + variant + (1 if role == "unsupported_after" else 0)
            for value in TEXTBOOK_TRAIL_ADDENDS
        )
        stop_count = len(values)
        totals = cumulative_totals(values, start=start)
        answer = totals[-1]
        prompt = f"{start} සිට එකතු කිරීමේ මාර්ගයේ සියලු සමුච්චිත එකතු ගොඩනඟන්න."
        distractors = [
            (values[-1], "running_total_reset"),
            (sum(values[:-1]), "running_total_reset"),
            (answer - values[0], "partial_sums_concatenated"),
        ]
        game.update(start=start, stops=values, cumulative_totals=totals)
        signature = f"running-{stop_count}-stops"
    elif skill_id == "G5-MAT-ADD-CONTEXT-01":
        addend_count = 3
        base = TEXTBOOK_CONTEXT_EXAMPLES[family_rng.randrange(len(TEXTBOOK_CONTEXT_EXAMPLES))]
        shift = family_rng.randrange(0, 4) * 10 + (7 if role == "unsupported_after" else 0)
        values = tuple(value + shift for value in base)
        answer = sum(values)
        context = "sports_houses" if max(base) < 1_000 else "three_sources"
        prompt = f"කාණ්ඩ තුනේ {', '.join(map(str, values))} එකතු කර මුළු ගණන සොයන්න."
        distractors = [
            (sum(values[:2]), "third_addend_omitted" if addend_count == 3 else "carry_omitted"),
            (max(values) - min(values), "operation_selection_error"),
            (answer - 100, "carry_not_included_in_next_column"),
        ]
        game.update(addends=values, addend_count=addend_count, context=context)
        signature = f"context-{addend_count}-addends"
    else:
        is_seedling = skill_id.endswith("TOTAL-01")
        source_table = TEXTBOOK_SEEDLING_TABLE if is_seedling else TEXTBOOK_SCHOOL_TABLE
        shift = family_rng.randrange(0, 3) * 4 + (3 if role == "unsupported_after" else 0)
        table = tuple(
            tuple(
                value + shift + (row + column if shift else 0)
                for column, value in enumerate(values)
            )
            for row, values in enumerate(source_table)
        )
        if is_seedling:
            row_labels = ("ජනවාරි", "පෙබරවාරි", "මාර්තු")
            column_labels = ("වම්බටු", "බණ්ඩක්කා", "මිරිස්")
            table_context = "seedlings"
        else:
            # The photographed source is legible enough for a draft transcription,
            # but these names remain explicitly blocked on Sinhala human review.
            row_labels = ("රාසිංදේවී පාසල", "සංඝබෝධි පාසල", "මැද්දුම බණ්ඩාර පාසල")
            column_labels = ("2022", "2023", "2024")
            table_context = "schools"
        if skill_id.endswith("TOTAL-01"):
            target_type = family_rng.choice(("row", "column"))
            index = family_rng.randrange(3)
            cells = (
                tuple((index, column) for column in range(3))
                if target_type == "row"
                else tuple((row, index) for row in range(3))
            )
            answer = table_total(table, cells)
            label = row_labels[index] if target_type == "row" else column_labels[index]
            prompt = f"{label} සඳහා අදාළ කොටු තෝරා මුළු එකතුව සොයන්න."
            distractors = [
                (table_total(table, ((0, index), (1, index))), "wrong_table_cells_selected"),
                (max(table[row][column] for row, column in cells), "operation_selection_error"),
                (answer - table[cells[-1][0]][cells[-1][1]], "wrong_table_cells_selected"),
            ]
            signature = f"table-{target_type}-total"
            game.update(target_type=target_type, selected_cells=cells)
        elif skill_id.endswith("DIFFERENCE-01"):
            left, right = family_rng.sample(range(3), 2)
            left_cells = tuple((left, column) for column in range(3))
            right_cells = tuple((right, column) for column in range(3))
            left_total = table_total(table, left_cells)
            right_total = table_total(table, right_cells)
            answer = abs(left_total - right_total)
            prompt = f"{row_labels[left]} සහ {row_labels[right]} එකතු දෙක අතර වෙනස සොයන්න."
            distractors = [
                (left_total + right_total, "operation_selection_error"),
                (abs(table[left][0] - table[right][0]), "wrong_table_cells_selected"),
                (max(left_total, right_total), "operation_selection_error"),
            ]
            signature = "table-row-total-difference"
            game.update(
                target_type="difference",
                selected_cells=left_cells + right_cells,
                comparison_rows=(left, right),
            )
        else:
            row_totals = tuple(sum(row) for row in table)
            winning_row = max(range(len(row_totals)), key=row_totals.__getitem__)
            cells = tuple((winning_row, column) for column in range(3))
            answer = row_totals[winning_row]
            prompt = "වසර තුනේ වැඩිම මුළු ශිෂ්‍ය සංඛ්‍යාව ඇති පාසලේ පේළිය තෝරන්න."
            distractors = [
                (row_totals[(winning_row + 1) % 3], "maximum_row_aggregation_error"),
                (max(table[winning_row]), "operation_selection_error"),
                (answer - table[winning_row][-1], "wrong_table_cells_selected"),
            ]
            signature = "table-maximum-row"
            game.update(target_type="maximum_row", selected_cells=cells)
        game.update(
            table=table,
            row_labels=row_labels,
            column_labels=column_labels,
            table_context=table_context,
        )

    rendered, correct_id, codes = _options(rng, answer, distractors)
    family = f"{skill_id}:{signature}:{EQUIVALENCE_VERSION}"
    fingerprint = hashlib.sha256(
        json.dumps(game, ensure_ascii=False, sort_keys=True, default=list).encode()
    ).hexdigest()[:12]
    return AdditionItem(
        item_id=f"{skill_id}:{suffix}:{fingerprint}",
        revision_id=f"{skill_id}:{suffix}:{fingerprint}@v1",
        parallel_family_id=family,
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,  # type: ignore[arg-type]
        prompt_si=prompt,
        options=rendered,
        correct_option_id=correct_id,
        error_codes=codes,
        game_data=game,
    )


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 1.0
) -> dict[str, object]:
    if not 0 <= evidence_quality <= 1:
        raise ValueError("INVALID_EVIDENCE_QUALITY")
    probabilities = {code: 0.025 for code in MISCONCEPTIONS}
    probabilities["unknown_or_other"] = 0.20
    if sparse or evidence_quality < 0.5:
        probabilities["unknown_or_other"] = 0.78
    elif error_code in probabilities and error_code != "unknown_or_other":
        probabilities[error_code] = 0.50 + 0.12 * evidence_quality
    total = sum(probabilities.values())
    normalized = {key: value / total for key, value in probabilities.items()}
    top = max(normalized, key=normalized.__getitem__)
    entropy = -sum(value * math.log(value) for value in normalized.values() if value)
    abstained = sparse or evidence_quality < 0.5 or top == "unknown_or_other"
    return {
        "probabilities": normalized,
        "confidence": normalized[top],
        "entropy": entropy,
        "top_hypothesis": top,
        "abstained": abstained,
        "low_confidence": abstained or normalized[top] < 0.5,
        "evidence_quality": evidence_quality,
    }


def scaffold_decision(
    skill_id: str, condition: str, belief: dict[str, object], *, seed: int
) -> dict[str, object]:
    if skill_id not in SKILLS:
        raise ValueError("ADDITION_SKILL_NOT_FOUND")
    top = str(belief["top_hypothesis"])
    abstained = bool(belief["abstained"])
    affinity = {
        "visual_guidance": {
            "place_alignment_error",
            "carry_added_to_wrong_column",
            "wrong_table_cells_selected",
            "maximum_row_aggregation_error",
        },
        "worked_parallel_example": {
            "fact_recall_or_decomposition_error",
            "column_total_digit_reversal",
            "operation_selection_error",
        },
        "step_by_step_guidance": {
            "carry_omitted",
            "carry_not_included_in_next_column",
            "partial_sums_concatenated",
            "third_addend_omitted",
            "running_total_reset",
        },
    }
    candidates = []
    for index, scaffold in enumerate(SCAFFOLDS):
        predicted = 0.07 + index * 0.01 + (0.10 if top in affinity[scaffold] else 0.0)
        candidates.append(
            {
                "scaffold_type": scaffold,
                "eligible": True,
                "exclusion_reasons": [],
                "predicted_raw_ig": round(predicted, 6),
                "uncertainty": 0.20 if abstained else 0.10,
                "propensity": 1 / len(SCAFFOLDS),
                **SCAFFOLD_CATALOGUE[scaffold],
            }
        )
    if condition == "baseline":
        selected, used_model1, mode = "visual_guidance", False, "deterministic_baseline"
    elif abstained:
        selected, used_model1, mode = (
            "visual_guidance",
            True,
            "proposed_shadow_conservative_fallback",
        )
    else:
        selected = str(
            max(candidates, key=lambda row: float(row["predicted_raw_ig"]))["scaffold_type"]
        )
        used_model1, mode = True, "proposed_shadow"
    return {
        "policy_version": POLICY_VERSION,
        "skill_id": skill_id,
        "condition": condition,
        "mode": mode,
        "uses_complete_model1_distribution": used_model1,
        "objective": "predicted_raw_independence_gain",
        "reward_source": "valid_post_withdrawal_raw_ig_only",
        "seed": seed,
        "selected_action": selected,
        "candidates": candidates,
    }


def package_hash() -> str:
    payload = {
        "skills": [
            {
                "skill_id": row.skill_id,
                "chapter": row.chapter,
                "name_si": row.name_si,
                "source_node_id": row.source_node_id,
                "source_page": row.source_page,
                "outcome_provenance": row.outcome_provenance,
            }
            for row in ATOMIC_SKILLS
        ],
        "misconceptions": MISCONCEPTIONS,
        "scaffolds": SCAFFOLD_CATALOGUE,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()

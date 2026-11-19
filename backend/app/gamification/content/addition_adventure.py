"""Draft, source-linked content for Nimo's Sky Adventure, the Grade 5 Sinhala addition game.

Three skills: quick addition facts (the crystal flight), adding two three-digit numbers with two
carries (the Number Factory), and adding three three-digit numbers with carrying (the Sky City
mission). The two carrying skills are direct curriculum outcomes; quick facts is a provisional
activity mapping kept for educator review. This module is deterministic and contains no HTTP,
persistence, learner identity, or client-trusted scoring code.
"""

from __future__ import annotations

import hashlib
import json
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

# Source-page facts are kept as auditable content fixtures. Runtime items use deterministic
# parallel variants so the unsupported-after probe is fresh.
TEXTBOOK_FACTS = ((8, 3), (11, 5), (17, 5), (3, 6), (2, 3), (4, 3))
# Simpler-version facts: smaller than every textbook fact and within ten, so no bridge is needed.
SIMPLER_FACTS = ((2, 1), (1, 3), (2, 2))
Chapter = Literal["crystal_flight", "number_factory", "sky_city"]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    source_node_id: str
    source_page: str
    outcome_provenance: str


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-MAT-ADD-MENTAL-01",
        "crystal_flight",
        "මානසික එකතු කිරීම හා කොටස් කිරීම",
        "easy",
        "G5-MAT-U103-A001",
        "8",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-C06-L01-O01",
        "number_factory",
        "ගෙනයාම අවස්ථා දෙකක් සහිත සංඛ්‍යා දෙකක් එකතු කිරීම",
        "medium",
        "G5-MAT-C06-L01-O01",
        "12",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-C06-L01-O03",
        "sky_city",
        "ගෙනයාම සහිත සංඛ්‍යා තුනක් එකතු කිරීම",
        "hard",
        "G5-MAT-C06-L01-O03",
        "12",
        "draft_trace_medium_confidence",
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
    elif skill_id in {"G5-MAT-C06-L01-O01", "G5-MAT-C06-L01-O03"}:
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
    else:
        return False, "unknown_or_other", normalized

    if kind != expected_kind:
        return False, "unknown_or_other", normalized
    return bool(correct), "correct" if correct else error, normalized


def _seed(skill_id: str, role: str, seed: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")


def _family_seed(skill_id: str, seed: int) -> random.Random:
    value = int.from_bytes(hashlib.sha256(f"{skill_id}:family:{seed}".encode()).digest()[:8], "big")
    return random.Random(value)


def _addends_with_carries(
    rng: random.Random,
    *,
    count: int,
    minimum_carries: int,
    maximum_carries: int,
    digits: int,
) -> tuple[int, ...]:
    low, high = 10 ** (digits - 1), 10**digits - 1
    for _ in range(20_000):
        values = tuple(rng.randint(low, high) for _ in range(count))
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


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> AdditionItem:
    """The same skill and game with smaller facts, fewer carries, fewer stops, or smaller values."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(skill_id: str, *, role: str, seed: int, simpler: bool = False) -> AdditionItem:
    if skill_id not in SKILLS:
        raise ValueError("ADDITION_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    rng = random.Random(_seed(skill_id, role, seed))
    family_rng = _family_seed(skill_id, seed)
    skill = SKILLS[skill_id]
    suffix = ("B" if role == "unsupported_before" else "A") + ("S" if simpler else "")
    game: dict[str, object] = {"chapter": skill.chapter}

    if skill_id == "G5-MAT-ADD-MENTAL-01":
        facts = SIMPLER_FACTS if simpler else TEXTBOOK_FACTS
        first, second = facts[rng.randrange(len(facts))]
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
    else:
        # Three-digit numbers: 458 + 379 in the factory, 382 + 728 + 298 in the city.
        digits = 3
        if skill_id.endswith("O01"):
            addend_count, low, high, signature = 2, 2, 2, "two-addends-two-carries"
        else:
            # Three three-digit addends carry out of the ones, tens and hundreds at most.
            target_carries = family_rng.choice((2, 3))
            addend_count, low, high = 3, target_carries, target_carries
            signature = f"three-addends-{target_carries}-carries"
        if simpler:
            # The same column game and addend count with a single carry.
            low = high = 1
        addends = _addends_with_carries(
            rng, count=addend_count, minimum_carries=low, maximum_carries=high, digits=digits
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


def package_hash() -> str:
    payload = {
        "skills": [
            {
                "skill_id": row.skill_id,
                "chapter": row.chapter,
                "name_si": row.name_si,
                "difficulty": row.difficulty,
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

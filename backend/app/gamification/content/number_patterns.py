"""Draft, source-linked Number Patterns (Bubble Rush) content for Grade 5 Sinhala maths.

The photographed textbook pages are represented as deterministic constructed-response
families.  This module contains no persistence, learner identity, or client-trusted scoring.
All mappings remain unreviewed draft content.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-03"
UNIVERSAL_SKILL_ID = "APT-PAT"
PACKAGE_VERSION = "g5-mat-number-patterns-draft-v1"
CATALOGUE_VERSION = "g5-mat-number-patterns-misconceptions-v1"
FEATURE_VERSION = "g5-mat-number-patterns-features-v1"
MAPPING_VERSION = "g5-mat-number-patterns-mapping-v1"
MODEL_VERSION = "g5-mat-number-patterns-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-number-patterns-raw-ig-shadow-v1"
SCORING_VERSION = "g5-mat-number-patterns-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-number-patterns-parallel-v1"
SCAFFOLD_VERSION = "g5-mat-number-patterns-scaffolds-v1"

# Every pattern is a Bubble Rush mission; its help games are chosen by the help type.
Chapter = Literal["bubble_rush"]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    source_node_id: str
    source_page: str
    operation: Literal["add", "subtract", "multiply"]
    rule: int


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-MAT-PAT-DIFF-ASC-01",
        "bubble_rush",
        "දෙක බැගින් වැඩිවන රටා",
        "easy",
        "G5-MAT-C02-L01-O02",
        "66",
        "add",
        2,
    ),
    AtomicSkill(
        "G5-MAT-PAT-DIFF-DESC-01",
        "bubble_rush",
        "දෙක බැගින් අඩුවන රටා",
        "easy",
        "G5-MAT-C02-L01",
        "supplied exercise",
        "subtract",
        2,
    ),
    AtomicSkill(
        "G5-MAT-PAT-RATIO-2-01",
        "bubble_rush",
        "දෙගුණ වන සංඛ්‍යා රටා",
        "medium",
        "G5-MAT-C02-L02-O01",
        "supplied exercise",
        "multiply",
        2,
    ),
    AtomicSkill(
        "G5-MAT-PAT-RATIO-5-01",
        "bubble_rush",
        "පස්ගුණ වන සංඛ්‍යා රටා",
        "hard",
        "G5-MAT-C02-L02-O01",
        "supplied exercise",
        "multiply",
        5,
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

TEXTBOOK_FAMILIES: dict[str, tuple[tuple[int, ...], ...]] = {
    "G5-MAT-PAT-DIFF-ASC-01": (
        (1, 3, 5, 7, 9, 11),
        (2, 4, 6, 8, 10, 12),
        (13, 15, 17, 19, 21, 23),
        (32, 34, 36, 38, 40, 42),
        (148, 150, 152, 154, 156, 158),
        (333, 335, 337, 339, 341, 343),
    ),
    "G5-MAT-PAT-DIFF-DESC-01": (
        (12, 10, 8, 6, 4, 2),
        (30, 28, 26, 24, 22, 20),
        (61, 59, 57, 55, 53, 51),
        (100, 98, 96, 94, 92, 90),
    ),
    "G5-MAT-PAT-RATIO-2-01": ((5, 10, 20, 40, 80), (7, 14, 28, 56, 112), (8, 16, 32, 64, 128)),
    "G5-MAT-PAT-RATIO-5-01": ((4, 20, 100, 500), (8, 40, 200, 1000), (7, 35, 175, 875)),
}

MISCONCEPTIONS = (
    "wrong_direction",
    "difference_as_next_term",
    "difference_order_error",
    "inconsistent_rule",
    "reapplies_rule_to_first_term",
    "additive_multiplicative_confusion",
    "multiplier_treated_as_addend",
    "multiplies_once_then_adds",
    "wrong_multiplier",
    "copies_previous_term",
    "skips_position",
    "terms_out_of_order",
    "incomplete_response",
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
        "answer_leakage_rule": "exact_failed_item_only_inside_active_support",
        "withdrawal_behavior": "remove_terms_equations_highlights_announcements_and_handlers",
        "version": SCAFFOLD_VERSION,
        "review_status": "unreviewed_blocked",
    }
    for scaffold in SCAFFOLDS
}


@dataclass(frozen=True, slots=True)
class NumberPatternItem:
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


def _sequence(start: int, operation: str, rule: int, count: int) -> tuple[int, ...]:
    values = [start]
    for _ in range(count - 1):
        if operation == "add":
            values.append(values[-1] + rule)
        elif operation == "subtract":
            values.append(values[-1] - rule)
        else:
            values.append(values[-1] * rule)
    if any(value < 0 or value > 1_000 for value in values):
        raise ValueError("PATTERN_VALUE_OUT_OF_RANGE")
    return tuple(values)


def validate_constructed_response(
    item: NumberPatternItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, NumberPatternItem) else item.get("game_data")
    if not isinstance(game, Mapping):
        raise TypeError("INVALID_ITEM")
    operation = str(game["operation"])
    rule = int(game["rule"])
    sequence = [int(value) for value in game["sequence"]]  # type: ignore[union-attr]
    missing_indices = [int(value) for value in game["missing_indices"]]  # type: ignore[union-attr]
    terms = response.get("completed_terms")
    if not isinstance(terms, list) or any(type(value) is not int for value in terms):
        terms = []
    expected = [sequence[index] for index in missing_indices]
    normalized: dict[str, object] = {"kind": str(response.get("kind")), "completed_terms": terms}
    if operation in {"add", "subtract"}:
        expected_kind = "constant_difference_pattern"
        allowed_fields = {"kind", "operation", "difference", "completed_terms"}
        normalized.update(
            operation=response.get("operation"), difference=response.get("difference")
        )
        rule_valid = response.get("operation") == operation and response.get("difference") == rule
    else:
        expected_kind = "constant_ratio_pattern"
        allowed_fields = {"kind", "multiplier", "completed_terms"}
        normalized["multiplier"] = response.get("multiplier")
        rule_valid = response.get("multiplier") == rule
    if response.get("kind") != expected_kind:
        # A rule of the other kind (adding where the pattern multiplies, or the reverse).
        other_kind = response.get("kind") in {
            "constant_difference_pattern",
            "constant_ratio_pattern",
        }
        error = "additive_multiplicative_confusion" if other_kind else "unknown_or_other"
        return False, error, normalized
    if set(response) != allowed_fields:
        return False, "unknown_or_other", normalized
    if len(terms) != len(expected):
        return False, "incomplete_response", normalized
    if any(value < 0 or value > 1_000 for value in terms):
        return False, "unknown_or_other", normalized
    if not rule_valid:
        error = "wrong_direction" if operation != "multiply" else "wrong_multiplier"
        return False, error, normalized
    if terms == expected:
        return True, "correct", normalized
    if operation == "multiply" and terms and terms[0] == sequence[missing_indices[0] - 1] + rule:
        error = "multiplier_treated_as_addend"
    elif terms and all(value == sequence[missing_indices[0] - 1] for value in terms):
        error = "copies_previous_term"
    elif sorted(terms) == sorted(expected):
        error = "terms_out_of_order"
    else:
        error = "inconsistent_rule"
    return False, error, normalized


SIMPLER_TERM_COUNT = 4
FRESH_ADDITIVE_STEPS = 30


def _fresh_start(
    base: tuple[int, ...], operation: str, rule: int, rng: random.Random
) -> int:
    """A start for an after item: not the before item's, of a similar size, in range."""

    first, count = base[0], len(base)
    if operation == "multiply":
        starts = [
            start
            for start in range(max(2, first // 2), first * 2 + 1)
            if start != first and start * rule ** (count - 1) <= 1_000
        ]
    else:
        starts = [
            first + rule * step
            for step in range(1, FRESH_ADDITIVE_STEPS + 1)
            if first + rule * (step + count) <= 1_000
        ]
    return rng.choice(starts)


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> NumberPatternItem:
    """The same rule and operation as a shorter pattern of small numbers with one blank."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(
    skill_id: str, *, role: str, seed: int, simpler: bool = False
) -> NumberPatternItem:
    if skill_id not in SKILLS:
        raise ValueError("NUMBER_PATTERN_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    skill = SKILLS[skill_id]
    families = TEXTBOOK_FAMILIES[skill_id]
    family_rng = random.Random(
        int.from_bytes(hashlib.sha256(f"{skill_id}:family:{seed}".encode()).digest()[:8], "big")
    )
    family_index = family_rng.randrange(len(families))
    base = families[family_index]
    rule = skill.rule if skill.operation == "multiply" else abs(base[1] - base[0])
    # Keep before/after structurally equivalent but fresh. When only a small photographed
    # family exists, a bounded offset retains the exact rule without exposing the probe.
    if simpler:
        start = {"add": rule, "subtract": rule * SIMPLER_TERM_COUNT, "multiply": 1}[
            skill.operation
        ]
        sequence = _sequence(start, skill.operation, rule, SIMPLER_TERM_COUNT)
    elif role == "unsupported_before":
        sequence = base
    else:
        # Each after item is shown to a learner only once, so it comes from a pool of starts of a
        # similar size (same rule, same length), not from the few photographed rows alone.
        sequence = _sequence(
            _fresh_start(base, skill.operation, rule, family_rng),
            skill.operation,
            rule,
            len(base),
        )
    missing_count = 1 if simpler else 2
    missing_indices = tuple(range(len(sequence) - missing_count, len(sequence)))
    visible_terms: tuple[int | None, ...] = tuple(
        None if index in missing_indices else value for index, value in enumerate(sequence)
    )
    operation_si = {"add": "එකතු කර", "subtract": "අඩු කර", "multiply": "ගුණ කර"}[skill.operation]
    prompt = (
        "එකම රීතිය යොදා හිස් ස්ථානය සම්පූර්ණ කරන්න."
        if simpler
        else "එකම රීතිය නැවත නැවත යොදා හිස් ස්ථාන දෙක සම්පූර්ණ කරන්න."
    )
    signature = f"{skill.operation}-{rule}-terms-{len(sequence)}-missing-{missing_count}"
    fingerprint = hashlib.sha256(json.dumps(sequence).encode()).hexdigest()[:12]
    suffix = ("B" if role == "unsupported_before" else "A") + ("S" if simpler else "")
    game = {
        "chapter": skill.chapter,
        "operation": skill.operation,
        "rule": rule,
        "visible_terms": visible_terms,
        "sequence": sequence,
        "missing_indices": missing_indices,
        "term_count": len(sequence),
        "operation_label_si": operation_si,
    }
    return NumberPatternItem(
        item_id=f"{skill_id}:{suffix}:{fingerprint}",
        revision_id=f"{skill_id}:{suffix}:{fingerprint}@v1",
        parallel_family_id=f"{skill_id}:{signature}:{EQUIVALENCE_VERSION}",
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,  # type: ignore[arg-type]
        prompt_si=prompt,
        options=(),
        correct_option_id="constructed-response",
        error_codes={},
        game_data=game,
    )


def package_hash() -> str:
    payload = {
        "skills": [
            skill.__dict__
            if hasattr(skill, "__dict__")
            else {
                field: getattr(skill, field)
                for field in (
                    "skill_id",
                    "chapter",
                    "name_si",
                    "difficulty",
                    "source_node_id",
                    "source_page",
                    "operation",
                    "rule",
                )
            }
            for skill in ATOMIC_SKILLS
        ],
        "misconceptions": MISCONCEPTIONS,
        "scaffolds": SCAFFOLD_CATALOGUE,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()

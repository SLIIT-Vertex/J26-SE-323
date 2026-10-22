"""Development-only, source-linked fraction activities for G5-AREA-MAT-05."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-05"
UNIVERSAL_SKILL_ID = "MAT-FRC"
PACKAGE_VERSION = "g5-mat-fraction-adventure-draft-v1"
CATALOGUE_VERSION = "g5-mat-fraction-misconceptions-v1"
FEATURE_VERSION = "g5-mat-fraction-features-v1"
MAPPING_VERSION = "g5-mat-fraction-source-mapping-v1"
MODEL_VERSION = "g5-mat-fraction-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-fraction-raw-ig-shadow-v1"
SCORING_VERSION = "g5-mat-fraction-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-fraction-parallel-v1"
SCAFFOLD_VERSION = "g5-mat-fraction-scaffolds-v1"

Chapter = Literal["equal_share_studio", "quarter_orchard", "tenths_mosaic"]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    source_node_id: str
    source_page: int
    source_status: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-MAT-FRC-HALF-WHOLE-01",
        "equal_share_studio",
        "සම්පූර්ණයක බාගය",
        "easy",
        "G5-MAT-C03-L01",
        69,
        "provisional_unreviewed",
        "fraction_shading",
    ),
    AtomicSkill(
        "G5-MAT-C03-L01-O01",
        "equal_share_studio",
        "සමූහයක බාගය",
        "easy",
        "G5-MAT-C03-L01-O01",
        69,
        "existing_pilot_identity",
        "equal_grouping",
    ),
    AtomicSkill(
        "G5-MAT-FRC-QUARTER-WHOLE-01",
        "quarter_orchard",
        "සම්පූර්ණයක කාල",
        "easy",
        "G5-MAT-C03-L01",
        69,
        "provisional_unreviewed",
        "fraction_shading",
    ),
    AtomicSkill(
        "G5-MAT-C03-L01-O02",
        "quarter_orchard",
        "සමූහයක කාල",
        "medium",
        "G5-MAT-C03-L01-O02",
        70,
        "development_only_unreviewed",
        "equal_grouping",
    ),
    AtomicSkill(
        "G5-MAT-FRC-QUARTER-TABLE-01",
        "quarter_orchard",
        "කාල සම්බන්ධතා වගුව",
        "medium",
        "G5-MAT-C03-L01-O02",
        70,
        "provisional_unreviewed",
        "fraction_quantity_table",
    ),
    AtomicSkill(
        "G5-MAT-FRC-TENTHS-BUILD-01",
        "tenths_mosaic",
        "දහයෙන් කොටස් සෑදීම",
        "medium",
        "G5-MAT-C03-L01-O03",
        70,
        "provisional_unreviewed",
        "tenths_representation",
    ),
    AtomicSkill(
        "G5-MAT-FRC-TENTHS-READ-01",
        "tenths_mosaic",
        "දහයෙන් කොටස් කියවීම",
        "medium",
        "G5-MAT-C03-L01-O03",
        70,
        "provisional_unreviewed",
        "tenths_representation",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

MISCONCEPTIONS = (
    "parts_not_equal",
    "whole_selected_as_fraction",
    "numerator_denominator_swapped",
    "denominator_used_as_object_answer",
    "whole_count_reported_instead_of_one_group",
    "subtracts_denominator_instead_of_dividing",
    "incomplete_distribution",
    "unequal_group_sizes",
    "object_duplicated_or_omitted",
    "quarter_group_count_off_by_one",
    "two_quarters_treated_as_two_objects",
    "three_quarters_complement_only",
    "fraction_table_column_shift",
    "tenths_wrong_shaded_count",
    "tenths_denominator_not_ten",
    "selected_noncontiguous_parts_as_unequal_parts",
    "unknown_or_other",
)
SCAFFOLDS: tuple[ScaffoldType, ...] = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
SCAFFOLD_CATALOGUE = {
    kind: {
        "supported_atomic_skills": tuple(SKILLS),
        "answer_leakage_rule": "exact_failed_item_only_inside_active_support",
        "withdrawal_behavior": "remove_solved_regions_groups_table_values_announcements_and_handlers",
        "review_status": "unreviewed_blocked",
        "version": SCAFFOLD_VERSION,
    }
    for kind in SCAFFOLDS
}


@dataclass(frozen=True, slots=True)
class FractionItem:
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


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# Shading one half or one quarter of a whole is already the smallest form of those skills.
_NO_SIMPLER_FORM = frozenset({"G5-MAT-FRC-HALF-WHOLE-01", "G5-MAT-FRC-QUARTER-WHOLE-01"})


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> FractionItem | None:
    """The same fraction skill with fewer objects to share or fewer tenths to shade."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    if skill_id in _NO_SIMPLER_FORM:
        return None
    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(
    skill_id: str, *, role: str, seed: int, simpler: bool = False
) -> FractionItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("FRACTION_ITEM_REQUEST_INVALID")
    skill = SKILLS[skill_id]
    rng = _rng(skill_id, role, seed)
    representation = rng.choice(("circle", "rectangle"))
    game: dict[str, object] = {
        "response_kind": skill.response_kind,
        "source_node_id": skill.source_node_id,
        "source_page": skill.source_page,
        "mapping_basis": "photographed_textbook_pages_69_70",
        "review_status": skill.source_status,
    }
    if skill_id == "G5-MAT-FRC-HALF-WHOLE-01":
        game.update(
            representation=representation, denominator=2, requested_numerator=1, region_count=2
        )
        prompt = "සමාන කොටස් දෙකෙන් එක කොටසක් පාට කරන්න."
    elif skill_id == "G5-MAT-C03-L01-O01":
        total = rng.choice((4, 6) if simpler else tuple(range(6, 41, 2)))
        game.update(denominator=2, total=total, object_kind="apple")
        prompt = f"ඇපල් {total} සමාන කණ්ඩායම් දෙකකට බෙදන්න."
    elif skill_id == "G5-MAT-FRC-QUARTER-WHOLE-01":
        game.update(
            representation=representation, denominator=4, requested_numerator=1, region_count=4
        )
        prompt = "සමාන කොටස් හතරෙන් එක කොටසක් පාට කරන්න."
    elif skill_id == "G5-MAT-C03-L01-O02":
        total = rng.choice((4, 8) if simpler else tuple(range(8, 41, 4)))
        game.update(denominator=4, total=total, object_kind="apple")
        prompt = f"ඇපල් {total} සමාන කණ්ඩායම් හතරකට බෙදන්න."
    elif skill_id == "G5-MAT-FRC-QUARTER-TABLE-01":
        total = rng.choice((4, 8) if simpler else (8, 12, 16, 20, 24))
        game.update(
            denominator=4,
            total=total,
            columns=["whole", "one_quarter", "two_quarters", "three_quarters"],
        )
        prompt = f"{total} සඳහා කාල සම්බන්ධතා වගුව සම්පූර්ණ කරන්න."
    elif skill_id == "G5-MAT-FRC-TENTHS-BUILD-01":
        numerator = rng.randint(1, 2) if simpler else rng.randint(1, 9)
        game.update(
            representation=rng.choice(("strip", "circle")),
            denominator=10,
            requested_numerator=numerator,
            region_count=10,
            stimulus_shaded_indices=[],
        )
        prompt = f"දහයෙන් {numerator} කොටස් පාට කරන්න."
    else:
        numerator = rng.randint(1, 3) if simpler else rng.randint(1, 9)
        # The simpler version shades the first parts in a row, which are easier to count.
        indices = list(range(numerator)) if simpler else sorted(rng.sample(range(10), numerator))
        game.update(
            representation=rng.choice(("strip", "circle")),
            denominator=10,
            region_count=10,
            stimulus_shaded_indices=indices,
        )
        prompt = "පාට කළ දහයෙන් කොටස් ගණන භාගයක් ලෙස සකසන්න."
    revision = f"{skill_id}:{role}{':simpler' if simpler else ''}:{seed % 100000}@v1"
    return FractionItem(
        item_id=f"{skill_id}:{role}",
        revision_id=revision,
        parallel_family_id=f"{skill_id}:parallel-v1",
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,
        prompt_si=prompt,
        options=(),
        correct_option_id="constructed-response",
        error_codes={},
        game_data=game,
    )


def _strict_keys(response: Mapping[str, object], required: set[str]) -> None:
    if set(response) != required or len(response) > 6:
        raise ValueError("MALFORMED_FRACTION_RESPONSE")


def _indices(value: object, denominator: int) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) > denominator
        or any(type(i) is not int for i in value)
    ):
        raise ValueError("INVALID_SHADED_INDICES")
    result = list(value)
    if len(set(result)) != len(result) or any(i < 0 or i >= denominator for i in result):
        raise ValueError("INVALID_SHADED_INDICES")
    return sorted(result)


def validate_constructed_response(
    item: Mapping[str, object] | FractionItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, FractionItem) else item["game_data"]
    assert isinstance(game, Mapping)
    expected = str(game["response_kind"])
    if response.get("kind") != expected:
        raise ValueError("WRONG_RESPONSE_KIND")
    if expected == "fraction_shading":
        _strict_keys(response, {"kind", "representation", "denominator", "shaded_indices"})
        denominator = int(game["denominator"])
        shaded = _indices(response["shaded_indices"], denominator)
        if (
            response["representation"] != game["representation"]
            or response["denominator"] != denominator
        ):
            raise ValueError("INCOMPATIBLE_REPRESENTATION")
        correct = len(shaded) == int(game["requested_numerator"])
        return (
            correct,
            "correct"
            if correct
            else (
                "whole_selected_as_fraction" if len(shaded) == denominator else "parts_not_equal"
            ),
            dict(response, shaded_indices=shaded),
        )
    if expected == "equal_grouping":
        _strict_keys(response, {"kind", "denominator", "assignments"})
        denominator, total = int(game["denominator"]), int(game["total"])
        assignments = response["assignments"]
        if (
            response["denominator"] != denominator
            or not isinstance(assignments, list)
            or len(assignments) != total
            # -1 is an object the child has not placed yet: an incomplete share, not bad input.
            or any(type(v) is not int or v < -1 or v >= denominator for v in assignments)
        ):
            raise ValueError("INVALID_GROUP_ASSIGNMENTS")
        sizes = [assignments.count(group) for group in range(denominator)]
        correct = sum(sizes) == total and len(set(sizes)) == 1
        return (
            correct,
            "correct"
            if correct
            else ("incomplete_distribution" if sum(sizes) != total else "unequal_group_sizes"),
            {"kind": expected, "denominator": denominator, "assignments": list(assignments)},
        )
    if expected == "fraction_quantity_table":
        _strict_keys(response, {"kind", "total", "quarter_values"})
        values = response["quarter_values"]
        total = int(game["total"])
        if (
            response["total"] != total
            or not isinstance(values, list)
            or len(values) != 3
            or any(type(v) is not int or v < 0 or v > 40 for v in values)
        ):
            raise ValueError("INVALID_QUARTER_TABLE")
        answer = [total // 4, total // 2, total * 3 // 4]
        correct = values == answer
        return (
            correct,
            "correct" if correct else "fraction_table_column_shift",
            {"kind": expected, "total": total, "quarter_values": list(values)},
        )
    _strict_keys(response, {"kind", "representation", "numerator", "denominator", "shaded_indices"})
    shaded = _indices(response["shaded_indices"], 10)
    if response["representation"] != game["representation"] or response["denominator"] != 10:
        raise ValueError("INVALID_TENTHS_REPRESENTATION")
    target = int(game.get("requested_numerator", len(game.get("stimulus_shaded_indices", []))))
    correct = response["numerator"] == target and len(shaded) == target
    error = (
        "tenths_denominator_not_ten"
        if response["denominator"] != 10
        else "tenths_wrong_shaded_count"
    )
    return (
        correct,
        "correct" if correct else error,
        {
            "kind": expected,
            "representation": response["representation"],
            "numerator": response["numerator"],
            "denominator": 10,
            "shaded_indices": shaded,
        },
    )


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8
) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    base = 1 / len(MISCONCEPTIONS)
    probabilities = {name: base for name in MISCONCEPTIONS}
    if not sparse:
        confidence = min(0.72, max(0.2, evidence_quality * 0.72))
        remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
        probabilities = {
            name: (confidence if name == primary else remainder) for name in MISCONCEPTIONS
        }
    total = sum(probabilities.values())
    return {
        "probabilities": {k: v / total for k, v in probabilities.items()},
        "predicted_label": primary,
        "confidence": probabilities[primary],
        "fallback_used": sparse,
    }


def scaffold_decision(
    skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int
) -> dict[str, object]:
    del seed
    worked_first = skill_id in {"G5-MAT-C03-L01-O02", "G5-MAT-FRC-QUARTER-TABLE-01"}
    selected = "worked_parallel_example" if worked_first else "visual_guidance"
    return {
        "selected_action": selected,
        "condition": condition,
        "propensity": 1.0,
        "policy_version": POLICY_VERSION,
        "eligible_actions": list(SCAFFOLDS),
        "belief_label": belief.get("predicted_label"),
    }


def package_hash() -> str:
    payload = {
        "version": PACKAGE_VERSION,
        "skills": [
            skill.__dict__
            if hasattr(skill, "__dict__")
            else [skill.skill_id, skill.source_node_id, skill.source_page, skill.difficulty]
            for skill in ATOMIC_SKILLS
        ],
        "misconceptions": MISCONCEPTIONS,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    if scaffold_type == "visual_guidance":
        return ["සමාන කොටස්වල සීමා බලන්න.", "එක් එක් කොටස එකම ප්‍රමාණයද බලන්න."]
    if game["response_kind"] == "equal_grouping":
        return [
            "එක් වස්තුවක් එක් කණ්ඩායමකට දමන්න.",
            "ඊළඟ වස්තුව ඊළඟ කණ්ඩායමට දමන්න.",
            "සියලු කණ්ඩායම් සමාන වන තෙක් මාරුවෙන් මාරුවට බෙදන්න.",
        ]
    if game["response_kind"] == "fraction_quantity_table":
        return [
            "සම්පූර්ණය සමාන කොටස් හතරකට බෙදන්න.",
            "එක් කාලයක ගණන සොයන්න.",
            "එක් කාල කණ්ඩායම් දෙක සහ තුන එකතු කර වගුව සකසන්න.",
        ]
    return ["සමාන කොටස් ගණන් කරන්න.", "අවශ්‍ය කොටස් එකින් එක තෝරන්න.", "ඉහළ අංකය සහ පහළ අංකය පරීක්ෂා කරන්න."]

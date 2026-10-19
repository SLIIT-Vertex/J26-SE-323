"""Draft multiplication activities for G5-AREA-MAT-06.

Digit order for written products is left to right, highest place first.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-06"
UNIVERSAL_SKILL_ID = "MAT-OPS"
PACKAGE_VERSION = "g5-mat-multiplication-adventure-draft-v1"
CATALOGUE_VERSION = "g5-mat-multiplication-misconceptions-v1"
FEATURE_VERSION = "g5-mat-multiplication-features-v1"
MAPPING_VERSION = "g5-mat-multiplication-mapping-v1"
MODEL_VERSION = "g5-mat-multiplication-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-multiplication-raw-ig-shadow-v1"
SCORING_VERSION = "g5-mat-multiplication-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-multiplication-parallel-v1"

Chapter = Literal["table_explorer", "column_workshop", "story_mission"]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]
PLACES = ("ten_thousands", "thousands", "hundreds", "tens", "ones")
PLACE_LABELS = {
    "ten_thousands": "දස දහස්",
    "thousands": "දහස්",
    "hundreds": "සිය",
    "tens": "දහය",
    "ones": "එක",
}
MISCONCEPTIONS = (
    "uses_addition",
    "off_by_one_factor",
    "wrong_place_column",
    "omits_place_shift_for_ten",
    "extra_digit",
    "missing_digit",
    "reversed_factors",
    "counts_groups_instead_of_product",
    "incomplete",
    "unknown_or_other",
)
STORY_CONTEXTS = (
    {"context_id": "parcel_boxes", "label_si": "පාර්සල්", "asset": "/curriculum/game/G5-AREA-MAT-02/cargo-parcel.png"},
    {"context_id": "bus_seats", "label_si": "බස් රථ", "asset": "/curriculum/game/G5-AREA-MAT-07/time-journey-bus.png"},
    {"context_id": "fruit_rows", "label_si": "පේළි", "asset": "/curriculum/game/G5-AREA-MAT-02/fruit-tokens.png"},
    {"context_id": "crate_stacks", "label_si": "පෙට්ටි", "asset": "/curriculum/game/G5-AREA-MAT-01/harbour-crate.png"},
)


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    response_kind: str
    difficulty: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-MUL-TABLE-01", "table_explorer", "ගුණන වගුව 1–12", "multiplication_fact", "easy"),
    AtomicSkill("G5-MAT-MUL-BY-2-3-01", "column_workshop", "තුන් ඉලක්කම් ×2 හෝ ×3", "written_multiplication", "easy_medium"),
    AtomicSkill("G5-MAT-MUL-BY-4-6-01", "column_workshop", "තුන් ඉලක්කම් ×4 සිට ×6", "written_multiplication", "medium"),
    AtomicSkill("G5-MAT-MUL-BY-7-10-01", "column_workshop", "තුන් ඉලක්කම් ×7 සිට ×10", "written_multiplication", "medium_hard"),
    AtomicSkill("G5-MAT-MUL-STORY-01", "story_mission", "එක් පියවරක ගුණන කතාව", "multiplication_story", "hard"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class MultiplicationItem:
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


def digits_of(value: int) -> list[int]:
    return [int(char) for char in str(value)]


def places_for(width: int) -> list[str]:
    return list(PLACES[-width:])


def _fact(rng: random.Random) -> tuple[int, int]:
    return rng.randint(1, 12), rng.randint(1, 12)


def _written(rng: random.Random, skill_id: str) -> tuple[int, int]:
    multiplicand = rng.randint(100, 999)
    if skill_id == "G5-MAT-MUL-BY-2-3-01":
        multiplier = rng.choice((2, 3))
    elif skill_id == "G5-MAT-MUL-BY-4-6-01":
        multiplier = rng.choice((4, 5, 6))
    else:
        multiplier = 10 if rng.randrange(4) == 0 else rng.choice((7, 8, 9))
    return multiplicand, multiplier


def _story(rng: random.Random) -> tuple[int, int, dict[str, str]]:
    context = dict(STORY_CONTEXTS[rng.randrange(len(STORY_CONTEXTS))])
    return rng.randint(2, 12), rng.randint(2, 9), context


def generate_item(skill_id: str, *, role: str, seed: int) -> MultiplicationItem:
    skill = SKILLS[skill_id]
    rng = random.Random(f"{PACKAGE_VERSION}:{skill_id}:{role}:{seed}")
    if skill.response_kind == "multiplication_fact":
        multiplicand, multiplier = _fact(rng)
        product = multiplicand * multiplier
        game: dict[str, object] = {
            "response_kind": "multiplication_fact",
            "multiplicand": multiplicand,
            "multiplier": multiplier,
            "product": product,
            "grid_max": 12,
        }
        prompt = "වගුවේ හමුවන කොටුවේ ගුණිතය ලියන්න."
    elif skill.response_kind == "written_multiplication":
        multiplicand, multiplier = _written(rng, skill_id)
        product = multiplicand * multiplier
        width = len(str(product))
        places = places_for(width)
        game = {
            "response_kind": "written_multiplication",
            "multiplicand": multiplicand,
            "multiplier": multiplier,
            "product": product,
            "result_digits": digits_of(product),
            "places": places,
            "place_labels_si": [PLACE_LABELS[place] for place in places],
            "place_shift": multiplier == 10,
            "difficulty": skill.difficulty,
        }
        prompt = "තීරු ගැලපී ගුණ කර පිළිතුර ගොඩනඟන්න."
    else:
        group_size, group_count, context = _story(rng)
        product = group_size * group_count
        game = {
            "response_kind": "multiplication_story",
            "group_size": group_size,
            "group_count": group_count,
            "product": product,
            **context,
        }
        prompt = f"{context['label_si']} සමාන කණ්ඩායම් ලෙස ගුණ කරන්න."
    revision = hashlib.sha256(
        json.dumps({"skill": skill_id, "role": role, "seed": seed, "game": game}, sort_keys=True).encode()
    ).hexdigest()[:16]
    return MultiplicationItem(
        item_id=f"{skill_id}:{role}:{revision}",
        revision_id=revision,
        parallel_family_id=f"{skill_id}:{EQUIVALENCE_VERSION}",
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,  # type: ignore[arg-type]
        prompt_si=prompt,
        options=(),
        correct_option_id="",
        error_codes={},
        game_data=game,
    )


def _integers(values: object, expected: int) -> list[int] | None:
    if not isinstance(values, list) or len(values) != expected:
        return None
    digits: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 9:
            return None
        digits.append(value)
    return digits


def validate_constructed_response(
    item: MultiplicationItem | Mapping[str, object], payload: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, MultiplicationItem) else item.get("game_data")
    if not isinstance(game, Mapping):
        raise TypeError("INVALID_ITEM")
    kind = game["response_kind"]
    normalized = {"kind": payload.get("kind")}
    if payload.get("kind") != kind or set(payload) - _ALLOWED[str(kind)]:
        return False, "unexpected_payload", normalized
    if kind == "multiplication_fact":
        if payload.get("multiplicand") != game["multiplicand"] or payload.get("multiplier") != game["multiplier"]:
            return False, "reversed_factors", normalized
        product = payload.get("product")
        if isinstance(product, bool) or not isinstance(product, int):
            return False, "incomplete", normalized
        return product == game["product"], "ok" if product == game["product"] else "off_by_one_factor", normalized
    if kind == "written_multiplication":
        if payload.get("multiplicand") != game["multiplicand"] or payload.get("multiplier") != game["multiplier"]:
            return False, "reversed_factors", normalized
        expected = list(game["result_digits"])  # type: ignore[arg-type]
        digits = _integers(payload.get("result_digits"), len(expected))
        product = payload.get("product")
        if digits is None or isinstance(product, bool) or not isinstance(product, int):
            return False, "incomplete", normalized
        if len(digits) != len(expected):
            return False, "missing_digit" if len(digits) < len(expected) else "extra_digit", normalized
        if digits != expected:
            return False, "omits_place_shift_for_ten" if game.get("place_shift") else "wrong_place_column", normalized
        if product != game["product"]:
            return False, "uses_addition", normalized
        return True, "ok", normalized
    if payload.get("group_size") != game["group_size"] or payload.get("group_count") != game["group_count"]:
        return False, "counts_groups_instead_of_product", normalized
    product = payload.get("product")
    if isinstance(product, bool) or not isinstance(product, int):
        return False, "incomplete", normalized
    return product == game["product"], "ok" if product == game["product"] else "uses_addition", normalized


_ALLOWED = {
    "multiplication_fact": {"kind", "multiplicand", "multiplier", "product"},
    "written_multiplication": {"kind", "multiplicand", "multiplier", "result_digits", "product"},
    "multiplication_story": {"kind", "group_size", "group_count", "product"},
}


def infer_belief(error_code: str, *, sparse: bool = False) -> dict[str, object]:
    probabilities = {name: 0.03 for name in MISCONCEPTIONS}
    probabilities["unknown_or_other"] = 0.73 if sparse else 0.20
    if not sparse and error_code in probabilities and error_code != "unknown_or_other":
        probabilities[error_code] = 0.53
    total = sum(probabilities.values())
    normalized = {name: value / total for name, value in probabilities.items()}
    top = max(normalized, key=normalized.__getitem__)
    entropy = -sum(value * math.log(value) for value in normalized.values() if value)
    return {
        "probabilities": normalized,
        "confidence": normalized[top],
        "entropy": entropy,
        "top_hypothesis": top,
        "abstained": sparse or top == "unknown_or_other",
        "low_confidence": sparse or normalized[top] < 0.5,
    }


def scaffold_decision(
    skill_id: str, condition: str, belief: dict[str, object], *, seed: int
) -> dict[str, object]:
    del belief
    selected = "visual_guidance"
    return {
        "policy_version": POLICY_VERSION,
        "skill_id": skill_id,
        "condition": condition,
        "mode": "deterministic_baseline" if condition == "baseline" else "proposed_shadow",
        "uses_complete_model1_distribution": condition == "proposed",
        "objective": "predicted_raw_independence_gain",
        "reward_source": "valid_post_withdrawal_raw_ig_only",
        "seed": seed,
        "selected_action": selected,
        "candidates": [
            {"scaffold_type": scaffold, "eligible": True, "exclusion_reasons": [], "propensity": 1 / 3}
            for scaffold in ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
        ],
    }


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    if scaffold_type == "visual_guidance":
        if game["response_kind"] == "multiplication_fact":
            return ["තෝරාගත් පේළිය බලන්න.", "තෝරාගත් තීරුව බලන්න.", "හමුවන කොටුව සොයන්න."]
        if game["response_kind"] == "multiplication_story":
            return ["එක් කණ්ඩායමක් බලන්න.", "කණ්ඩායම් ගණන බලන්න.", "ගුණන වාක්‍යය සාදන්න."]
        if game.get("place_shift"):
            return ["එක තැන බලන්න.", "සෑම ඉලක්කමක්ම එක් තැනක් වමට යයි.", "හිස් එක තැන 0 වේ."]
        return ["දැන් වැඩ කරන තීරුව බලන්න.", "එක තැනේ සිට වමට යන්න."]
    if game["response_kind"] == "written_multiplication":
        multiplicand = int(game["multiplicand"])
        multiplier = int(game["multiplier"])
        steps = []
        for index, digit in enumerate(reversed(digits_of(multiplicand))):
            steps.append(f"{digit} × {multiplier} = {digit * multiplier}")
            if index == 2:
                break
        if multiplier == 10:
            steps.append("×10 නිසා සෑම ඉලක්කමක්ම එක් ස්ථානයක් වමට යයි.")
        return steps[:6]
    if game["response_kind"] == "multiplication_story":
        return [
            "එක් කණ්ඩායමක් වෙන් කර බලන්න.",
            "එම කණ්ඩායම නැවත නැවත සෑදේ.",
            f"{game['group_size']} × {game['group_count']} ලියන්න.",
        ]
    return [
        f"{game['multiplicand']} පේළිය බලන්න.",
        f"{game['multiplier']} තීරුව බලන්න.",
        "පේළිය සහ තීරුව හමුවන කොටුවේ ගුණිතය ලියන්න.",
    ]


def package_hash() -> str:
    payload = {
        "skills": [skill.skill_id for skill in ATOMIC_SKILLS],
        "package": PACKAGE_VERSION,
        "scoring": SCORING_VERSION,
        "equivalence": EQUIVALENCE_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

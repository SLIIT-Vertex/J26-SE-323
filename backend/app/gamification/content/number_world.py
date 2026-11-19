"""Draft, source-linked content and deterministic mechanics for Nimo's Wacky Toybox (Numbers).

Four skills, one per toy: ordering numbers (the Toy Parade, played first), building a number on the
six-rod bead toy (Bead Bounce), and the place and value of a digit (the Costume Shop).

This package is deliberately blocked from production.  It gives the durable learning-flow
orchestrator a skill-area-specific item bank, Model-1 catalogue, and scaffold catalogue without
reinterpreting the reviewed fractions vertical slice.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-01"
UNIVERSAL_SKILL_ID = "MAT-NUM"
PACKAGE_VERSION = "g5-mat-number-world-draft-v1"
CATALOGUE_VERSION = "g5-mat-number-world-misconceptions-v1"
FEATURE_VERSION = "g5-mat-number-world-features-v1"
MAPPING_VERSION = "g5-mat-number-world-mapping-v1"
MODEL_VERSION = "g5-mat-number-world-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-number-world-raw-ig-shadow-v1"
SCORING_VERSION = "g5-mat-number-world-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-number-world-parallel-v1"

Chapter = Literal["costume_shop", "bead_bounce", "toy_parade"]
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
        "G5-MAT-NUM-POSITION-01",
        "costume_shop",
        "ඉලක්කමේ ස්ථානය හා ස්ථානීය අගය",
        "easy",
        "G5-MAT-C01-L01-O01",
        "2",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-REPRESENTED-01",
        "costume_shop",
        "ඉලක්කමෙන් නිරූපිත අගය",
        "easy",
        "G5-MAT-C01-L01-O03",
        "2",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-ABACUS-01",
        "bead_bounce",
        "ස්ථානීය අගය වගුව හා ගණක රාමුව",
        "medium",
        "G5-MAT-C01-L01-K02",
        "xiv",
        "draft_content_point_high_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-ORDER-01",
        "toy_parade",
        "99 999 තෙක් ආරෝහණ හා අවරෝහණ පිළිවෙළ",
        "hard",
        "G5-MAT-C01-L02",
        "xiv",
        "draft_trace_high_confidence",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

MISCONCEPTIONS = (
    "place_shift_left",
    "place_shift_right",
    "digit_as_represented_value",
    "counts_places_from_wrong_direction",
    "zero_placeholder_omitted",
    "expanded_term_omitted_or_misplaced",
    "leading_zero_first",
    "ascending_descending_reversed",
    "first_visible_digit_only",
    "unknown_or_other",
)

SCAFFOLDS: tuple[ScaffoldType, ...] = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)


@dataclass(frozen=True, slots=True)
class NumberWorldItem:
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


def _seed(skill_id: str, role: str, seed: int) -> int:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def place_values(number: int) -> tuple[int, ...]:
    if number < 0 or number > 100_000:
        raise ValueError("NUMBER_OUT_OF_RANGE")
    return tuple(int(digit) * (10**index) for index, digit in enumerate(reversed(str(number))))


def abacus_digits(number: int) -> tuple[int, int, int, int, int, int]:
    if number < 0 or number > 999_999:
        raise ValueError("NUMBER_OUT_OF_RANGE")
    return tuple(int(value) for value in f"{number:06d}")  # type: ignore[return-value]


def order_numbers(values: tuple[int, ...], *, ascending: bool) -> tuple[int, ...]:
    if not 3 <= len(values) <= 5 or any(value < 0 or value > 99_999 for value in values):
        raise ValueError("INVALID_VALUES")
    return tuple(sorted(values, reverse=not ascending))


def _number_with_unique_target(
    rng: random.Random,
    lower: int,
    upper: int,
    *,
    exclude_first: bool = False,
    exclude_zero: bool = False,
) -> tuple[int, int, int]:
    """Return a number and an unambiguous target digit position."""

    while True:
        number = rng.randint(lower, upper)
        characters = str(number)
        eligible_positions = [
            index
            for index, value in enumerate(characters)
            if characters.count(value) == 1
            and (not exclude_first or index > 0)
            and (not exclude_zero or value != "0")
        ]
        if eligible_positions:
            position = rng.choice(eligible_positions)
            return number, int(characters[position]), len(characters) - position - 1


def validate_constructed_response(
    item: NumberWorldItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    """Validate a manipulation result without trusting a client score or answer key."""

    game = item.game_data if isinstance(item, NumberWorldItem) else item.get("game_data")
    skill_id = item.skill_id if isinstance(item, NumberWorldItem) else item.get("skill_id")
    if not isinstance(game, Mapping) or not isinstance(skill_id, str):
        raise TypeError("INVALID_ITEM")
    kind = response.get("kind")
    normalized: dict[str, object] = {"kind": str(kind)}

    if skill_id.endswith("POSITION-01"):
        selected_place = response.get("selected_place")
        correct = type(selected_place) is int and selected_place == game.get("place")
        normalized["selected_place"] = selected_place
        error = (
            "place_shift_left"
            if type(selected_place) is int and selected_place > int(game["place"])
            else "place_shift_right"
        )
        expected_kind = "drag_to_slot"
    elif skill_id.endswith("REPRESENTED-01"):
        represented = response.get("represented_value")
        expected = int(game["digit"]) * 10 ** int(game["place"])
        correct = type(represented) is int and represented == expected
        normalized["represented_value"] = represented
        error = (
            "digit_as_represented_value" if represented == game["digit"] else "place_shift_right"
        )
        expected_kind = "drag_to_slot"
    elif skill_id.endswith("ABACUS-01"):
        rods = response.get("rods")
        expected = tuple(
            int(value) for value in game.get("rods", abacus_digits(int(game["number"])))
        )
        valid_rods = (
            isinstance(rods, list)
            and len(rods) == 6
            and all(type(value) is int and 0 <= value <= 9 for value in rods)
        )
        correct = valid_rods and tuple(rods) == expected
        normalized["rods"] = rods if valid_rods else []
        error = "zero_placeholder_omitted" if valid_rods else "counts_places_from_wrong_direction"
        expected_kind = "bead_placement"
    else:
        order = response.get("order")
        supplied = tuple(int(value) for value in game["values"])
        valid_order = (
            isinstance(order, list)
            and len(order) == len(supplied)
            and all(type(value) is int for value in order)
            and sorted(order) == sorted(supplied)
        )
        expected = order_numbers(supplied, ascending=bool(game["ascending"]))
        correct = valid_order and tuple(order) == expected
        normalized["order"] = order if valid_order else []
        error = "ascending_descending_reversed"
        expected_kind = "number_order"

    if kind != expected_kind:
        return False, "unknown_or_other", normalized
    return bool(correct), "correct" if correct else error, normalized


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> NumberWorldItem:
    """The same skill and game with a shorter number, fewer digits, or fewer values to order."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(skill_id: str, *, role: str, seed: int, simpler: bool = False) -> NumberWorldItem:
    if skill_id not in SKILLS:
        raise ValueError("NUMBER_WORLD_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    rng = random.Random(_seed(skill_id, role, seed))
    skill = SKILLS[skill_id]
    family = f"{skill_id}:parallel-v1"
    item_suffix = ("B" if role == "unsupported_before" else "A") + ("S" if simpler else "")
    prompt = ""
    answer = ""
    distractors: list[tuple[str, str]] = []
    game_data: dict[str, object] = {"chapter": skill.chapter}

    if skill_id.endswith("POSITION-01"):
        number, digit, power = _number_with_unique_target(
            rng, *((123, 987) if simpler else (1_234, 98_765))
        )
        answer = str(10**power)
        prompt = f"{number:,} හි {digit} ඉලක්කම තිබෙන්නේ කුමන ස්ථානයේද?"
        distractors = [
            (str(10 ** max(0, power - 1)), "place_shift_right"),
            (str(10 ** (power + 1)), "place_shift_left"),
            (str(digit), "digit_as_represented_value"),
        ]
        game_data.update(number=number, digit=digit, place=power)
    elif skill_id.endswith("REPRESENTED-01"):
        number, digit, power = _number_with_unique_target(
            rng,
            *((1_234, 9_876) if simpler else (10_234, 98_765)),
            exclude_first=True,
            exclude_zero=True,
        )
        answer = str(digit * 10**power)
        prompt = f"{number:,} හි {digit} ඉලක්කමෙන් නිරූපිත අගය කීයද?"
        distractors = [
            (str(digit), "digit_as_represented_value"),
            (str(digit * 10 ** max(0, power - 1)), "place_shift_right"),
            (str(digit * 10 ** (power + 1)), "place_shift_left"),
        ]
        game_data.update(number=number, digit=digit, place=power)
    elif skill_id.endswith("ABACUS-01"):
        number = rng.choice((205, 370, 904, 610) if simpler else (40_205, 50_070, 70_304, 90_010))
        answer = str(number)
        prompt = f"{number:,} සංඛ්‍යාව දඬු හයේ ගණක රාමුවේ සාදන්න."
        distractors = [
            (str(int(str(number).replace("0", ""))), "zero_placeholder_omitted"),
            (str(number // 10), "place_shift_right"),
            (str(min(999_999, number * 10)), "place_shift_left"),
        ]
        game_data.update(number=number, rods=abacus_digits(number))
    else:
        prefix = rng.randint(1, 8) * 1000
        values = tuple(prefix + value for value in rng.sample(range(10, 990), 3 if simpler else 4))
        ascending = rng.choice((True, False))
        ordered = order_numbers(values, ascending=ascending)
        answer = ",".join(map(str, ordered))
        prompt = f"{list(values)} → {'ආරෝහණ' if ascending else 'අවරෝහණ'} පිළිවෙළ"
        distractors = [
            (",".join(map(str, reversed(ordered))), "ascending_descending_reversed"),
            (",".join(map(str, values)), "first_visible_digit_only"),
            (
                ",".join(map(str, sorted(values, key=lambda value: str(value)[0]))),
                "first_visible_digit_only",
            ),
        ]
        game_data.update(values=values, ascending=ascending)

    unique = [(answer, "correct")]
    for value, code in distractors:
        if value not in {item[0] for item in unique}:
            unique.append((value, code))
    while len(unique) < 4:
        unique.append((str(rng.randint(1, 99_999)), "unknown_or_other"))
    rng.shuffle(unique)
    options = tuple((f"option-{index + 1}", value) for index, (value, _) in enumerate(unique))
    codes = {option_id: unique[index][1] for index, (option_id, _) in enumerate(options)}
    correct_id = next(option_id for option_id, value in options if value == answer)
    fingerprint = hashlib.sha256(
        json.dumps(game_data, sort_keys=True, default=list).encode()
    ).hexdigest()[:12]
    return NumberWorldItem(
        item_id=f"{skill_id}:{item_suffix}:{fingerprint}",
        revision_id=f"{skill_id}:{item_suffix}:{fingerprint}@v1",
        parallel_family_id=family,
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,  # type: ignore[arg-type]
        prompt_si=prompt,
        options=options,
        correct_option_id=correct_id,
        error_codes=codes,
        game_data=game_data,
    )


def package_hash() -> str:
    payload = {
        "skills": [
            skill.__dict__
            if hasattr(skill, "__dict__")
            else {
                "skill_id": skill.skill_id,
                "chapter": skill.chapter,
                "name_si": skill.name_si,
                "difficulty": skill.difficulty,
                "source_node_id": skill.source_node_id,
                "source_page": skill.source_page,
                "outcome_provenance": skill.outcome_provenance,
            }
            for skill in ATOMIC_SKILLS
        ],
        "misconceptions": MISCONCEPTIONS,
        "scaffolds": SCAFFOLDS,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()

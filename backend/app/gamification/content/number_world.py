"""Draft, source-linked content and deterministic mechanics for Grade 5 Number World.

This package is deliberately blocked from production.  It gives the durable learning-flow
orchestrator a skill-area-specific item bank, Model-1 catalogue, and scaffold catalogue without
reinterpreting the reviewed fractions vertical slice.
"""

from __future__ import annotations

import hashlib
import json
import math
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

Chapter = Literal[
    "place_value_harbour",
    "firefly_abacus",
    "kite_workshop",
    "river_route_rally",
]
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
        "place_value_harbour",
        "ඉලක්කමේ ස්ථානය හා ස්ථානීය අගය",
        "easy",
        "G5-MAT-C01-L01-O01",
        "2",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-REPRESENTED-01",
        "place_value_harbour",
        "ඉලක්කමෙන් නිරූපිත අගය",
        "easy",
        "G5-MAT-C01-L01-O03",
        "2",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-100000-01",
        "place_value_harbour",
        "100 000 තෙක් සංඛ්‍යා",
        "easy",
        "G5-MAT-C01-L01-O02",
        "2",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-ABACUS-01",
        "firefly_abacus",
        "ස්ථානීය අගය වගුව හා ගණක රාමුව",
        "medium",
        "G5-MAT-C01-L01-K02",
        "xiv",
        "draft_content_point_high_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-EXPAND-01",
        "firefly_abacus",
        "සංඛ්‍යා ගොඩනැගීම හා විහිදුවීම",
        "medium",
        "G5-MAT-C01-L01-O04",
        "2",
        "draft_trace_medium_confidence",
    ),
    AtomicSkill(
        "G5-MAT-NUM-EXTREME-01",
        "kite_workshop",
        "දී ඇති ඉලක්කම්වලින් විශාලතම හා කුඩාතම සංඛ්‍යාව",
        "medium",
        "G5-MAT-C01-L01-O02",
        "2",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-NUM-LEADING-ZERO-01",
        "kite_workshop",
        "කුඩාතම සංඛ්‍යාවේ මුල් ශූන්‍ය රීතිය",
        "medium",
        "G5-MAT-C01-L01-O02",
        "2",
        "draft_activity_mapping_requires_educator_review",
    ),
    AtomicSkill(
        "G5-MAT-NUM-ORDER-01",
        "river_route_rally",
        "99 999 තෙක් ආරෝහණ හා අවරෝහණ පිළිවෙළ",
        "medium",
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


def expanded_terms(number: int) -> tuple[int, ...]:
    terms = tuple(value for value in reversed(place_values(number)) if value)
    return terms or (0,)


def expanded_form(number: int) -> str:
    return " + ".join(str(value) for value in expanded_terms(number))


def abacus_digits(number: int) -> tuple[int, int, int, int, int, int]:
    if number < 0 or number > 999_999:
        raise ValueError("NUMBER_OUT_OF_RANGE")
    return tuple(int(value) for value in f"{number:06d}")  # type: ignore[return-value]


def construct_extreme(digits: tuple[int, ...], *, greatest: bool) -> int:
    if not 3 <= len(digits) <= 5 or any(digit < 0 or digit > 9 for digit in digits):
        raise ValueError("INVALID_DIGITS")
    if greatest:
        ordered = sorted(digits, reverse=True)
    else:
        ordered = sorted(digits)
        if ordered[0] == 0:
            first_nonzero = next((i for i, value in enumerate(ordered) if value), None)
            if first_nonzero is None:
                raise ValueError("LEADING_ZERO_ONLY")
            ordered[0], ordered[first_nonzero] = ordered[first_nonzero], ordered[0]
    return int("".join(map(str, ordered)))


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
    elif skill_id.endswith("100000-01"):
        value = response.get("constructed_number")
        correct = type(value) is int and value == game.get("number")
        normalized["constructed_number"] = value
        error = "zero_placeholder_omitted"
        expected_kind = "constructed_number"
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
    elif skill_id.endswith("EXPAND-01"):
        terms = response.get("terms")
        expected = expanded_terms(int(game["number"]))
        valid_terms = isinstance(terms, list) and all(type(value) is int for value in terms)
        correct = valid_terms and tuple(terms) == expected
        normalized["terms"] = terms if valid_terms else []
        error = "expanded_term_omitted_or_misplaced"
        expected_kind = "expanded_form"
    elif skill_id.endswith(("EXTREME-01", "LEADING-ZERO-01")):
        digits = response.get("digits")
        supplied = tuple(int(value) for value in game["digits"])
        valid_digits = (
            isinstance(digits, list)
            and len(digits) == len(supplied)
            and all(type(value) is int and 0 <= value <= 9 for value in digits)
            and sorted(digits) == sorted(supplied)
        )
        leading_zero = bool(valid_digits and digits[0] == 0)
        expected = construct_extreme(supplied, greatest=bool(game["greatest"]))
        correct = valid_digits and not leading_zero and int("".join(map(str, digits))) == expected
        normalized.update(digits=digits if valid_digits else [], leading_zero=leading_zero)
        error = "leading_zero_first" if leading_zero else "ascending_descending_reversed"
        expected_kind = "digit_order"
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


def _spaced(value: int) -> str:
    """``39 999``: thousands separated by a space, as the games print numbers."""

    return f"{value:,}".replace(",", " ")


def generate_item(
    skill_id: str, *, role: str, seed: int, simpler: bool = False
) -> NumberWorldItem:
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
    elif skill_id.endswith("100000-01"):
        # A random round milestone, one below it given: 39 999 + 1 = 40 000, 7 999 + 1 = 8 000,
        # up to 99 999 + 1 = 100 000. The simpler version stays at three and four digits.
        power = rng.choice((2, 3) if simpler else (3, 4, 4))
        lead = rng.randint(1, 9)
        if not simpler and rng.random() < 0.2:
            power, lead = 5, 1
        number = lead * 10**power
        base = number - 1
        answer = str(number)
        prompt = f"රටාව බලන්න. {_spaced(base)} ට 1ක් එකතු කළ විට ලැබෙන සංඛ්‍යාව තෝරන්න."
        distractors = [
            (str(number // 10), "zero_placeholder_omitted"),
            (str(base + 10), "zero_placeholder_omitted"),
            (str(number * 10), "counts_places_from_wrong_direction"),
        ]
        game_data.update(
            number=number,
            milestone=True,
            milestone_steps=tuple(lead * 10**k for k in range(1, power + 1)),
            milestone_choices=(number // 10, number, number * 10),
        )
    elif skill_id.endswith("ABACUS-01"):
        number = rng.choice(
            (205, 370, 904, 610) if simpler else (40_205, 50_070, 70_304, 90_010)
        )
        answer = str(number)
        prompt = f"{number:,} සංඛ්‍යාව දඬු හයේ ගණක රාමුවේ සාදන්න."
        distractors = [
            (str(int(str(number).replace("0", ""))), "zero_placeholder_omitted"),
            (str(number // 10), "place_shift_right"),
            (str(min(999_999, number * 10)), "place_shift_left"),
        ]
        game_data.update(number=number, rods=abacus_digits(number))
    elif skill_id.endswith("EXPAND-01"):
        number = rng.choice(
            (305, 406, 280, 704) if simpler else (42_305, 70_406, 90_080, 18_204)
        )
        answer = expanded_form(number)
        prompt = f"{number:,} සංඛ්‍යාව ස්ථානීය අගය වගුවෙන් විහිදුවන්න."
        terms = answer.split(" + ")
        distractors = [
            (" + ".join(terms[:-1]), "expanded_term_omitted_or_misplaced"),
            (str(number), "digit_as_represented_value"),
            (expanded_form(number // 10), "place_shift_right"),
        ]
        game_data.update(number=number, expanded=answer)
    elif skill_id.endswith(("EXTREME-01", "LEADING-ZERO-01")):
        count = 3 if simpler else rng.randint(3, 5)
        digits = rng.sample(range(1, 10), count - 1)
        digits.insert(rng.randrange(count), 0)
        greatest = skill_id.endswith("EXTREME-01")
        answer = str(construct_extreme(tuple(digits), greatest=greatest))
        prompt = f"{digits} → {'විශාලතම' if greatest else 'කුඩාතම'} සංඛ්‍යාව"
        zero_first = "".join(map(str, sorted(digits)))
        distractors = [
            (zero_first, "leading_zero_first"),
            (
                str(construct_extreme(tuple(digits), greatest=not greatest)),
                "ascending_descending_reversed",
            ),
            (str(int("".join(map(str, digits)))), "first_visible_digit_only"),
        ]
        game_data.update(digits=digits, greatest=greatest)
    else:
        prefix = rng.randint(1, 8) * 1000
        values = tuple(
            prefix + value for value in rng.sample(range(10, 990), 3 if simpler else 4)
        )
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


def infer_belief(error_code: str, *, sparse: bool = False) -> dict[str, object]:
    probabilities = {code: 0.03 for code in MISCONCEPTIONS}
    probabilities["unknown_or_other"] = 0.20 if not sparse else 0.73
    if not sparse and error_code in probabilities and error_code != "unknown_or_other":
        probabilities[error_code] = 0.53
    total = sum(probabilities.values())
    normalized = {key: value / total for key, value in probabilities.items()}
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


_SCAFFOLD_BASE_PREDICTION = 0.08
_SCAFFOLD_INDEX_INCREMENT = 0.01
_SCAFFOLD_AFFINITY_BONUS = 0.09
_SCAFFOLD_UNCERTAINTY_ABSTAINED = 0.18
_SCAFFOLD_UNCERTAINTY_NORMAL = 0.09
_SCAFFOLD_UNIFORM_PROPENSITY = 1 / 3


def scaffold_decision(
    skill_id: str, condition: str, belief: dict[str, object], *, seed: int
) -> dict[str, object]:
    top = str(belief["top_hypothesis"])
    abstained = bool(belief["abstained"])
    affinity = {
        "visual_guidance": {
            "place_shift_left",
            "place_shift_right",
            "zero_placeholder_omitted",
            "first_visible_digit_only",
        },
        "worked_parallel_example": {
            "digit_as_represented_value",
            "expanded_term_omitted_or_misplaced",
        },
        "step_by_step_guidance": {
            "counts_places_from_wrong_direction",
            "leading_zero_first",
            "ascending_descending_reversed",
        },
    }
    candidates = []
    for index, scaffold in enumerate(SCAFFOLDS):
        predicted = _SCAFFOLD_BASE_PREDICTION + index * _SCAFFOLD_INDEX_INCREMENT + (_SCAFFOLD_AFFINITY_BONUS if top in affinity[scaffold] else 0.0)
        candidates.append(
            {
                "scaffold_type": scaffold,
                "eligible": True,
                "exclusion_reasons": [],
                "predicted_raw_ig": round(predicted, 6),
                "uncertainty": _SCAFFOLD_UNCERTAINTY_ABSTAINED if abstained else _SCAFFOLD_UNCERTAINTY_NORMAL,
                "propensity": _SCAFFOLD_UNIFORM_PROPENSITY,
            }
        )
    if condition == "baseline":
        selected = "visual_guidance"
        used_model1 = False
        mode = "deterministic_baseline"
    elif abstained:
        selected = "visual_guidance"
        used_model1 = True
        mode = "proposed_shadow_conservative_fallback"
    else:
        selected = max(candidates, key=lambda row: float(row["predicted_raw_ig"]))["scaffold_type"]
        used_model1 = True
        mode = "proposed_shadow"
    return {
        "policy_version": POLICY_VERSION,
        "skill_id": skill_id,
        "condition": condition,
        "mode": mode,
        "uses_complete_model1_distribution": used_model1,
        "objective": "predicted_raw_independence_gain",
        "seed": seed,
        "selected_action": selected,
        "candidates": candidates,
    }


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

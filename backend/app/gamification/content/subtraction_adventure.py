"""Draft, source-linked Subtraction Adventure content for Grade 5 Sinhala maths.

Photographed textbook structures are preserved as deterministic constructed-response
families. This module does not persist learner identity and never trusts a client score.
Two-regroup items follow the repository's draft outcome mapping; the photographed page
does not supply that worked procedure. All mappings remain unreviewed.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-04"
UNIVERSAL_SKILL_ID = "MAT-OPS"
PACKAGE_VERSION = "g5-mat-subtraction-adventure-draft-v1"
CATALOGUE_VERSION = "g5-mat-subtraction-misconceptions-v1"
FEATURE_VERSION = "g5-mat-subtraction-features-v1"
MAPPING_VERSION = "g5-mat-subtraction-mapping-v1"
MODEL_VERSION = "g5-mat-subtraction-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-subtraction-raw-ig-shadow-v1"
SCORING_VERSION = "g5-mat-subtraction-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-subtraction-parallel-v1"
SCAFFOLD_VERSION = "g5-mat-subtraction-scaffolds-v1"

Chapter = Literal["place_value_board", "regrouping_workshop", "difference_story"]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]
Place = Literal["thousands", "hundreds", "tens", "ones"]
Relationship = Literal["difference_between", "how_many_more"]

PLACES: tuple[Place, ...] = ("thousands", "hundreds", "tens", "ones")
PLACE_LABELS = {"thousands": "දහස්", "hundreds": "සිය", "tens": "දහය", "ones": "එක"}
PLACE_INDEX = {place: index for index, place in enumerate(PLACES)}

# Photographed evidence. These exact pairs are verified by the analyser and then
# excluded from unsupported item generation so the answers are not replayed.
TEXTBOOK_PAIRS = {
    (685, 339),
    (7828, 2506),
    (4497, 2359),
    (720, 512),
    (425, 319),
}


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    source_node_id: str
    source_status: str
    response_kind: str
    relationship: Relationship | None = None


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-MAT-SUB-NO-REGROUP-01",
        "place_value_board",
        "ස්ථාන අගය එකට ගැලපූ අඩු කිරීම",
        "easy",
        "G5-MAT-C07-L01",
        "provisional_source_linked",
        "column_subtraction",
    ),
    AtomicSkill(
        "G5-MAT-SUB-EXPANDED-01",
        "place_value_board",
        "විහිදුණු ආකාරයෙන් අඩු කිරීම",
        "easy_medium",
        "G5-MAT-C07-L01",
        "provisional_source_linked",
        "expanded_subtraction",
    ),
    AtomicSkill(
        "G5-MAT-C07-L01-O01",
        "regrouping_workshop",
        "ගෙන ඒම් එකක් සහිත අඩු කිරීම",
        "medium",
        "G5-MAT-C07-L01-O01",
        "draft_medium_confidence",
        "column_subtraction",
    ),
    AtomicSkill(
        "G5-MAT-C07-L01-O02",
        "regrouping_workshop",
        "ගෙන ඒම් දෙකක් සහිත අඩු කිරීම",
        "medium_hard",
        "G5-MAT-C07-L01-O02",
        "draft_medium_confidence_repository_not_photograph",
        "column_subtraction",
    ),
    AtomicSkill(
        "G5-MAT-SUB-DIFF-BETWEEN-01",
        "difference_story",
        "කාණ්ඩ දෙකක වෙනස",
        "medium",
        "G5-MAT-C07-L01-O03",
        "provisional_source_linked",
        "difference_story",
        "difference_between",
    ),
    AtomicSkill(
        "G5-MAT-SUB-HOW-MANY-MORE-01",
        "difference_story",
        "කොපමණ වැඩියිද",
        "medium",
        "G5-MAT-C07-L01-O03",
        "provisional_source_linked",
        "difference_story",
        "how_many_more",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

MISCONCEPTIONS = (
    "subtracts_larger_digit_in_column",
    "reverses_minuend_and_subtrahend",
    "starts_from_left",
    "misaligns_place_columns",
    "omits_internal_zero",
    "copies_digit_unchanged",
    "unnecessary_exchange",
    "fails_to_exchange",
    "wrong_exchange_source",
    "source_decreased_without_adding_ten",
    "ten_added_without_decreasing_source",
    "exchanged_ten_counted_as_one",
    "uses_original_source_digit",
    "adjusted_digit_wrong_column",
    "only_one_of_two_exchanges",
    "uses_addition_instead",
    "smaller_quantity_as_minuend",
    "calculates_total_for_difference",
    "digits_wrong_order",
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
        "estimated_interaction_budget": 6 if scaffold != "visual_guidance" else 3,
        "eligibility_constraints": ["grade5", "sinhala", "development_or_test", "draft_opt_in"],
        "answer_leakage_rule": "exact_failed_item_only_inside_active_support",
        "withdrawal_behavior": "remove_digits_exchanges_equations_highlights_announcements_and_handlers",
        "version": SCAFFOLD_VERSION,
        "review_status": "unreviewed_blocked",
    }
    for scaffold in SCAFFOLDS
}

STORY_CONTEXTS: dict[Relationship, tuple[dict[str, object], ...]] = {
    "difference_between": (
        {
            "context_id": "station_flow",
            "scene": "station",
            "asset": "/curriculum/game/G5-AREA-MAT-01/route-boat.png",
            "first_label_si": "ඇතුළු වූ මගීන්",
            "second_label_si": "පිටව ගිය මගීන්",
            "prompt_si": "මගීන් ඇතුළු වූ සංඛ්‍යාව සහ පිටව ගිය සංඛ්‍යාව අතර වෙනස සොයන්න.",
        },
        {
            "context_id": "library_flow",
            "scene": "library",
            "asset": "/curriculum/game/G5-AREA-MAT-02/empty-fruit-basket.png",
            "first_label_si": "ගෙනා පොත්",
            "second_label_si": "බාර දුන් පොත්",
            "prompt_si": "ගෙනා පොත් ගණන සහ බාර දුන් පොත් ගණන අතර වෙනස සොයන්න.",
        },
        {
            "context_id": "bus_flow",
            "scene": "bus",
            "asset": "/curriculum/game/G5-AREA-MAT-02/tuk-tuk.png",
            "first_label_si": "බස් රථයට නැග්ග අය",
            "second_label_si": "බස් රථයෙන් බැස්ස අය",
            "prompt_si": "බස් රථයට නැග්ග සංඛ්‍යාව සහ බැස්ස සංඛ්‍යාව අතර වෙනස සොයන්න.",
        },
    ),
    "how_many_more": (
        {
            "context_id": "fruit_baskets",
            "scene": "fruits",
            "asset": "/curriculum/game/G5-AREA-MAT-02/fruit-tokens.png",
            "first_label_si": "පළමු කූඩයේ පළතුරු",
            "second_label_si": "දෙවන කූඩයේ පළතුරු",
            "prompt_si": "පළමු කූඩයේ පළතුරු දෙවන කූඩයට වඩා කොපමණ වැඩියිද?",
        },
        {
            "context_id": "seedling_trays",
            "scene": "seedlings",
            "asset": "/curriculum/game/G5-AREA-MAT-02/cargo-parcel.png",
            "first_label_si": "පළමු තැටියේ පැළ",
            "second_label_si": "දෙවන තැටියේ පැළ",
            "prompt_si": "පළමු තැටියේ පැළ දෙවන තැටියට වඩා කොපමණ වැඩියිද?",
        },
        {
            "context_id": "class_groups",
            "scene": "groups",
            "asset": "/curriculum/game/G5-AREA-MAT-02/school-building-token-a.png",
            "first_label_si": "අ පන්තියේ ළමයි",
            "second_label_si": "ආ පන්තියේ ළමයි",
            "prompt_si": "අ පන්තියේ ළමයි ආ පන්තියට වඩා කොපමණ වැඩියිද?",
        },
    ),
}


@dataclass(frozen=True, slots=True)
class SubtractionItem:
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


def place_terms(value: int, width: int) -> tuple[int, ...]:
    """Return width place terms, preserving internal zeros."""

    if value < 0 or width < 1 or width > 4:
        raise ValueError("NUMBER_OUT_OF_RANGE")
    digits = [int(character) for character in f"{value:0{width}d}"]
    return tuple(digit * (10 ** (width - 1 - index)) for index, digit in enumerate(digits))


def analyze_subtraction(minuend: int, subtrahend: int) -> dict[str, object]:
    """Recompute place alignment, exchanges, and expanded terms on the server."""

    if type(minuend) is not int or type(subtrahend) is not int:
        raise ValueError("INVALID_OPERANDS")
    if minuend < 0 or subtrahend < 0 or minuend > 9999 or subtrahend > 9999:
        raise ValueError("NUMBER_OUT_OF_RANGE")
    if minuend < subtrahend:
        raise ValueError("NEGATIVE_DIFFERENCE")
    width = max(len(str(minuend)), 1)
    places = PLACES[-width:]
    minuend_digits = [int(character) for character in f"{minuend:0{width}d}"]
    subtrahend_digits = [int(character) for character in f"{subtrahend:0{width}d}"]
    working = minuend_digits[:]
    exchanges: list[dict[str, str]] = []
    across_zero = False
    for index in range(width - 1, -1, -1):
        if working[index] < subtrahend_digits[index]:
            source = index - 1
            if source < 0 or working[source] <= 0:
                across_zero = True
                break
            working[source] -= 1
            working[index] += 10
            exchanges.append({"from_place": places[source], "to_place": places[index]})
    result = minuend - subtrahend
    to_places = {row["to_place"] for row in exchanges}
    sequential = any(row["from_place"] in to_places for row in exchanges)
    return {
        "width": width,
        "places": places,
        "place_labels_si": tuple(PLACE_LABELS[place] for place in places),
        "minuend_digits": tuple(minuend_digits),
        "subtrahend_digits": tuple(subtrahend_digits),
        "adjusted_digits": None if across_zero else tuple(working),
        "exchanges": tuple(exchanges),
        "regroup_positions": tuple(row["to_place"] for row in exchanges),
        "result": result,
        "result_digits": tuple(int(character) for character in f"{result:0{width}d}"),
        "regroup_count": 0 if across_zero else len(exchanges),
        "borrow_across_zero": across_zero,
        "sequential": sequential and not across_zero,
        "zero_mask": tuple(int(digit == 0) for digit in subtrahend_digits),
        "minuend_terms": place_terms(minuend, width),
        "subtrahend_terms": place_terms(subtrahend, width),
        "adjusted_terms": (
            None
            if across_zero
            else tuple(digit * (10 ** (width - 1 - index)) for index, digit in enumerate(working))
        ),
        "result_terms": place_terms(result, width),
    }


def _seed(skill_id: str, role: str, seed: int) -> random.Random:
    value = int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")
    return random.Random(value)


def _family_seed(skill_id: str, seed: int) -> random.Random:
    value = int.from_bytes(
        hashlib.sha256(f"{skill_id}:family:{seed}".encode()).digest()[:8], "big"
    )
    return random.Random(value)


# Simpler version: the fewest columns and exchanges that still practise the same skill.
_SIMPLER_PROFILES: dict[str, tuple[int, tuple[str, ...], bool]] = {
    "G5-MAT-SUB-NO-REGROUP-01": (2, (), False),
    "G5-MAT-SUB-EXPANDED-01": (3, (), False),
    "G5-MAT-C07-L01-O01": (3, ("ones",), False),
    "G5-MAT-C07-L01-O02": (3, ("tens", "ones"), True),
}
_SIMPLER_STORY_PROFILE = (3, (), False)


def _simpler_profile(skill: AtomicSkill) -> dict[str, object]:
    width, destinations, sequential = _SIMPLER_PROFILES.get(skill.skill_id, _SIMPLER_STORY_PROFILE)
    return {
        "width": width,
        "destinations": destinations,
        "sequential": sequential,
        "zero_indexes": (),
        "relationship": skill.relationship,
    }


def _profile(skill: AtomicSkill, family: random.Random) -> dict[str, object]:
    if skill.skill_id == "G5-MAT-SUB-NO-REGROUP-01":
        width = family.choice((2, 3, 4))
        zero_indexes = (family.randrange(1, width - 1),) if width >= 3 and family.randrange(2) else ()
        destinations: tuple[str, ...] = ()
        sequential = False
    elif skill.skill_id == "G5-MAT-SUB-EXPANDED-01":
        width = family.choice((3, 4))
        zero_indexes = (width - 2,) if family.randrange(2) else ()
        destinations = ()
        sequential = False
    elif skill.skill_id == "G5-MAT-C07-L01-O01":
        width = family.choice((3, 4))
        available = ("ones", "tens") if width == 3 else ("ones", "tens", "hundreds")
        destinations = (family.choice(available),)
        sequential = False
        zero_indexes = ()
    elif skill.skill_id == "G5-MAT-C07-L01-O02":
        width = 4
        sequential = bool(family.randrange(2))
        destinations = ("tens", "ones") if sequential else ("hundreds", "ones")
        zero_indexes = ()
    else:
        width = family.choice((3, 4))
        destinations = ("ones",) if family.randrange(2) else ()
        sequential = False
        zero_indexes = ()
    return {
        "width": width,
        "destinations": destinations,
        "sequential": sequential,
        "zero_indexes": zero_indexes,
        "relationship": skill.relationship,
    }


def _construct_pair(
    rng: random.Random,
    *,
    width: int,
    destinations: tuple[str, ...],
    zero_indexes: tuple[int, ...],
) -> tuple[int, int]:
    places = PLACES[-width:]
    wanted = tuple(place for place in reversed(places) if place in destinations)
    for _ in range(20_000):
        minuend_digits = [rng.randint(2, 8) for _ in range(width)]
        minuend_digits[0] = rng.randint(max(3, len(destinations) + 1), 8)
        subtrahend_digits = [0] * width
        working = minuend_digits[:]
        failed = False
        for index in range(width - 1, -1, -1):
            if places[index] in destinations:
                if index == 0 or working[index - 1] <= 0 or working[index] >= 9:
                    failed = True
                    break
                subtrahend_digits[index] = rng.randint(working[index] + 1, 9)
                working[index - 1] -= 1
                working[index] += 10
            elif index in zero_indexes:
                subtrahend_digits[index] = 0
            else:
                if working[index] <= 0:
                    failed = True
                    break
                subtrahend_digits[index] = rng.randint(1, working[index])
        if failed:
            continue
        if any((digit == 0) != (index in zero_indexes) for index, digit in enumerate(subtrahend_digits)):
            continue
        minuend = int("".join(str(digit) for digit in minuend_digits))
        subtrahend = int("".join(str(digit) for digit in subtrahend_digits))
        if (minuend, subtrahend) in TEXTBOOK_PAIRS or minuend == subtrahend:
            continue
        try:
            analysed = analyze_subtraction(minuend, subtrahend)
        except ValueError:
            continue
        if analysed["borrow_across_zero"] or analysed["regroup_positions"] != wanted:
            continue
        return minuend, subtrahend
    raise RuntimeError("SUBTRACTION_ITEM_GENERATION_EXHAUSTED")


def _ints(value: object) -> list[int] | None:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        return None
    return value


def _exchange_rows(value: object) -> list[dict[str, str]] | None:
    if not isinstance(value, list):
        return None
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"from_place", "to_place"}:
            return None
        source = item.get("from_place")
        destination = item.get("to_place")
        if source not in PLACES or destination not in PLACES:
            return None
        if PLACE_INDEX[str(source)] + 1 != PLACE_INDEX[str(destination)]:
            return None
        rows.append({"from_place": str(source), "to_place": str(destination)})
    return rows


def _column_error(
    analysed: Mapping[str, object], digits: list[int], exchanges: list[dict[str, str]]
) -> str:
    expected_digits = list(analysed["result_digits"])  # type: ignore[arg-type]
    expected_exchanges = [dict(row) for row in analysed["exchanges"]]  # type: ignore[union-attr]
    width = int(analysed["width"])
    if len(digits) != width or any(digit < 0 or digit > 9 for digit in digits):
        if len(digits) < width and 0 in expected_digits:
            return "omits_internal_zero"
        return "incomplete_response" if len(digits) != width else "unknown_or_other"
    # A right answer is right even when it looks like a copied number (82 − 41 = 41).
    if digits == expected_digits and exchanges == expected_exchanges:
        return "correct"
    if digits == list(reversed(expected_digits)) and digits != expected_digits:
        return "digits_wrong_order"
    minuend_digits = list(analysed["minuend_digits"])  # type: ignore[arg-type]
    subtrahend_digits = list(analysed["subtrahend_digits"])  # type: ignore[arg-type]
    if digits == minuend_digits or digits == subtrahend_digits:
        return "copies_digit_unchanged"
    independent = [abs(left - right) % 10 for left, right in zip(minuend_digits, subtrahend_digits, strict=True)]
    if digits == independent and independent != expected_digits:
        return "subtracts_larger_digit_in_column"
    if len(exchanges) > len(expected_exchanges) and not expected_exchanges:
        return "unnecessary_exchange"
    if len(exchanges) < len(expected_exchanges):
        if len(expected_exchanges) == 2 and len(exchanges) == 1:
            return "only_one_of_two_exchanges"
        return "fails_to_exchange"
    if exchanges != expected_exchanges:
        return "wrong_exchange_source"
    if digits != expected_digits:
        minuend = int("".join(str(digit) for digit in minuend_digits))
        subtrahend = int("".join(str(digit) for digit in subtrahend_digits))
        entered = int("".join(str(digit) for digit in digits))
        if entered == minuend + subtrahend or entered == (minuend + subtrahend) % (10**width):
            return "uses_addition_instead"
        return "unknown_or_other"
    return "correct"


def validate_constructed_response(
    item: SubtractionItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, SubtractionItem) else item.get("game_data")
    skill_id = item.skill_id if isinstance(item, SubtractionItem) else item.get("skill_id")
    if not isinstance(game, Mapping) or not isinstance(skill_id, str) or skill_id not in SKILLS:
        raise TypeError("INVALID_ITEM")
    skill = SKILLS[skill_id]
    kind = response.get("kind")
    normalized: dict[str, object] = {"kind": str(kind)}
    analysed = analyze_subtraction(int(game["minuend"]), int(game["subtrahend"]))
    if skill.response_kind == "column_subtraction":
        allowed = {"kind", "result_digits", "exchanges"}
        digits = _ints(response.get("result_digits"))
        exchanges = _exchange_rows(response.get("exchanges"))
        normalized.update(
            result_digits=digits if digits is not None else [],
            exchanges=exchanges if exchanges is not None else [],
        )
        if kind != "column_subtraction" or set(response) != allowed or digits is None or exchanges is None:
            return False, "unknown_or_other", normalized
        error = _column_error(analysed, digits, exchanges)
    elif skill.response_kind == "expanded_subtraction":
        allowed = {
            "kind",
            "minuend_terms",
            "subtrahend_terms",
            "adjusted_minuend_terms",
            "result_terms",
            "result",
        }
        fields = {
            "minuend_terms": _ints(response.get("minuend_terms")),
            "subtrahend_terms": _ints(response.get("subtrahend_terms")),
            "adjusted_minuend_terms": _ints(response.get("adjusted_minuend_terms")),
            "result_terms": _ints(response.get("result_terms")),
        }
        result = response.get("result")
        normalized.update({key: value if value is not None else [] for key, value in fields.items()})
        normalized["result"] = result
        if (
            kind != "expanded_subtraction"
            or set(response) != allowed
            or any(value is None for value in fields.values())
            or type(result) is not int
        ):
            return False, "unknown_or_other", normalized
        width = int(analysed["width"])
        if any(len(value) != width for value in fields.values()):  # type: ignore[arg-type]
            error = (
                "omits_internal_zero"
                if 0 in analysed["subtrahend_terms"] or 0 in analysed["result_terms"]  # type: ignore[operator]
                else "incomplete_response"
            )
        elif any(term < 0 or term > 9000 for value in fields.values() for term in value):  # type: ignore[union-attr]
            error = "unknown_or_other"
        elif (
            fields["minuend_terms"] != list(analysed["minuend_terms"])  # type: ignore[arg-type]
            or fields["subtrahend_terms"] != list(analysed["subtrahend_terms"])  # type: ignore[arg-type]
            or fields["adjusted_minuend_terms"] != list(analysed["adjusted_terms"])  # type: ignore[arg-type]
            or fields["result_terms"] != list(analysed["result_terms"])  # type: ignore[arg-type]
            or result != analysed["result"]
        ):
            if fields["result_terms"] == list(reversed(analysed["result_terms"])):  # type: ignore[arg-type]
                error = "digits_wrong_order"
            elif result == int(game["minuend"]) + int(game["subtrahend"]):
                error = "uses_addition_instead"
            else:
                error = "unknown_or_other"
        else:
            error = "correct"
    else:
        allowed = {
            "kind",
            "relationship",
            "minuend_source",
            "subtrahend_source",
            "result_digits",
            "result",
        }
        digits = _ints(response.get("result_digits"))
        result = response.get("result")
        relationship = response.get("relationship")
        minuend_source = response.get("minuend_source")
        subtrahend_source = response.get("subtrahend_source")
        normalized.update(
            relationship=relationship,
            minuend_source=minuend_source,
            subtrahend_source=subtrahend_source,
            result_digits=digits if digits is not None else [],
            result=result,
        )
        if (
            kind != "difference_story"
            or set(response) != allowed
            or digits is None
            or type(result) is not int
            or relationship not in {"difference_between", "how_many_more"}
            or minuend_source not in {"first", "second"}
            or subtrahend_source not in {"first", "second"}
        ):
            return False, "unknown_or_other", normalized
        if minuend_source == subtrahend_source:
            return False, "incomplete_response", normalized
        if relationship != game["relationship"]:
            return False, "unknown_or_other", normalized
        if (
            minuend_source != game["minuend_source"]
            or subtrahend_source != game["subtrahend_source"]
        ):
            error = "smaller_quantity_as_minuend"
        elif result == int(game["first_value"]) + int(game["second_value"]):
            error = "calculates_total_for_difference"
        elif digits == list(reversed(analysed["result_digits"])) and digits != list(  # type: ignore[arg-type]
            analysed["result_digits"]
        ):
            error = "digits_wrong_order"
        elif len(digits) != int(analysed["width"]):
            error = "incomplete_response"
        elif digits != list(analysed["result_digits"]) or result != analysed["result"]:  # type: ignore[arg-type]
            error = "unknown_or_other"
        else:
            error = "correct"
    return error == "correct", error, normalized


def apply_interaction_evidence(error_code: str, summary: Mapping[str, object] | None) -> str:
    """Use bounded interaction counts only when the payload itself is unexplained."""

    if error_code != "unknown_or_other" or not summary:
        return error_code
    if summary.get("started_from_ones") is False:
        return "starts_from_left"
    if summary.get("alignment_valid") is False:
        return "misaligns_place_columns"
    invalid_exchanges = summary.get("invalid_exchange_count")
    if type(invalid_exchanges) is int and invalid_exchanges > 0:
        return "wrong_exchange_source"
    if type(summary.get("operation_changes")) is int and int(summary["operation_changes"]) > 0:
        return "uses_addition_instead"
    if type(summary.get("story_reorder_count")) is int and int(summary["story_reorder_count"]) > 0:
        return "smaller_quantity_as_minuend"
    return error_code


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> SubtractionItem:
    """The same subtraction skill with fewer columns and the fewest exchanges it needs."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(
    skill_id: str, *, role: str, seed: int, simpler: bool = False
) -> SubtractionItem:
    if skill_id not in SKILLS:
        raise ValueError("SUBTRACTION_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    skill = SKILLS[skill_id]
    family = _family_seed(skill_id, seed)
    profile = _simpler_profile(skill) if simpler else _profile(skill, family)
    rng = _seed(skill_id, role, seed)
    width = int(profile["width"])
    destinations = tuple(profile["destinations"])  # type: ignore[arg-type]
    zero_indexes = tuple(profile["zero_indexes"])  # type: ignore[arg-type]
    minuend, subtrahend = _construct_pair(
        rng, width=width, destinations=destinations, zero_indexes=zero_indexes
    )
    analysed = analyze_subtraction(minuend, subtrahend)
    if analysed["borrow_across_zero"] or int(analysed["regroup_count"]) != len(destinations):
        raise RuntimeError("SUBTRACTION_ITEM_GENERATION_EXHAUSTED")
    places = tuple(analysed["places"])
    game: dict[str, object] = {
        "chapter": skill.chapter,
        "response_kind": skill.response_kind,
        "minuend": minuend,
        "subtrahend": subtrahend,
        "width": width,
        "places": places,
        "place_labels_si": tuple(PLACE_LABELS[place] for place in places),
        "blank_count": width,
        "regroup_count": analysed["regroup_count"],
        "regroup_positions": analysed["regroup_positions"],
        "sequential": analysed["sequential"],
        "zero_indexes": zero_indexes,
        "zero_mask": analysed["zero_mask"],
        "exchanges": analysed["exchanges"],
        "result_digits": analysed["result_digits"],
        "result": analysed["result"],
        "minuend_terms": analysed["minuend_terms"],
        "subtrahend_terms": analysed["subtrahend_terms"],
        "adjusted_terms": analysed["adjusted_terms"],
        "result_terms": analysed["result_terms"],
        "borrow_across_zero": False,
    }
    prompt = "ස්ථාන අගය තීරු ගැලපී අඩු කර පිළිතුර ගොඩනඟන්න."
    if skill.response_kind == "expanded_subtraction":
        prompt = "සංඛ්‍යා දෙක විහිදුණු ආකාරයට ලියා අඩු කරන්න."
    if skill.relationship is not None:
        contexts = STORY_CONTEXTS[skill.relationship]
        context_index = family.randrange(len(contexts))
        if role == "unsupported_after":
            context_index = (context_index + 1) % len(contexts)
        context = dict(contexts[context_index])
        first_value, second_value = minuend, subtrahend
        if rng.randrange(2):
            first_value, second_value = second_value, first_value
        larger = "first" if first_value >= second_value else "second"
        smaller = "second" if larger == "first" else "first"
        game.update(
            relationship=skill.relationship,
            context_id=context["context_id"],
            scene=context["scene"],
            asset=context["asset"],
            first_value=first_value,
            second_value=second_value,
            first_label_si=context["first_label_si"],
            second_label_si=context["second_label_si"],
            minuend_source=larger,
            subtrahend_source=smaller,
            minuend=max(first_value, second_value),
            subtrahend=min(first_value, second_value),
        )
        prompt = str(context["prompt_si"])
    signature = (
        f"{width}:{'-'.join(destinations) or 'none'}:seq-{int(bool(game['sequential']))}:"
        f"zeros-{','.join(map(str, zero_indexes)) or 'none'}:"
        f"rel-{skill.relationship or 'none'}"
    )
    suffix = ("B" if role == "unsupported_before" else "A") + ("S" if simpler else "")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"minuend": game["minuend"], "subtrahend": game["subtrahend"], "role": role + suffix},
            sort_keys=True,
        ).encode()
    ).hexdigest()[:12]
    return SubtractionItem(
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


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 1.0
) -> dict[str, object]:
    if error_code not in MISCONCEPTIONS and error_code != "correct":
        error_code = "unknown_or_other"
    if not 0 <= evidence_quality <= 1:
        raise ValueError("INVALID_EVIDENCE_QUALITY")
    probabilities = {code: 0.02 for code in MISCONCEPTIONS}
    probabilities["unknown_or_other"] = 0.18
    if sparse or evidence_quality < 0.5 or error_code == "correct":
        probabilities["unknown_or_other"] = 0.78
    elif error_code in probabilities:
        probabilities[error_code] = 0.52 + 0.10 * evidence_quality
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
        raise ValueError("SUBTRACTION_SKILL_NOT_FOUND")
    abstained = bool(belief.get("abstained"))
    first = {
        "G5-MAT-SUB-NO-REGROUP-01": "visual_guidance",
        "G5-MAT-SUB-EXPANDED-01": "visual_guidance",
        "G5-MAT-C07-L01-O01": "worked_parallel_example",
        "G5-MAT-C07-L01-O02": "worked_parallel_example",
        "G5-MAT-SUB-DIFF-BETWEEN-01": "visual_guidance",
        "G5-MAT-SUB-HOW-MANY-MORE-01": "visual_guidance",
    }[skill_id]
    candidates = []
    for index, scaffold in enumerate(SCAFFOLDS):
        candidates.append(
            {
                "scaffold_type": scaffold,
                "eligible": True,
                "exclusion_reasons": [],
                "predicted_raw_ig": round(0.08 + (0.04 if scaffold == first else index * 0.01), 6),
                "uncertainty": 0.20 if abstained else 0.12,
                "propensity": 1 / 3,
                **SCAFFOLD_CATALOGUE[scaffold],
            }
        )
    return {
        "policy_version": POLICY_VERSION,
        "skill_id": skill_id,
        "condition": condition,
        "mode": "deterministic_baseline" if condition == "baseline" else "proposed_shadow",
        "uses_complete_model1_distribution": condition == "proposed",
        "objective": "predicted_raw_independence_gain",
        "reward_source": "valid_post_withdrawal_raw_ig_only",
        "seed": seed,
        "selected_action": first,
        "candidates": candidates,
    }


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    minuend = int(game["minuend"])
    subtrahend = int(game["subtrahend"])
    if scaffold_type == "visual_guidance":
        if game.get("relationship") == "difference_between":
            return [
                "ප්‍රමාණ දෙක බලන්න.",
                "වැඩි ප්‍රමාණය සහ අඩු ප්‍රමාණය වෙන් කරන්න.",
                "එක තැනේ සිට වමට අඩු කරන්න.",
            ]
        if game.get("relationship") == "how_many_more":
            return [
                "සසඳන ප්‍රමාණ දෙක බලන්න.",
                "කොපමණ වැඩියිද යන්න වෙනසක් බව හඳුනා ගන්න.",
                "වැඩි ප්‍රමාණයෙන් අඩු ප්‍රමාණය අඩු කරන්න.",
            ]
        return [
            "එක තැන ඉස්මතු කර බලන්න.",
            "අඩු කිරීම එක තැනේ සිට වමට යයි.",
            "පිළිතුර නොබලා ඉලක්කම ලියන්න.",
        ]
    if minuend == 685 and subtrahend == 339:
        return [
            "එක තැනේ 5 සහ 9 බලමු. 5 න් 9 අඩු කළ නොහැක.",
            "දහය තැනින් එකක් ගෙන එමු. දහය 8 යන්න 7 වෙයි.",
            "එක 5 යන්න 15 වෙයි.",
            "15 − 9 = 6.",
            "7 − 3 = 4.",
            "6 − 3 = 3.",
        ]
    analysed = analyze_subtraction(minuend, subtrahend)
    if scaffold_type == "step_by_step_guidance":
        return [
            "දැන් වැඩ කරන තැන තෝරන්න.",
            "ඉලක්කම් දෙක සසඳන්න.",
            "හුවමාරුවක් අවශ්‍යද යන්න තීරණය කරන්න.",
            "අවශ්‍ය නම් මූලාශ්‍ර තීරුව තෝරා හුවමාරුව කරන්න.",
            "එම තැනේ පිළිතුරු ඉලක්කම ලියන්න.",
            "ඊළඟ වම් තැනට ගොස් අවසාන සංඛ්‍යාව තහවුරු කරන්න.",
        ]
    steps = [f"{minuend} − {subtrahend} එක තැනේ සිට වමට විසඳමු."]
    exchanges = list(analysed["exchanges"])  # type: ignore[arg-type]
    if exchanges:
        first = exchanges[0]
        steps.append(
            f"{PLACE_LABELS[first['from_place']]} තැනින් එකක් "
            f"{PLACE_LABELS[first['to_place']]} තැනට දහයක් කරමු."
        )
    steps.append("හුවමාරුවෙන් පසු එක තැනේ වෙනස ලියමු.")
    steps.append("ඊළඟ තීරුවල වෙනස ලියමු.")
    steps.append(f"පිළිතුර {analysed['result']} වේ.")
    return steps[:6]


def package_hash() -> str:
    payload = {
        "skills": [
            {
                "skill_id": skill.skill_id,
                "chapter": skill.chapter,
                "difficulty": skill.difficulty,
                "source_node_id": skill.source_node_id,
                "source_status": skill.source_status,
                "response_kind": skill.response_kind,
                "relationship": skill.relationship,
            }
            for skill in ATOMIC_SKILLS
        ],
        "misconceptions": MISCONCEPTIONS,
        "scaffolds": SCAFFOLD_CATALOGUE,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

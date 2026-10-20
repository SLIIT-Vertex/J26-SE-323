"""Server-authored Grade 5 division activities and canonical paper working."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-08"
UNIVERSAL_SKILL_ID = "MAT-DIV"
PACKAGE_VERSION = "g5-mat-division-adventure-draft-v1"
CATALOGUE_VERSION = "g5-mat-division-misconceptions-v1"
FEATURE_VERSION = "g5-mat-division-features-v1"
MAPPING_VERSION = "g5-mat-division-source-mapping-v1"
MODEL_VERSION = "g5-mat-division-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-division-deterministic-support-v1"
SCORING_VERSION = "g5-mat-division-trace-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-division-parallel-v1"

Chapter = Literal["equal_share", "paper_division", "division_story"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-DIV-SHARE-01", "equal_share", "දෙකට බෙදමු", "easy", "equal_sharing"),
    AtomicSkill("G5-MAT-DIV-PLAN-01", "equal_share", "බෙදීමේ සැලැස්ම", "easy_medium", "written_division"),
    AtomicSkill("G5-MAT-DIV-WRITTEN-01", "paper_division", "දිගු බෙදීම පුරවමු", "medium", "written_division"),
    AtomicSkill("G5-MAT-DIV-REMAINDER-01", "paper_division", "ඉතිරිය සොයමු", "medium_hard", "written_division"),
    AtomicSkill("G5-MAT-DIV-STORY-01", "division_story", "බෙදීමේ කතාව විසඳමු", "hard", "division_story"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
MISCONCEPTIONS = (
    "dividend_divisor_confused",
    "unequal_groups",
    "incorrect_quotient_digit",
    "quotient_digit_wrong_place",
    "incorrect_multiplication_fact",
    "incorrect_subtraction",
    "next_digit_not_brought_down",
    "wrong_digit_brought_down",
    "zero_quotient_digit_omitted",
    "invalid_remainder",
    "remainder_treated_as_quotient",
    "incorrect_contextual_interpretation",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class DivisionItem:
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


def validate_operands(dividend: object, divisor: object) -> tuple[int, int]:
    if type(dividend) is not int or type(divisor) is not int:
        raise ValueError("DIVISION_OPERANDS_MUST_BE_INTEGERS")
    if not 0 <= dividend <= 999 or not 1 <= divisor <= 9:
        raise ValueError("DIVISION_OPERANDS_OUT_OF_RANGE")
    return dividend, divisor


def quotient_and_remainder(dividend: int, divisor: int) -> tuple[int, int]:
    dividend, divisor = validate_operands(dividend, divisor)
    quotient, remainder = divmod(dividend, divisor)
    if not 0 <= remainder < divisor:
        raise ValueError("INVALID_REMAINDER")
    return quotient, remainder


def canonical_long_division(dividend: int, divisor: int) -> list[dict[str, int | None]]:
    """Return textbook divide/multiply/subtract/bring-down cycles with column positions."""

    dividend, divisor = validate_operands(dividend, divisor)
    digits = [int(value) for value in str(dividend)]
    steps: list[dict[str, int | None]] = []
    current = 0
    started = False
    for column, digit in enumerate(digits):
        current = current * 10 + digit
        if not started and current < divisor and column < len(digits) - 1:
            continue
        started = True
        quotient_digit = current // divisor
        product = quotient_digit * divisor
        subtraction = current - product
        brought_down = digits[column + 1] if column + 1 < len(digits) else None
        steps.append(
            {
                "step_index": len(steps),
                "partial_dividend": current,
                "quotient_digit": quotient_digit,
                "quotient_column": column,
                "partial_product": product,
                "subtraction_result": subtraction,
                "brought_down_digit": brought_down,
            }
        )
        current = subtraction
    return steps


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate_item(skill_id: str, *, role: str, seed: int) -> DivisionItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("DIVISION_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill_id == "G5-MAT-DIV-SHARE-01":
        dividend, divisor = rng.choice((20, 30, 50, 80)), 2
        prompt = f"{dividend} වස්තු කණ්ඩායම් දෙකට සමානව බෙදන්න."
        game: dict[str, object] = {"dividend": dividend, "divisor": divisor}
    elif skill_id == "G5-MAT-DIV-PLAN-01":
        divisor = rng.choice((2, 3, 4))
        dividend = divisor * rng.choice((11, 12, 21))
        prompt = f"{dividend} ÷ {divisor} හි පළමු කඩදාසි පියවර පුරවන්න."
        game = {"dividend": dividend, "divisor": divisor, "trace_limit": 1}
    elif skill_id == "G5-MAT-DIV-WRITTEN-01":
        divisor = rng.choice((2, 3, 4, 5))
        quotient = rng.choice((12, 21, 102, 111))
        dividend = divisor * quotient
        prompt = f"{dividend} ÷ {divisor} කඩදාසි ක්‍රමයෙන් විසඳන්න."
        game = {"dividend": dividend, "divisor": divisor}
    elif skill_id == "G5-MAT-DIV-REMAINDER-01":
        divisor = rng.choice((3, 4, 5, 6))
        quotient, remainder = rng.choice((12, 21, 31)), rng.randint(1, divisor - 1)
        dividend = divisor * quotient + remainder
        prompt = f"{dividend} ÷ {divisor} විසඳා ඉතිරිය සොයන්න."
        game = {"dividend": dividend, "divisor": divisor}
    else:
        divisor = rng.choice((3, 4, 5))
        quotient, remainder = rng.choice((12, 14, 21)), rng.randint(1, divisor - 1)
        dividend = divisor * quotient + remainder
        story_id = "basket_groups"
        prompt = f"පලතුරු {dividend}ක් බැගින් {divisor}ක් දමන කූඩවලට දමමු."
        game = {
            "dividend": dividend,
            "divisor": divisor,
            "story_id": story_id,
            "context_mode": "complete_groups_and_leftover",
            "object_label_si": "පලතුරු",
            "group_label_si": "කූඩ",
        }
    quotient, remainder = quotient_and_remainder(dividend, divisor)
    game.update(
        response_kind=skill.response_kind,
        has_remainder=remainder > 0,
        dividend_digit_count=len(str(dividend)),
        step_count=len(canonical_long_division(dividend, divisor)),
    )
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return DivisionItem(
        f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id,
        skill.chapter, role, prompt, (), "constructed-response", {}, game,
    )


def _strict(response: Mapping[str, object], keys: set[str]) -> None:
    if set(response) != keys:
        raise ValueError("MALFORMED_DIVISION_RESPONSE")


def _integer(value: object, minimum: int = 0, maximum: int = 999) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("DIVISION_VALUE_OUT_OF_RANGE")
    return value


def _integer_list(value: object, *, maximum: int = 999) -> list[int]:
    if not isinstance(value, list):
        raise TypeError("DIVISION_LIST_REQUIRED")
    return [_integer(entry, maximum=maximum) for entry in value]


def _normalize_steps(value: object) -> list[dict[str, int | None]]:
    if not isinstance(value, list) or len(value) > 3:
        raise ValueError("INVALID_WORKING_TRACE")
    normalized: list[dict[str, int | None]] = []
    keys = {
        "step_index", "partial_dividend", "quotient_digit", "quotient_column",
        "partial_product", "subtraction_result", "brought_down_digit",
    }
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != keys:
            raise ValueError("INVALID_WORKING_STEP")
        brought = raw["brought_down_digit"]
        normalized.append(
            {
                "step_index": _integer(raw["step_index"], maximum=2),
                "partial_dividend": _integer(raw["partial_dividend"]),
                "quotient_digit": _integer(raw["quotient_digit"], maximum=9),
                "quotient_column": _integer(raw["quotient_column"], maximum=2),
                "partial_product": _integer(raw["partial_product"]),
                "subtraction_result": _integer(raw["subtraction_result"], maximum=9),
                "brought_down_digit": None if brought is None else _integer(brought, maximum=9),
            }
        )
    return normalized


def _trace_error(actual: list[dict[str, int | None]], expected: list[dict[str, int | None]]) -> str:
    if len(actual) != len(expected):
        return "next_digit_not_brought_down"
    fields = (
        ("partial_dividend", "incorrect_quotient_digit"),
        ("quotient_digit", "incorrect_quotient_digit"),
        ("quotient_column", "quotient_digit_wrong_place"),
        ("partial_product", "incorrect_multiplication_fact"),
        ("subtraction_result", "incorrect_subtraction"),
        ("brought_down_digit", "wrong_digit_brought_down"),
    )
    for actual_step, expected_step in zip(actual, expected, strict=True):
        for field, error in fields:
            if actual_step[field] != expected_step[field]:
                if field == "quotient_digit" and expected_step[field] == 0:
                    return "zero_quotient_digit_omitted"
                return error
    return "correct"


def _validate_written(game: Mapping[str, object], response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    keys = {
        "kind", "dividend", "divisor", "working_steps", "quotient_digits",
        "partial_dividends", "partial_products", "subtraction_results",
        "brought_down_digits", "final_quotient", "final_remainder",
    }
    _strict(response, keys)
    dividend, divisor = _integer(response["dividend"]), _integer(response["divisor"], 1, 9)
    expected = canonical_long_division(int(game["dividend"]), int(game["divisor"]))
    limit = int(game.get("trace_limit", len(expected)))
    expected = expected[:limit]
    steps = _normalize_steps(response["working_steps"])
    quotient_digits = _integer_list(response["quotient_digits"], maximum=9)
    partial_dividends = _integer_list(response["partial_dividends"])
    partial_products = _integer_list(response["partial_products"])
    subtraction_results = _integer_list(response["subtraction_results"], maximum=9)
    brought_down_digits = _integer_list(response["brought_down_digits"], maximum=9)
    final_quotient = _integer(response["final_quotient"])
    final_remainder = _integer(response["final_remainder"], maximum=9)
    expected_q, expected_r = quotient_and_remainder(int(game["dividend"]), int(game["divisor"]))
    trace_error = _trace_error(steps, expected)
    arrays_match = (
        quotient_digits == [int(step["quotient_digit"]) for step in expected]
        and partial_dividends == [int(step["partial_dividend"]) for step in expected]
        and partial_products == [int(step["partial_product"]) for step in expected]
        and subtraction_results == [int(step["subtraction_result"]) for step in expected]
        and brought_down_digits == [int(step["brought_down_digit"]) for step in expected if step["brought_down_digit"] is not None]
    )
    result_match = (
        (limit < len(canonical_long_division(int(game["dividend"]), int(game["divisor"])))
         and final_quotient == int(expected[-1]["quotient_digit"])
         and final_remainder == int(expected[-1]["subtraction_result"]))
        or (limit == len(canonical_long_division(int(game["dividend"]), int(game["divisor"])))
            and final_quotient == expected_q and final_remainder == expected_r)
    )
    correct = dividend == game["dividend"] and divisor == game["divisor"] and trace_error == "correct" and arrays_match and result_match
    if final_remainder >= divisor:
        error = "invalid_remainder"
    elif dividend != game["dividend"] or divisor != game["divisor"]:
        error = "dividend_divisor_confused"
    elif trace_error != "correct":
        error = trace_error
    elif not arrays_match:
        error = "incorrect_quotient_digit"
    else:
        error = "remainder_treated_as_quotient"
    normalized = {
        "kind": "written_division", "dividend": dividend, "divisor": divisor,
        "working_steps": steps, "quotient_digits": quotient_digits,
        "partial_dividends": partial_dividends, "partial_products": partial_products,
        "subtraction_results": subtraction_results, "brought_down_digits": brought_down_digits,
        "final_quotient": final_quotient, "final_remainder": final_remainder,
        "_feedback_step_index": next(
            (index for index in range(max(len(steps), len(expected))) if index >= len(steps) or index >= len(expected) or steps[index] != expected[index]),
            None,
        ),
    }
    return correct, "correct" if correct else error, normalized


def validate_constructed_response(item: Mapping[str, object] | DivisionItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, DivisionItem) else item["game_data"]
    assert isinstance(game, Mapping)
    kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    if kind == "equal_sharing":
        _strict(response, {"kind", "dividend", "divisor", "group_quantities", "quotient", "remainder"})
        dividend, divisor = _integer(response["dividend"]), _integer(response["divisor"], 1, 9)
        groups = _integer_list(response["group_quantities"])
        quotient, remainder = _integer(response["quotient"]), _integer(response["remainder"], maximum=9)
        expected_q, expected_r = quotient_and_remainder(int(game["dividend"]), int(game["divisor"]))
        correct = dividend == game["dividend"] and divisor == game["divisor"] and groups == [expected_q] * divisor and quotient == expected_q and remainder == expected_r
        error = "unequal_groups" if len(set(groups)) > 1 or sum(groups) != dividend else "incorrect_quotient_digit"
        return correct, "correct" if correct else error, {"kind": kind, "dividend": dividend, "divisor": divisor, "group_quantities": groups, "quotient": quotient, "remainder": remainder}
    if kind == "written_division":
        return _validate_written(game, response)
    _strict(response, {"kind", "problem_id", "dividend", "divisor", "written_working", "quotient", "remainder", "contextual_interpretation"})
    written = response["written_working"]
    if not isinstance(written, Mapping):
        raise TypeError("INVALID_WORKING_TRACE")
    written_response = {"kind": "written_division", **dict(written)}
    written_correct, written_error, normalized_written = _validate_written(game, written_response)
    quotient, remainder = _integer(response["quotient"]), _integer(response["remainder"], maximum=9)
    interpretation = response["contextual_interpretation"]
    if not isinstance(interpretation, str) or len(interpretation) > 64:
        raise ValueError("INVALID_CONTEXTUAL_INTERPRETATION")
    expected_q, expected_r = quotient_and_remainder(int(game["dividend"]), int(game["divisor"]))
    expected_interpretation = f"complete_groups:{expected_q};leftover:{expected_r}"
    correct = written_correct and response["problem_id"] == game["story_id"] and quotient == expected_q and remainder == expected_r and interpretation == expected_interpretation
    error = written_error if not written_correct else "incorrect_contextual_interpretation"
    return correct, "correct" if correct else error, {
        "kind": kind, "problem_id": str(response["problem_id"]),
        "dividend": _integer(response["dividend"]), "divisor": _integer(response["divisor"], 1, 9),
        "written_working": {key: value for key, value in normalized_written.items() if key != "kind"},
        "quotient": quotient, "remainder": remainder, "contextual_interpretation": interpretation,
    }


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    dividend, divisor = int(game["dividend"]), int(game["divisor"])
    quotient, remainder = quotient_and_remainder(dividend, divisor)
    if game["response_kind"] == "equal_sharing":
        return {"kind": "equal_sharing", "dividend": dividend, "divisor": divisor, "group_quantities": [quotient] * divisor, "quotient": quotient, "remainder": remainder}
    steps = canonical_long_division(dividend, divisor)
    limit = int(game.get("trace_limit", len(steps)))
    visible = steps[:limit]
    written = {
        "dividend": dividend, "divisor": divisor, "working_steps": visible,
        "quotient_digits": [step["quotient_digit"] for step in visible],
        "partial_dividends": [step["partial_dividend"] for step in visible],
        "partial_products": [step["partial_product"] for step in visible],
        "subtraction_results": [step["subtraction_result"] for step in visible],
        "brought_down_digits": [step["brought_down_digit"] for step in visible if step["brought_down_digit"] is not None],
        "final_quotient": quotient if limit == len(steps) else visible[-1]["quotient_digit"],
        "final_remainder": remainder if limit == len(steps) else visible[-1]["subtraction_result"],
    }
    if game["response_kind"] == "written_division":
        return {"kind": "written_division", **written}
    return {
        "kind": "division_story", "problem_id": game["story_id"],
        "dividend": dividend, "divisor": divisor, "written_working": written,
        "quotient": quotient, "remainder": remainder,
        "contextual_interpretation": f"complete_groups:{quotient};leftover:{remainder}",
    }


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else remainder for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del seed
    selected = "visual_guidance" if skill_id == "G5-MAT-DIV-SHARE-01" else "worked_parallel_example"
    return {"selected_action": selected, "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    if game["response_kind"] == "equal_sharing":
        return ["වස්තු එකින් එක කණ්ඩායම් අතර බෙදමු.", "කණ්ඩායම් දෙකේ ගණන සමානද බලමු.", "එක් කණ්ඩායමක ගණන පිළිතුර ලෙස ලියමු."]
    steps = ["බෙදිය යුතු කොටස තෝරන්න.", "බෙදුම කී වරක් ගැළපේද ඉහළින් ලියන්න.", "ගුණිතය යටින් ලියා අඩු කරන්න.", "ඊළඟ ඉලක්කම පහළට ගෙන නැවත කරන්න.", "අවසාන ලබ්ධිය සහ ඉතිරිය පරීක්ෂා කරන්න."]
    if game["response_kind"] == "division_story":
        steps.append("ලබ්ධිය සම්පූර්ණ කූඩ ගණනත් ඉතිරිය ඉතිරි වස්තුත් ලෙස කියන්න.")
    if scaffold_type == "visual_guidance":
        return ["වර්ණයෙන් පෙන්වන ඊළඟ කොටුව බලන්න.", *steps]
    return steps


def package_hash() -> str:
    payload = {"version": PACKAGE_VERSION, "skills": [skill.skill_id for skill in ATOMIC_SKILLS], "misconceptions": MISCONCEPTIONS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

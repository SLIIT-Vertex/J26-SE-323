"""Grade 5 Sinhala Roman-numeral activities for G5-AREA-MAT-16."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-16"
UNIVERSAL_SKILL_ID = "MAT-ROM"
PACKAGE_VERSION = "g5-mat-roman-adventure-v1"
CATALOGUE_VERSION = "g5-mat-roman-misconceptions-v1"
FEATURE_VERSION = "g5-mat-roman-features-v1"
MAPPING_VERSION = "g5-mat-roman-source-mapping-v1"
MODEL_VERSION = "g5-mat-roman-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-roman-deterministic-support-v1"
SCORING_VERSION = "g5-mat-roman-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-roman-parallel-v1"
Chapter = Literal["roman_match", "emoji_count", "roman_arithmetic"]
ROMANS = {
    1: "i",
    2: "ii",
    3: "iii",
    4: "iv",
    5: "v",
    6: "vi",
    7: "vii",
    8: "viii",
    9: "ix",
    10: "x",
    11: "xi",
    12: "xii",
    13: "xiii",
    14: "xiv",
    15: "xv",
    16: "xvi",
    17: "xvii",
    18: "xviii",
    19: "xix",
    20: "xx",
}
EMOJIS = (
    ("flower", "🌸"),
    ("football", "⚽"),
    ("mango", "🥭"),
    ("cherries", "🍒"),
    ("leaf", "🍃"),
    ("pencil", "✏️"),
    ("star", "⭐"),
    ("shell", "🐚"),
)
MISCONCEPTIONS = (
    "confused_i_v_x",
    "v_or_x_counted_as_one",
    "iv_vi_reversed",
    "ix_xi_reversed",
    "noncanonical_additive_form",
    "wrong_match",
    "incomplete_matching",
    "incorrect_emoji_count",
    "duplicate_emoji_count",
    "omitted_emoji",
    "wrong_symbol_order",
    "concatenated_operands",
    "mechanical_symbol_subtraction",
    "incorrect_arithmetic",
    "correct_value_invalid_roman",
    "subtraction_order_reversed",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-MAT-ROMAN-MATCH-01",
        "roman_match",
        "අංකය හා රෝම සංඛ්‍යාව ගළපමු",
        "easy",
        "roman_numeral_match",
    ),
    AtomicSkill(
        "G5-MAT-ROMAN-COUNT-01",
        "emoji_count",
        "රූප ගණන රෝම සංඛ්‍යාවක් කරමු",
        "easy-medium",
        "emoji_quantity_to_roman",
    ),
    AtomicSkill(
        "G5-MAT-ROMAN-ARITHMETIC-01",
        "roman_arithmetic",
        "රෝම සංඛ්‍යා එකතු කර අඩු කරමු",
        "medium-hard",
        "roman_arithmetic",
    ),
)
SKILLS = {s.skill_id: s for s in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class RomanItem:
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


def int_to_roman(value: object) -> str:
    if type(value) is not int or value not in ROMANS:
        raise ValueError("ROMAN_VALUE_OUT_OF_RANGE")
    return ROMANS[value]


def roman_to_int(value: object) -> int:
    if not isinstance(value, str):
        raise TypeError("INVALID_ROMAN_NUMERAL")
    normalized = value.lower()
    result = next((n for n, r in ROMANS.items() if r == normalized), None)
    if result is None:
        raise ValueError("NONCANONICAL_ROMAN_NUMERAL")
    return result


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    return random.Random(
        int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")
    )


def evaluate_roman(left: str, operation: str, right: str) -> int:
    a, b = roman_to_int(left), roman_to_int(right)
    result = a + b if operation == "add" else a - b if operation == "subtract" else 0
    if result not in ROMANS:
        raise ValueError("ROMAN_RESULT_OUT_OF_RANGE")
    return result


def generate_item(skill_id: str, *, role: str, seed: int) -> RomanItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("ROMAN_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "roman_numeral_match":
        values = rng.sample(range(1, 21), 5)
        romans = [ROMANS[v] for v in values]
        rng.shuffle(romans)
        game = {
            "response_kind": skill.response_kind,
            "round_id": f"roman-{seed % 10000}-{role}",
            "arabic_values": values,
            "roman_tiles": romans,
        }
        prompt = "අංකය එහි නිවැරදි රෝම සංඛ්‍යාවට ගළපන්න."
    elif skill.response_kind == "emoji_quantity_to_roman":
        quantity = rng.randint(2, 10)
        emoji_id, symbol = rng.choice(EMOJIS)
        game = {
            "response_kind": skill.response_kind,
            "group_id": f"emoji-{seed % 10000}-{role}",
            "emoji_id": emoji_id,
            "emoji_symbol": symbol,
            "quantity": quantity,
        }
        prompt = "ඉමෝජි එකින් එක ගණන් කර රෝම සංඛ්‍යාව ගොඩනඟන්න."
    else:
        examples = (
            (5, "add", 5),
            (1, "add", 4),
            (3, "add", 2),
            (7, "add", 2),
            (4, "add", 4),
            (7, "subtract", 4),
            (10, "subtract", 5),
            (11, "subtract", 3),
            (6, "subtract", 5),
            (14, "add", 5),
        )
        left, operation, right = rng.choice(examples)
        game = {
            "response_kind": skill.response_kind,
            "problem_id": f"calc-{left}-{operation}-{right}-{role}",
            "left_roman": ROMANS[left],
            "operation": operation,
            "right_roman": ROMANS[right],
        }
        prompt = "රෝම සංඛ්‍යා ගැටලුව විසඳා පිළිතුර ගොඩනඟන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return RomanItem(
        f"{skill_id}:{role}",
        revision,
        f"{skill_id}:parallel-v1",
        skill_id,
        skill.chapter,
        role,
        prompt,
        (),
        "constructed-response",
        {},
        game,
    )


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "roman_numeral_match":
        values = [int(v) for v in game["arabic_values"]]  # type: ignore[union-attr]
        return {
            "kind": kind,
            "round_id": str(game["round_id"]),
            "matches": [{"arabic_value": v, "selected_roman": ROMANS[v]} for v in values],
            "interaction_trace": [f"match:{v}:{ROMANS[v]}" for v in values],
            "revisions": 0,
        }
    if kind == "emoji_quantity_to_roman":
        q = int(game["quantity"])
        roman = ROMANS[q]
        return {
            "kind": kind,
            "group_id": str(game["group_id"]),
            "emoji_id": str(game["emoji_id"]),
            "quantity": q,
            "counted_indices": list(range(q)),
            "constructed_symbols": list(roman),
            "final_roman": roman,
            "interaction_trace": [
                *[f"count:{i}" for i in range(q)],
                *[f"symbol:{s}" for s in roman],
            ],
            "revisions": 0,
        }
    result = evaluate_roman(
        str(game["left_roman"]), str(game["operation"]), str(game["right_roman"])
    )
    roman = ROMANS[result]
    return {
        "kind": kind,
        "problem_id": str(game["problem_id"]),
        "left_roman": str(game["left_roman"]),
        "operation": str(game["operation"]),
        "right_roman": str(game["right_roman"]),
        "left_value_work": roman_to_int(game["left_roman"]),
        "right_value_work": roman_to_int(game["right_roman"]),
        "constructed_result_symbols": list(roman),
        "final_roman": roman,
        "final_value": result,
        "interaction_trace": [
            f"left:{game['left_roman']}",
            f"right:{game['right_roman']}",
            *[f"symbol:{s}" for s in roman],
        ],
        "revisions": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | RomanItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, RomanItem) else item["game_data"]
    assert isinstance(game, Mapping)
    expected = correct_response(game)
    kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    if set(response) != set(expected):
        raise ValueError("MALFORMED_ROMAN_RESPONSE")
    normalized = dict(response)
    for key in ("interaction_trace",):
        if not isinstance(response.get(key), list) or not all(
            isinstance(x, str) for x in response[key]
        ):
            raise ValueError("INVALID_ROMAN_TRACE")  # type: ignore[index]
    if kind == "roman_numeral_match":
        matches = response.get("matches")
        if not isinstance(matches, list) or len(matches) != len(expected["matches"]):
            raise ValueError("INVALID_ROMAN_MATCH")
        first = next(
            (
                row
                for i, row in enumerate(matches)
                if not isinstance(row, Mapping) or row != expected["matches"][i]
            ),
            None,
        )  # type: ignore[index]
        normalized["_feedback_column"] = (
            f"match-{first.get('arabic_value')}" if isinstance(first, Mapping) else "matches"
        )
        correct = first is None
        wrong = str(first.get("selected_roman", "")) if isinstance(first, Mapping) else ""
        value = int(first.get("arabic_value", 0)) if isinstance(first, Mapping) else 0
        error = (
            "iv_vi_reversed"
            if (value, wrong) in ((4, "vi"), (6, "iv"))
            else "ix_xi_reversed"
            if (value, wrong) in ((9, "xi"), (11, "ix"))
            else "wrong_match"
        )
        return correct, "correct" if correct else error, normalized
    if kind == "emoji_quantity_to_roman":
        indices = response.get("counted_indices")
        symbols = response.get("constructed_symbols")
        if (
            not isinstance(indices, list)
            or not all(type(i) is int for i in indices)
            or not isinstance(symbols, list)
            or not all(s in {"i", "v", "x"} for s in symbols)
        ):
            raise ValueError("INVALID_EMOJI_ROMAN_RESPONSE")
        normalized["_feedback_column"] = (
            "emoji-count" if len(set(indices)) != int(game["quantity"]) else "roman-symbols"
        )
        if len(indices) != len(set(indices)):
            error = "duplicate_emoji_count"
        elif set(indices) != set(range(int(game["quantity"]))):
            error = "incorrect_emoji_count"
        elif "".join(symbols) != expected["final_roman"]:
            error = "wrong_symbol_order"
        else:
            error = "correct"
        correct = (
            error == "correct"
            and response.get("final_roman") == expected["final_roman"]
            and response.get("quantity") == game["quantity"]
        )
        return correct, "correct" if correct else error, normalized
    symbols = response.get("constructed_result_symbols")
    if not isinstance(symbols, list) or not all(s in {"i", "v", "x"} for s in symbols):
        raise ValueError("INVALID_ROMAN_ARITHMETIC")
    built = "".join(symbols)
    normalized["_feedback_column"] = "result-symbols"
    if (
        response.get("left_value_work") != expected["left_value_work"]
        or response.get("right_value_work") != expected["right_value_work"]
    ):
        error = "incorrect_arithmetic"
    elif built != expected["final_roman"]:
        error = (
            "iv_vi_reversed"
            if {built, expected["final_roman"]} == {"iv", "vi"}
            else "ix_xi_reversed"
            if {built, expected["final_roman"]} == {"ix", "xi"}
            else "correct_value_invalid_roman"
        )
    elif response.get("final_value") != expected["final_value"]:
        error = "incorrect_arithmetic"
    else:
        error = "correct"
    return error == "correct", error, normalized


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8
) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    other = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {m: confidence if m == primary else other for m in MISCONCEPTIONS}
    return {
        "probabilities": probabilities,
        "predicted_label": primary,
        "confidence": probabilities[primary],
        "fallback_used": sparse,
    }


def scaffold_decision(
    skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int
) -> dict[str, object]:
    del skill_id, seed
    return {
        "selected_action": "visual_guidance",
        "condition": condition,
        "propensity": 1.0,
        "policy_version": POLICY_VERSION,
        "eligible_actions": list(SCAFFOLDS),
        "belief_label": belief.get("predicted_label"),
    }


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    kind = str(game["response_kind"])
    if scaffold_type == "visual_guidance":
        return {
            "roman_numeral_match": ["i, v, x යන මූලික සංකේතය බලන්න."],
            "emoji_quantity_to_roman": ["තවම ගණන් නොකළ ඉමෝජිය බලන්න."],
            "roman_arithmetic": ["පළමු රෝම සංඛ්‍යාවේ අගය බලන්න."],
        }[kind]
    if kind == "roman_numeral_match":
        return ["අංකයේ අගය බලමු.", "i, v, x වලින් කොටස් කරමු.", "නිවැරදි අනුපිළිවෙළින් රෝම සංඛ්‍යාව ගොඩනඟමු."]
    if kind == "emoji_quantity_to_roman":
        return ["ඉමෝජි එකින් එක ගණන් කරමු.", "ගණන සඳහා අවශ්‍ය i, v, x තෝරමු.", "සංකේත නිවැරදි අනුපිළිවෙළට තබමු."]
    return [
        "වම් රෝම සංඛ්‍යාවේ අගය සොයමු.",
        "දකුණු රෝම සංඛ්‍යාවේ අගය සොයමු.",
        "එකතු කිරීම හෝ අඩු කිරීම කරමු.",
        "පිළිතුර නැවත රෝම සංඛ්‍යාවක් කරමු.",
    ]


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "area": AREA_ID,
                "version": PACKAGE_VERSION,
                "skills": [s.skill_id for s in ATOMIC_SKILLS],
                "romans": ROMANS,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

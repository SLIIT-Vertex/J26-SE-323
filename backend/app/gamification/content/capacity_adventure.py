"""Grade 5 capacity activities using exact integer millilitres."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-11"
UNIVERSAL_SKILL_ID = "MAT-MAS"
PACKAGE_VERSION = "g5-mat-capacity-adventure-v1"
CATALOGUE_VERSION = "g5-mat-capacity-misconceptions-v1"
FEATURE_VERSION = "g5-mat-capacity-features-v1"
MAPPING_VERSION = "g5-mat-capacity-source-mapping-v1"
MODEL_VERSION = "g5-mat-capacity-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-capacity-deterministic-support-v1"
SCORING_VERSION = "g5-mat-capacity-trace-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-capacity-parallel-v1"
Chapter = Literal["water_laboratory", "litre_machine", "water_delivery"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-CAPACITY-READ-01", "water_laboratory", "දියර මට්ටම කියවමු", "easy", "vessel_reading"),
    AtomicSkill("G5-MAT-CAPACITY-COMPOSE-01", "water_laboratory", "ලීටර් එකක් සාදමු", "easy_medium", "capacity_composition"),
    AtomicSkill("G5-MAT-CAPACITY-CONVERT-01", "litre_machine", "ලීටර්–මිලිලීටර් මාරු කරමු", "medium", "capacity_conversion"),
    AtomicSkill("G5-MAT-CAPACITY-ARITHMETIC-01", "litre_machine", "ධාරිතාව ගණනය කරමු", "medium_hard", "capacity_arithmetic"),
    AtomicSkill("G5-MAT-CAPACITY-PROBLEM-01", "water_delivery", "ජල බෙදාහැරීමේ මෙහෙයුම", "hard", "capacity_delivery"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
PORTIONS = (100, 200, 250, 500, 1000)
MISCONCEPTIONS = (
    "incorrect_scale_reading", "counted_labels_not_intervals", "reversed_scale_direction",
    "confused_ml_l", "thousand_ml_as_hundred", "incorrect_portion_total", "overflowed_target",
    "assumed_single_composition", "reversed_conversion_direction", "incorrect_remainder_ml",
    "litre_ml_columns_reversed", "misaligned_compound_values", "failed_to_regroup",
    "regrouped_without_removing_ml", "subtracted_without_borrowing", "borrowed_incorrect_ml",
    "litre_column_not_reduced", "correct_result_invalid_working", "incorrect_delivery_interpretation",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class CapacityItem:
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


def _integer(value: object, maximum: int = 10_000_000) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("CAPACITY_VALUE_OUT_OF_RANGE")
    return value


def total_millilitres(litres: int, millilitres: int) -> int:
    _integer(litres); _integer(millilitres)
    return litres * 1000 + millilitres


def split_capacity(total_ml: int) -> tuple[int, int]:
    _integer(total_ml)
    return divmod(total_ml, 1000)


def normalize_capacity(litres: int, millilitres: int) -> tuple[int, int]:
    return split_capacity(total_millilitres(litres, millilitres))


def format_capacity(total_ml: int) -> str:
    litres, millilitres = split_capacity(total_ml)
    return f"{litres} l {millilitres:03d} ml"


def valid_graduation(value: int) -> bool:
    return type(value) is int and 100 <= value <= 1000 and value % 100 == 0


def composition_total(portions: list[int]) -> int:
    if not all(type(value) is int and value in PORTIONS for value in portions):
        raise ValueError("INVALID_CAPACITY_PORTION")
    return sum(portions)


def canonical_arithmetic(
    operation: str,
    left_litres: int,
    left_ml: int,
    right_litres: int,
    right_ml: int,
) -> dict[str, object]:
    for value in (left_litres, left_ml, right_litres, right_ml): _integer(value)
    left = total_millilitres(left_litres, left_ml)
    right = total_millilitres(right_litres, right_ml)
    if operation == "add":
        ml_work = left_ml + right_ml
        exchanged = ml_work // 1000
        result_ml = ml_work % 1000
        result_litres = left_litres + right_litres + exchanged
        steps = [
            f"ml:{left_ml}+{right_ml}={ml_work}", f"carry:{exchanged}",
            f"ml-result:{result_ml}", f"litres:{left_litres}+{right_litres}+{exchanged}={result_litres}",
        ]
    elif operation == "subtract":
        if left < right: raise ValueError("NEGATIVE_CAPACITY")
        exchanged = 1 if left_ml < right_ml else 0
        adjusted_litres = left_litres - exchanged
        adjusted_ml = left_ml + 1000 * exchanged
        ml_work = adjusted_ml
        result_ml = adjusted_ml - right_ml
        result_litres = adjusted_litres - right_litres
        steps = [
            f"borrow:{exchanged}",
            f"adjust:{left_litres}->{adjusted_litres}:{left_ml}->{adjusted_ml}",
            f"ml:{adjusted_ml}-{right_ml}={result_ml}",
            f"litres:{adjusted_litres}-{right_litres}={result_litres}",
        ]
    else: raise ValueError("INVALID_CAPACITY_OPERATION")
    return {
        "operation": operation,
        "left_litres": left_litres, "left_millilitres": left_ml,
        "right_litres": right_litres, "right_millilitres": right_ml,
        "millilitre_subtotal_or_adjustment": ml_work,
        "carried_or_borrowed_litres": exchanged,
        "exchange_used": exchanged > 0,
        "working_steps": steps,
        "result_litres": result_litres, "result_millilitres": result_ml,
    }


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate_item(skill_id: str, *, role: str, seed: int) -> CapacityItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("CAPACITY_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "vessel_reading":
        target = rng.choice((300, 600, 800, 900))
        start = rng.choice(tuple(value for value in range(100, 1001, 100) if value != target))
        game: dict[str, object] = {"capacity_ml": target, "start_level_ml": start, "tick_interval_ml": 100}
        prompt = f"දියර මට්ටම {target} ml සලකුණට සකස් කර අගය තහවුරු කරන්න."
    elif skill.response_kind == "capacity_composition":
        game = {"target_ml": 1000, "available_portions_ml": list(PORTIONS)}
        prompt = "විවිධ කොටස් භාවිතයෙන් ලීටර් එකක් සාදන්න."
    elif skill.response_kind == "capacity_conversion":
        source = rng.choice((2350, 2750, 4300, 5600))
        source_l, source_ml = (0, source) if rng.choice((True, False)) else split_capacity(source)
        game = {"source_litres": source_l, "source_millilitres": source_ml, "source_total_ml": source}
        prompt = f"{source_l} l {source_ml} ml ලීටර් සහ ඉතිරි මිලිලීටර් ලෙස මාරු කරන්න."
    elif skill.response_kind == "capacity_arithmetic":
        operation = rng.choice(("add", "subtract"))
        if operation == "add": pairs = ((8, 250, 4, 750), (3, 650, 2, 700))
        else: pairs = ((14, 600, 5, 750), (9, 200, 3, 650))
        left_l, left_ml, right_l, right_ml = rng.choice(pairs)
        game = {"operation": operation, "left_litres": left_l, "left_millilitres": left_ml, "right_litres": right_l, "right_millilitres": right_ml}
        prompt = f"{left_l} l {left_ml:03d} ml {('සහ' if operation == 'add' else 'න්')} {right_l} l {right_ml:03d} ml {('එකතු කරන්න.' if operation == 'add' else 'අඩු කරන්න.')}"
    else:
        request = rng.choice((2250, 2750, 3500))
        game = {"mission_id": f"delivery-{request}", "requested_total_ml": request, "available_containers_ml": [100, 250, 500, 1000], "source_total_ml": 5000}
        prompt = f"ගමනාන්තයට {format_capacity(request)} නිවැරදිව බෙදාහරින්න."
    game["response_kind"] = skill.response_kind
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return CapacityItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)


def _canonical_portions(target: int, available: list[int]) -> list[int]:
    remaining, result = target, []
    for portion in sorted(available, reverse=True):
        while portion <= remaining:
            result.append(portion); remaining -= portion
    if remaining: raise ValueError("IMPOSSIBLE_CAPACITY_TARGET")
    return result


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "vessel_reading":
        target, start = int(game["capacity_ml"]), int(game["start_level_ml"])
        step = 100 if target > start else -100
        actions = list(range(start + step, target + step, step))
        return {"kind": kind, "capacity_ml": target, "selected_tick_ml": target, "liquid_level_ml": target, "adjustment_actions": actions}
    if kind == "capacity_composition":
        target = int(game["target_ml"]); selected = _canonical_portions(target, [int(v) for v in game["available_portions_ml"]])  # type: ignore[index]
        counts = {str(value): selected.count(value) for value in sorted(set(selected))}
        return {"kind": kind, "target_ml": target, "selected_portions_ml": selected, "portion_counts": counts, "constructed_total_ml": target, "overflow_ml": 0}
    if kind == "capacity_conversion":
        total = int(game["source_total_ml"]); litres, millilitres = split_capacity(total)
        return {"kind": kind, "source_litres": int(game["source_litres"]), "source_millilitres": int(game["source_millilitres"]), "source_total_ml": total, "result_litres": litres, "result_millilitres": millilitres, "exchange_count": litres}
    if kind == "capacity_arithmetic":
        return {"kind": kind, **canonical_arithmetic(str(game["operation"]), int(game["left_litres"]), int(game["left_millilitres"]), int(game["right_litres"]), int(game["right_millilitres"]))}
    request = int(game["requested_total_ml"]); available = [int(v) for v in game["available_containers_ml"]]  # type: ignore[index]
    selected = _canonical_portions(request, available); litres, millilitres = split_capacity(request)
    return {"kind": kind, "mission_id": str(game["mission_id"]), "requested_total_ml": request, "selected_containers_ml": selected, "delivered_total_ml": request, "working_steps": [f"portion:{value}" for value in selected] + [f"total:{request}", f"convert:{request}={litres}:{millilitres}"], "result_litres": litres, "result_millilitres": millilitres, "remaining_or_overflow_ml": 0, "contextual_answer": f"delivered:{request}"}


def _strict(response: Mapping[str, object], expected: Mapping[str, object]) -> None:
    if set(response) != set(expected): raise ValueError("MALFORMED_CAPACITY_RESPONSE")


def validate_constructed_response(item: Mapping[str, object] | CapacityItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, CapacityItem) else item["game_data"]
    assert isinstance(game, Mapping)
    expected = correct_response(game); kind = str(game["response_kind"])
    if response.get("kind") != kind: raise ValueError("WRONG_RESPONSE_KIND")
    _strict(response, expected); normalized = dict(response); focus = "scale"
    if kind == "vessel_reading":
        for key in ("capacity_ml", "selected_tick_ml", "liquid_level_ml"): _integer(response[key], 1000)
        if not valid_graduation(int(response["selected_tick_ml"])): raise ValueError("INVALID_GRADUATION")
        actions = response.get("adjustment_actions")
        if not isinstance(actions, list) or not all(valid_graduation(value) for value in actions): raise ValueError("INVALID_ADJUSTMENT_TRACE")
        target = int(game["capacity_ml"])
        correct = response.get("capacity_ml") == target and response.get("selected_tick_ml") == target and response.get("liquid_level_ml") == target and bool(actions) and actions[-1] == target
        normalized["_feedback_column"] = "scale"
        return correct, "correct" if correct else "incorrect_scale_reading", normalized
    elif kind == "capacity_composition":
        selected = response.get("selected_portions_ml")
        if not isinstance(selected, list): raise ValueError("INVALID_CAPACITY_PORTIONS")
        selected = [int(value) for value in selected]; total = composition_total(selected)
        counts = {str(value): selected.count(value) for value in sorted(set(selected))}
        overflow = max(0, total - int(game["target_ml"]))
        normalized = {**normalized, "portion_counts": counts, "constructed_total_ml": total, "overflow_ml": overflow}
        correct = response.get("target_ml") == game["target_ml"] and response.get("portion_counts") == counts and response.get("constructed_total_ml") == total == game["target_ml"] and response.get("overflow_ml") == overflow == 0
        normalized["_feedback_column"] = "total"
        return correct, "correct" if correct else ("overflowed_target" if overflow else "incorrect_portion_total"), normalized
    elif kind == "capacity_conversion":
        error = "incorrect_remainder_ml"; focus = "conversion"
    elif kind == "capacity_arithmetic":
        if response.get("exchange_used") != expected["exchange_used"]: error = "failed_to_regroup" if game["operation"] == "add" else "subtracted_without_borrowing"
        elif response.get("carried_or_borrowed_litres") != expected["carried_or_borrowed_litres"]: error = "thousand_ml_as_hundred" if game["operation"] == "add" else "borrowed_incorrect_ml"
        elif response.get("millilitre_subtotal_or_adjustment") != expected["millilitre_subtotal_or_adjustment"]: error = "regrouped_without_removing_ml" if game["operation"] == "add" else "borrowed_incorrect_ml"
        elif response.get("result_litres") != expected["result_litres"]: error = "litre_column_not_reduced" if game["operation"] == "subtract" else "misaligned_compound_values"; focus = "litres"
        elif response.get("working_steps") != expected["working_steps"]: error = "correct_result_invalid_working"
        else: error = "misaligned_compound_values"
        focus = focus if focus == "litres" else "millilitres"
    else:
        selected = response.get("selected_containers_ml")
        if not isinstance(selected, list): raise ValueError("INVALID_DELIVERY_CONTAINERS")
        selected = [int(value) for value in selected]
        available = {int(value) for value in game["available_containers_ml"]}  # type: ignore[index]
        if any(value not in available for value in selected): raise ValueError("INVALID_DELIVERY_CONTAINERS")
        total = composition_total(selected)
        requested = int(game["requested_total_ml"]); litres, millilitres = split_capacity(total)
        steps = [f"portion:{value}" for value in selected] + [f"total:{total}", f"convert:{total}={litres}:{millilitres}"]
        normalized = {**normalized, "delivered_total_ml": total, "working_steps": steps, "result_litres": litres, "result_millilitres": millilitres, "remaining_or_overflow_ml": abs(requested - total), "contextual_answer": f"delivered:{total}"}
        correct = response.get("requested_total_ml") == requested and response.get("delivered_total_ml") == total == requested and response.get("working_steps") == steps and response.get("result_litres") == litres and response.get("result_millilitres") == millilitres and response.get("remaining_or_overflow_ml") == 0 and response.get("contextual_answer") == f"delivered:{total}"
        normalized["_feedback_column"] = "delivery"
        error = "overflowed_target" if total > requested else "incorrect_delivery_interpretation"
        return correct, "correct" if correct else error, normalized
    correct = normalized == expected
    normalized["_feedback_column"] = focus
    return correct, "correct" if correct else error, normalized


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = .8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(.72, max(.2, evidence_quality * .72))
    other = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else other for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    kind = str(game["response_kind"])
    if scaffold_type == "visual_guidance":
        return {"vessel_reading": ["අදාළ පරිමාණ කොටස බලන්න."], "capacity_composition": ["ටැංකියේ ඉතිරි හිස් කොටස බලන්න."], "capacity_conversion": ["සම්පූර්ණ 1000 ml කාණ්ඩ බලන්න."], "capacity_arithmetic": ["පළමුව ml තීරුව බලන්න."], "capacity_delivery": ["මූලාශ්‍රය සහ ඉල්ලූ ගමනාන්තය සම්බන්ධ කරන්න."]}[kind]
    if kind == "vessel_reading": return ["පහළ ලකුණු කළ අගයෙන් පටන් ගනිමු.", "එක් පරතරයක් බැගින් ගණන් කරමු.", "දියර මතුපිට ඇති ml අගය පෙන්වමු."]
    if kind == "capacity_composition": return ["එක් කොටසක් වත් කරමු.", "දැනට ඇති එකතුව යාවත්කාලීන කරමු.", "1000 ml සම්පූර්ණ කර 1 l ලෙස පෙන්වමු."]
    if kind == "capacity_conversion": return ["සම්පූර්ණ 1000 ml කාණ්ඩ සාදමු.", "එක් එක් කාණ්ඩය l ටැංකියට මාරු කරමු.", "ඉතිරි ml සහ l පිළිතුර පෙන්වමු."]
    if kind == "capacity_arithmetic": return ["l සහ ml නිවැරදි තීරුවල තබමු.", "ml තීරුව විසඳමු.", "1000 ml ⇄ 1 l හුවමාරුව පෙන්වමු.", "l තීරුව සහ අවසාන පිළිතුර පුරවමු."]
    return ["ඉල්ලූ ධාරිතාව කියවමු.", "සුදුසු කොටස් තෝරමු.", "එකතුව l/ml ලෙස මාරු කරමු.", "නිවැරදි ප්‍රමාණය බෙදාහැරීම සම්පූර්ණ කරමු."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"version": PACKAGE_VERSION, "skills": list(SKILLS), "misconceptions": MISCONCEPTIONS}, sort_keys=True).encode()).hexdigest()

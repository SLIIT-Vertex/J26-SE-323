"""Grade 5 mass activities using exact integer grams."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-12"
UNIVERSAL_SKILL_ID = "MAT-MAS"
PACKAGE_VERSION = "g5-mat-mass-adventure-v1"
CATALOGUE_VERSION = "g5-mat-mass-misconceptions-v1"
FEATURE_VERSION = "g5-mat-mass-features-v1"
MAPPING_VERSION = "g5-mat-mass-source-mapping-v1"
MODEL_VERSION = "g5-mat-mass-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-mass-deterministic-support-v1"
SCORING_VERSION = "g5-mat-mass-trace-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-mass-parallel-v1"
Chapter = Literal["weighing_station", "kilogram_machine", "market_delivery"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-MASS-INSTRUMENT-01", "weighing_station", "නිවැරදි තරාදිය සොයමු", "easy", "mass_instrument"),
    AtomicSkill("G5-MAT-MASS-BALANCE-01", "weighing_station", "තරාදිය සමබර කරමු", "easy_medium", "mass_balance"),
    AtomicSkill("G5-MAT-MASS-CONVERT-01", "kilogram_machine", "කිලෝග්‍රෑම් හා ග්‍රෑම් මාරු කරමු", "medium", "mass_conversion"),
    AtomicSkill("G5-MAT-MASS-ARITHMETIC-01", "kilogram_machine", "බර ගණනය කරමු", "medium_hard", "mass_arithmetic"),
    AtomicSkill("G5-MAT-MASS-PROBLEM-01", "market_delivery", "වෙළඳපොළ බර මෙහෙයුම", "hard", "mass_market_mission"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
STANDARD_MASSES_G = (5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)
INSTRUMENTS = ("two_pan_balance", "spring_balance", "dial_scale", "digital_scale", "platform_scale")
INSTRUMENT_ITEMS = (
    ("hanging-bag", "spring_balance", "hook"),
    ("market-crate", "platform_scale", "platform"),
    ("flour-bowl", "dial_scale", "tray"),
    ("small-parcel", "two_pan_balance", "pan"),
    ("sealed-package", "digital_scale", "platform"),
)
MISCONCEPTIONS = (
    "unsuitable_weighing_instrument", "confused_hook_pan_tray_platform", "confused_g_kg",
    "thousand_g_as_hundred", "incorrect_denomination_value", "incorrect_mass_combination",
    "repeated_balance_overshoot", "reversed_heavier_lighter", "tilted_pan_as_balanced",
    "reversed_conversion_direction", "incorrect_remainder_g", "kg_g_columns_reversed",
    "misaligned_compound_values", "failed_to_regroup", "regrouped_without_removing_g",
    "subtracted_without_borrowing", "borrowed_incorrect_g", "kg_column_not_reduced",
    "correct_result_invalid_working", "incorrect_delivery_interpretation", "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class MassItem:
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
        raise ValueError("MASS_VALUE_OUT_OF_RANGE")
    return value


def total_grams(kilograms: int, grams: int) -> int:
    _integer(kilograms); _integer(grams)
    return kilograms * 1000 + grams


def split_mass(total_g: int) -> tuple[int, int]:
    _integer(total_g)
    return divmod(total_g, 1000)


def normalize_mass(kilograms: int, grams: int) -> tuple[int, int]:
    return split_mass(total_grams(kilograms, grams))


def format_mass(total_g: int) -> str:
    kilograms, grams = split_mass(total_g)
    return f"{kilograms} kg {grams:03d} g"


def mass_total(values: list[int]) -> int:
    if not all(type(value) is int and value in STANDARD_MASSES_G for value in values):
        raise ValueError("INVALID_STANDARD_MASS")
    return sum(values)


def balance_difference(target_g: int, selected_g: list[int]) -> int:
    _integer(target_g)
    return mass_total(selected_g) - target_g


def canonical_arithmetic(operation: str, left_kg: int, left_g: int, right_kg: int, right_g: int) -> dict[str, object]:
    for value in (left_kg, left_g, right_kg, right_g): _integer(value)
    left, right = total_grams(left_kg, left_g), total_grams(right_kg, right_g)
    if operation == "add":
        gram_work = left_g + right_g
        exchanged = gram_work // 1000
        result_g = gram_work % 1000
        result_kg = left_kg + right_kg + exchanged
        steps = [f"g:{left_g}+{right_g}={gram_work}", f"carry:{exchanged}", f"g-result:{result_g}", f"kg:{left_kg}+{right_kg}+{exchanged}={result_kg}"]
    elif operation == "subtract":
        if left < right: raise ValueError("NEGATIVE_MASS")
        exchanged = 1 if left_g < right_g else 0
        adjusted_kg = left_kg - exchanged
        adjusted_g = left_g + 1000 * exchanged
        gram_work = adjusted_g
        result_g = adjusted_g - right_g
        result_kg = adjusted_kg - right_kg
        steps = [f"borrow:{exchanged}", f"adjust:{left_kg}->{adjusted_kg}:{left_g}->{adjusted_g}", f"g:{adjusted_g}-{right_g}={result_g}", f"kg:{adjusted_kg}-{right_kg}={result_kg}"]
    else:
        raise ValueError("INVALID_MASS_OPERATION")
    return {
        "operation": operation, "left_kilograms": left_kg, "left_grams": left_g,
        "right_kilograms": right_kg, "right_grams": right_g,
        "gram_subtotal_or_adjustment": gram_work,
        "carried_or_borrowed_kilograms": exchanged, "exchange_used": exchanged > 0,
        "working_steps": steps, "result_kilograms": result_kg, "result_grams": result_g,
    }


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate_item(skill_id: str, *, role: str, seed: int) -> MassItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("MASS_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "mass_instrument":
        object_id, instrument, placement = rng.choice(INSTRUMENT_ITEMS)
        game: dict[str, object] = {"object_id": object_id, "correct_instrument_type": instrument, "correct_placement": placement, "instrument_types": list(INSTRUMENTS)}
        prompt = "වස්තුව බර කිරීමට සුදුසු තරාදිය වෙත ගෙන යන්න."
    elif skill.response_kind == "mass_balance":
        target = rng.choice((350, 650, 750, 1250, 1500, 2500))
        game = {"target_mass_g": target, "available_masses_g": list(STANDARD_MASSES_G)}
        prompt = "වස්තුවේ බර සොයා ගැනීමට අනෙක් තැටිය සම්මත බරවලින් සමබර කරන්න."
    elif skill.response_kind == "mass_conversion":
        source = rng.choice((2350, 2750, 4300, 5600))
        source_kg, source_g = (0, source) if rng.choice((True, False)) else split_mass(source)
        game = {"source_kilograms": source_kg, "source_grams": source_g, "source_total_g": source}
        prompt = f"{source_kg} kg {source_g} g කිලෝග්‍රෑම් සහ ඉතිරි ග්‍රෑම් ලෙස මාරු කරන්න."
    elif skill.response_kind == "mass_arithmetic":
        operation = rng.choice(("add", "subtract"))
        pairs = ((8, 250, 7, 750), (3, 650, 2, 700)) if operation == "add" else ((14, 600, 5, 750), (9, 200, 3, 650))
        left_kg, left_g, right_kg, right_g = rng.choice(pairs)
        game = {"operation": operation, "left_kilograms": left_kg, "left_grams": left_g, "right_kilograms": right_kg, "right_grams": right_g}
        prompt = f"{left_kg} kg {left_g:03d} g {('සහ' if operation == 'add' else 'න්')} {right_kg} kg {right_g:03d} g {('එකතු කරන්න.' if operation == 'add' else 'අඩු කරන්න.')}"
    else:
        left_g, right_g, capacity_g = rng.choice(((1250, 750, 5000), (2400, 1600, 6000), (1750, 2250, 7000)))
        game = {"mission_id": f"market-{left_g}-{right_g}", "item_ids": ["produce-crate", "delivery-parcel"], "item_masses_g": [left_g, right_g], "available_masses_g": list(STANDARD_MASSES_G), "operation": "add", "cart_capacity_g": capacity_g}
        prompt = "වෙළඳ භාණ්ඩ දෙක බර කර මුළු බර හා රථයේ ඉතිරි ධාරිතාව සොයන්න."
    game["response_kind"] = skill.response_kind
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return MassItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)


def _canonical_masses(target: int) -> list[int]:
    remaining, result = target, []
    for mass in sorted(STANDARD_MASSES_G, reverse=True):
        while mass <= remaining:
            result.append(mass); remaining -= mass
    if remaining: raise ValueError("IMPOSSIBLE_MASS_TARGET")
    return result


def _counts(values: list[int]) -> dict[str, int]:
    return {str(value): values.count(value) for value in sorted(set(values))}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "mass_instrument":
        return {"kind": kind, "object_id": str(game["object_id"]), "instrument_type": str(game["correct_instrument_type"]), "placement": str(game["correct_placement"]), "interaction_trace": [f"place:{game['object_id']}:{game['correct_instrument_type']}:{game['correct_placement']}"]}
    if kind == "mass_balance":
        target = int(game["target_mass_g"]); selected = _canonical_masses(target)
        return {"kind": kind, "target_mass_g": target, "selected_mass_denominations_g": selected, "denomination_counts": _counts(selected), "selected_total_g": target, "balance_difference_g": 0, "balanced": True}
    if kind == "mass_conversion":
        total = int(game["source_total_g"]); kilograms, grams = split_mass(total)
        return {"kind": kind, "source_kilograms": int(game["source_kilograms"]), "source_grams": int(game["source_grams"]), "source_total_g": total, "result_kilograms": kilograms, "result_grams": grams, "exchange_count": kilograms}
    if kind == "mass_arithmetic":
        return {"kind": kind, **canonical_arithmetic(str(game["operation"]), int(game["left_kilograms"]), int(game["left_grams"]), int(game["right_kilograms"]), int(game["right_grams"]))}
    item_masses = [int(value) for value in game["item_masses_g"]]  # type: ignore[index]
    total = sum(item_masses); kilograms, grams = split_mass(total); capacity = int(game["cart_capacity_g"])
    first_kg, first_g = split_mass(item_masses[0]); second_kg, second_g = split_mass(item_masses[1])
    arithmetic = canonical_arithmetic("add", first_kg, first_g, second_kg, second_g)
    selected = _canonical_masses(total)
    return {"kind": kind, "mission_id": str(game["mission_id"]), "selected_items": list(game["item_ids"]), "item_masses_g": item_masses, "selected_standard_masses_g": selected, "operation": "add", "working_steps": arithmetic["working_steps"], "total_mass_g": total, "result_kilograms": kilograms, "result_grams": grams, "remaining_capacity_g": capacity - total, "contextual_answer": f"load:{total}:remaining:{capacity - total}"}


def _strict(response: Mapping[str, object], expected: Mapping[str, object]) -> None:
    if set(response) != set(expected): raise ValueError("MALFORMED_MASS_RESPONSE")


def validate_constructed_response(item: Mapping[str, object] | MassItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, MassItem) else item["game_data"]
    assert isinstance(game, Mapping)
    expected = correct_response(game); kind = str(game["response_kind"])
    if response.get("kind") != kind: raise ValueError("WRONG_RESPONSE_KIND")
    _strict(response, expected); normalized = dict(response)
    if kind == "mass_instrument":
        trace = response.get("interaction_trace")
        if not isinstance(trace, list) or not all(isinstance(value, str) for value in trace): raise ValueError("INVALID_INSTRUMENT_TRACE")
        correct = all(response.get(key) == expected[key] for key in ("object_id", "instrument_type", "placement")) and bool(trace)
        normalized["_feedback_column"] = "instrument"
        return correct, "correct" if correct else ("confused_hook_pan_tray_platform" if response.get("instrument_type") == expected["instrument_type"] else "unsuitable_weighing_instrument"), normalized
    if kind == "mass_balance":
        selected = response.get("selected_mass_denominations_g")
        if not isinstance(selected, list): raise ValueError("INVALID_STANDARD_MASSES")
        selected = [int(value) for value in selected]; total = mass_total(selected); difference = balance_difference(int(game["target_mass_g"]), selected)
        normalized = {**normalized, "denomination_counts": _counts(selected), "selected_total_g": total, "balance_difference_g": difference, "balanced": difference == 0}
        correct = response.get("target_mass_g") == game["target_mass_g"] and response.get("denomination_counts") == _counts(selected) and response.get("selected_total_g") == total and response.get("balance_difference_g") == difference and response.get("balanced") is (difference == 0) and difference == 0
        normalized["_feedback_column"] = "balance"
        return correct, "correct" if correct else ("repeated_balance_overshoot" if difference > 0 else "incorrect_mass_combination"), normalized
    if kind == "mass_conversion":
        error, focus = "incorrect_remainder_g", "conversion"
    elif kind == "mass_arithmetic":
        if response.get("exchange_used") != expected["exchange_used"]: error = "failed_to_regroup" if game["operation"] == "add" else "subtracted_without_borrowing"
        elif response.get("carried_or_borrowed_kilograms") != expected["carried_or_borrowed_kilograms"]: error = "thousand_g_as_hundred" if game["operation"] == "add" else "borrowed_incorrect_g"
        elif response.get("gram_subtotal_or_adjustment") != expected["gram_subtotal_or_adjustment"]: error = "regrouped_without_removing_g" if game["operation"] == "add" else "borrowed_incorrect_g"
        elif response.get("result_kilograms") != expected["result_kilograms"]: error = "kg_column_not_reduced" if game["operation"] == "subtract" else "misaligned_compound_values"
        elif response.get("working_steps") != expected["working_steps"]: error = "correct_result_invalid_working"
        else: error = "misaligned_compound_values"
        focus = "grams" if response.get("result_kilograms") == expected["result_kilograms"] else "kilograms"
    else:
        selected = response.get("selected_standard_masses_g")
        if not isinstance(selected, list): raise ValueError("INVALID_STANDARD_MASSES")
        selected = [int(value) for value in selected]; selected_total = mass_total(selected)
        correct = dict(response) == expected or (all(response.get(key) == expected[key] for key in set(expected) - {"selected_standard_masses_g"}) and selected_total == expected["total_mass_g"])
        normalized["_feedback_column"] = "delivery"
        return correct, "correct" if correct else ("incorrect_mass_combination" if selected_total != expected["total_mass_g"] else "incorrect_delivery_interpretation"), normalized
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
        return {"mass_instrument": ["වස්තුව තැබිය යුතු හුක්ක, තැටිය හෝ වේදිකාව බලන්න."], "mass_balance": ["කුමන තැටිය පහළද බලන්න."], "mass_conversion": ["සම්පූර්ණ 1000 g කාණ්ඩ බලන්න."], "mass_arithmetic": ["පළමුව g තීරුව බලන්න."], "mass_market_mission": ["භාණ්ඩ සහ වගුවේ පේළි සම්බන්ධ කරන්න."]}[kind]
    if kind == "mass_instrument": return ["වස්තුව බලමු.", "එය හුක්කකට, තැටියකට හෝ වේදිකාවකට ගැළපෙනවාද බලමු.", "සුදුසු තරාදිය වෙත වස්තුව ගෙන යමු."]
    if kind == "mass_balance": return ["වස්තුව එක් තැටියක තබමු.", "සම්මත බරක් අනෙක් තැටියට තබමු.", "එකතුව සහ තැටි චලනය බලමු.", "කදම්බය සමතලා වන තෙක් බර සකස් කරමු."]
    if kind == "mass_conversion": return ["සම්පූර්ණ 1000 g කාණ්ඩ සාදමු.", "එක් එක් කාණ්ඩය 1 kg කොටසකට මාරු කරමු.", "ඉතිරි g සහ kg පිළිතුර පෙන්වමු."]
    if kind == "mass_arithmetic": return ["kg සහ g නිවැරදි තීරුවල තබමු.", "g තීරුව විසඳමු.", "1000 g ⇄ 1 kg හුවමාරුව පෙන්වමු.", "kg තීරුව සහ අවසාන පිළිතුර පුරවමු."]
    return ["භාණ්ඩ දෙක බර කරමු.", "අගයන් kg/g වගුවට ගෙන යමු.", "g තීරුව හා හුවමාරුව විසඳමු.", "මුළු බර සහ ඉතිරි ධාරිතාව කියමු."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"version": PACKAGE_VERSION, "skills": list(SKILLS), "misconceptions": MISCONCEPTIONS}, sort_keys=True).encode()).hexdigest()

"""Grade 5 Sinhala tenths and decimal activities for G5-AREA-MAT-15."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-15"
UNIVERSAL_SKILL_ID = "MAT-DEC"
PACKAGE_VERSION = "g5-mat-decimal-adventure-v1"
CATALOGUE_VERSION = "g5-mat-decimal-misconceptions-v1"
FEATURE_VERSION = "g5-mat-decimal-features-v1"
MAPPING_VERSION = "g5-mat-decimal-source-mapping-v1"
MODEL_VERSION = "g5-mat-decimal-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-decimal-deterministic-support-v1"
SCORING_VERSION = "g5-mat-decimal-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-decimal-parallel-v1"

Chapter = Literal["decimal_reading_match", "decimal_tenths_shading", "tenths_fraction_to_decimal", "decimal_to_tenths_fraction"]
READINGS = {
    1: "බින්දුවයි දශම එක", 2: "බින්දුවයි දශම දෙක", 3: "බින්දුවයි දශම තුන",
    4: "බින්දුවයි දශම හතර", 5: "බින්දුවයි දශම පහ", 6: "බින්දුවයි දශම හය",
    7: "බින්දුවයි දශම හත", 8: "බින්දුවයි දශම අට", 9: "බින්දුවයි දශම නවය",
}
MISCONCEPTIONS = (
    "decimal_point_ignored", "whole_number_reading", "wrong_sinhala_digit_word", "decimal_readings_reversed",
    "tenths_as_fraction_not_decimal_reading", "incomplete_or_duplicate_matching", "wrong_shaded_count",
    "counted_unshaded_parts", "ten_parts_as_ten_wholes", "duplicate_or_invalid_section", "invalid_interaction_evidence",
    "fixed_zero_changed", "denominator_moved_to_decimal", "multiple_tenths_digits", "zero_before_point_omitted",
    "numerator_before_decimal", "numerator_denominator_reversed", "denominator_hundred", "whole_decimal_as_numerator",
    "denominator_omitted", "whole_digit_as_numerator", "denominator_one", "invalid_fraction_structure", "unknown_or_other",
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
    AtomicSkill("G5-MAT-DECIMAL-READ-01", "decimal_reading_match", "නිවැරදි කියවීම ගළපමු", "easy", "decimal_reading_match"),
    AtomicSkill("G5-MAT-DECIMAL-SHADE-01", "decimal_tenths_shading", "දශමය රූපයෙන් පෙන්වමු", "easy-medium", "decimal_tenths_shading"),
    AtomicSkill("G5-MAT-TENTHS-TO-DECIMAL-01", "tenths_fraction_to_decimal", "භාගයෙන් දශමයට", "medium", "tenths_fraction_to_decimal"),
    AtomicSkill("G5-MAT-DECIMAL-TO-TENTHS-01", "decimal_to_tenths_fraction", "දශමයෙන් භාගයට", "medium-hard", "decimal_to_tenths_fraction"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class DecimalItem:
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


def validate_tenths(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 9:
        raise ValueError("TENTHS_OUT_OF_RANGE")
    return value


def tenths_to_decimal(numerator: object) -> str:
    return f"0.{validate_tenths(numerator)}"


def decimal_to_tenths(value: object) -> tuple[int, int]:
    if not isinstance(value, str) or len(value) != 3 or not value.startswith("0.") or not value[2].isdigit():
        raise ValueError("INVALID_TENTHS_DECIMAL")
    return validate_tenths(int(value[2])), 10


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate_reading_matches(*, seed: int, role: str, count: int = 4) -> tuple[list[int], list[dict[str, str]]]:
    rng = _rng("decimal-reading", role, seed)
    digits = rng.sample(range(1, 10), count)
    readings = [{"reading_id": f"reading-{digit}", "label_si": READINGS[digit]} for digit in digits]
    rng.shuffle(readings)
    return digits, readings


def generate_item(skill_id: str, *, role: str, seed: int) -> DecimalItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("DECIMAL_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "decimal_reading_match":
        digits, readings = generate_reading_matches(seed=seed, role=role)
        game: dict[str, object] = {"response_kind": skill.response_kind, "decimal_tenths": digits, "reading_tiles": readings}
        prompt = "එක් එක් දශමය එහි නිවැරදි සිංහල කියවීමට ගළපන්න."
    elif skill.response_kind == "decimal_tenths_shading":
        tenths = rng.randint(1, 9)
        game = {"response_kind": skill.response_kind, "decimal_tenths": tenths, "representation": rng.choice(("rectangle", "circle")), "total_parts": 10, "accept_any_equal_parts": True}
        prompt = f"0.{tenths} රූපයෙන් පෙන්වීමට සමාන කොටස් පාට කරන්න."
    elif skill.response_kind == "tenths_fraction_to_decimal":
        numerator = rng.randint(1, 9)
        game = {"response_kind": skill.response_kind, "numerator": numerator, "denominator": 10, "fixed_whole_digit": 0}
        prompt = "දහයෙන් කොටසට සමාන දශමය සම්පූර්ණ කරන්න."
    else:
        tenths = rng.randint(1, 9)
        game = {"response_kind": skill.response_kind, "decimal_tenths": tenths, "decimal_value": f"0.{tenths}", "fraction_bar_present": True}
        prompt = "දශමයට සමාන දහයෙන් කොටස සම්පූර්ණ කරන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return DecimalItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "decimal_reading_match":
        digits = game["decimal_tenths"]
        return {"kind": kind, "matches": [{"decimal_tenths": digit, "reading_id": f"reading-{digit}"} for digit in digits], "interaction_trace": [f"match:{digit}:reading-{digit}" for digit in digits], "revisions": 0}  # type: ignore[union-attr]
    if kind == "decimal_tenths_shading":
        tenths = int(game["decimal_tenths"])
        return {"kind": kind, "representation": game["representation"], "decimal_tenths": tenths, "selected_part_indices": list(range(tenths)), "selected_count": tenths, "total_parts": 10, "interaction_trace": [f"toggle:{index}:on" for index in range(tenths)], "revisions": 0}
    if kind == "tenths_fraction_to_decimal":
        numerator = int(game["numerator"])
        return {"kind": kind, "numerator": numerator, "denominator": 10, "fixed_whole_digit": 0, "entered_tenths_digit": numerator, "decimal_value": f"0.{numerator}", "input_trace": [f"tenths:{numerator}"]}
    tenths = int(game["decimal_tenths"])
    return {"kind": kind, "decimal_tenths": tenths, "entered_numerator": tenths, "entered_denominator": 10, "fraction_bar_present": True, "input_order": ["numerator", "denominator"], "input_trace": [f"numerator:{tenths}", "denominator:1", "denominator:10"]}


def _strict(response: Mapping[str, object], keys: set[str]) -> None:
    if set(response) != keys:
        raise ValueError("MALFORMED_DECIMAL_RESPONSE")


def validate_selected_sections(indices: object, *, total_parts: int = 10) -> list[int]:
    if not isinstance(indices, list) or not all(type(index) is int and 0 <= index < total_parts for index in indices) or len(indices) != len(set(indices)):
        raise ValueError("INVALID_TENTHS_SELECTION")
    return sorted(indices)


def validate_constructed_response(item: Mapping[str, object] | DecimalItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, DecimalItem) else item["game_data"]
    assert isinstance(game, Mapping)
    kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    normalized = dict(response)
    if kind == "decimal_reading_match":
        _strict(response, {"kind", "matches", "interaction_trace", "revisions"})
        matches, trace = response["matches"], response["interaction_trace"]
        digits = list(game["decimal_tenths"])  # type: ignore[arg-type]
        if not isinstance(matches, list) or not isinstance(trace, list) or type(response["revisions"]) is not int or not 0 <= response["revisions"] <= 100:
            raise ValueError("INVALID_DECIMAL_MATCH")
        if len(matches) != len(digits) or not all(isinstance(row, Mapping) and set(row) == {"decimal_tenths", "reading_id"} for row in matches) or not all(isinstance(value, str) for value in trace):
            raise ValueError("INVALID_DECIMAL_MATCH")
        match_digits = [row["decimal_tenths"] for row in matches]
        reading_ids = [row["reading_id"] for row in matches]
        if set(match_digits) != set(digits) or len(set(match_digits)) != len(digits) or len(set(reading_ids)) != len(digits):
            return False, "incomplete_or_duplicate_matching", normalized
        first = next((row for row in matches if row["reading_id"] != f"reading-{row['decimal_tenths']}"), None)
        if first is None:
            return True, "correct", normalized
        normalized["_feedback_column"] = f"decimal-{first['decimal_tenths']}"
        reversed_pair = any(other["decimal_tenths"] != first["decimal_tenths"] and other["reading_id"] == f"reading-{first['decimal_tenths']}" for other in matches)
        return False, "decimal_readings_reversed" if reversed_pair else "wrong_sinhala_digit_word", normalized
    if kind == "decimal_tenths_shading":
        _strict(response, {"kind", "representation", "decimal_tenths", "selected_part_indices", "selected_count", "total_parts", "interaction_trace", "revisions"})
        selected = validate_selected_sections(response["selected_part_indices"])
        if response["representation"] != game["representation"] or response["decimal_tenths"] != game["decimal_tenths"] or response["total_parts"] != 10 or response["selected_count"] != len(selected) or not isinstance(response["interaction_trace"], list) or not all(isinstance(value, str) for value in response["interaction_trace"]) or type(response["revisions"]) is not int:
            raise ValueError("INVALID_SHADING_EVIDENCE")
        normalized["selected_part_indices"] = selected
        normalized["_feedback_column"] = "tenths-parts"
        wanted = int(game["decimal_tenths"])
        if len(selected) == wanted:
            return True, "correct", normalized
        error = "counted_unshaded_parts" if len(selected) == 10 - wanted else "wrong_shaded_count"
        return False, error, normalized
    if kind == "tenths_fraction_to_decimal":
        _strict(response, {"kind", "numerator", "denominator", "fixed_whole_digit", "entered_tenths_digit", "decimal_value", "input_trace"})
        if any(type(response[key]) is not int for key in ("numerator", "denominator", "fixed_whole_digit", "entered_tenths_digit")) or not isinstance(response["decimal_value"], str) or not isinstance(response["input_trace"], list):
            raise ValueError("INVALID_DECIMAL_INPUT")
        normalized["_feedback_column"] = "tenths-digit"
        if response["fixed_whole_digit"] != 0: return False, "fixed_zero_changed", normalized
        if response["denominator"] != 10: return False, "denominator_moved_to_decimal", normalized
        if response["numerator"] != game["numerator"]: raise ValueError("STIMULUS_MISMATCH")
        expected = int(game["numerator"])
        correct = response["entered_tenths_digit"] == expected and response["decimal_value"] == f"0.{expected}"
        return correct, "correct" if correct else "multiple_tenths_digits", normalized
    _strict(response, {"kind", "decimal_tenths", "entered_numerator", "entered_denominator", "fraction_bar_present", "input_order", "input_trace"})
    if response["decimal_tenths"] != game["decimal_tenths"] or type(response["entered_numerator"]) is not int or type(response["entered_denominator"]) is not int or response["fraction_bar_present"] is not True or not isinstance(response["input_order"], list) or not isinstance(response["input_trace"], list):
        raise ValueError("INVALID_FRACTION_INPUT")
    normalized["_feedback_column"] = "fraction"
    numerator, denominator, wanted = int(response["entered_numerator"]), int(response["entered_denominator"]), int(game["decimal_tenths"])
    if numerator == 10 and denominator == wanted: error = "numerator_denominator_reversed"
    elif denominator == 100: error = "denominator_hundred"
    elif denominator == 1: error = "denominator_one"
    elif denominator != 10: error = "denominator_omitted"
    elif numerator != wanted: error = "whole_digit_as_numerator" if numerator == 0 else "whole_decimal_as_numerator"
    else: error = "correct"
    return error == "correct", error, normalized


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
        return {
            "decimal_reading_match": ["0 සහ දශම ලකුණ ස්ථිර බවත් අවසාන ඉලක්කම දහයෙන් කොටස කියන බවත් බලන්න."],
            "decimal_tenths_shading": ["සමාන කොටස් දහය ගණන් කර ඊළඟ අඳුරු නොකළ කොටස බලන්න."],
            "tenths_fraction_to_decimal": ["ලවය සහ දශම ලකුණට පසු හිස් කොටුව සසඳන්න."],
            "decimal_to_tenths_fraction": ["දශම ලකුණට පසු ඉලක්කම සහ භාගයේ ලව කොටුව සසඳන්න."],
        }[kind]
    if kind == "decimal_reading_match": return ["පළමුව බින්දුව කියවමු.", "දශම ලකුණ කියවමු.", "අවසාන ඉලක්කම කියවා නිවැරදි පුවරුව ගළපමු."]
    if kind == "decimal_tenths_shading": return ["සමාන කොටස් දහය හඳුනාගනිමු.", "ඉලක්කමට සමාන කොටස් එකින් එක අඳුරු කරමු.", "අඳුරු කළ කොටස් ගණන/10 සහ 0.n සමාන බව බලමු."]
    if kind == "tenths_fraction_to_decimal": return ["ලවය බලමු.", "ස්ථිර 0. ට පසු එකම කොටුවට ලවය ගෙන යමු.", "සම්පූර්ණ දශමය කියවමු."]
    return ["දශම ලකුණට පසු ඉලක්කම ලවයට ගෙන යමු.", "භාග ඉරට පහළින් 10 තබමු.", "n/10 සහ 0.n සමාන බව බලමු."]


def package_hash() -> str:
    payload = {"area_id": AREA_ID, "version": PACKAGE_VERSION, "skills": [skill.skill_id for skill in ATOMIC_SKILLS], "readings": READINGS}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

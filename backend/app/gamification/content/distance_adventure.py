"""Source-linked Grade 5 distance activities with authoritative compound-unit working."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-09"
UNIVERSAL_SKILL_ID = "MAT-LENGTH"
PACKAGE_VERSION = "g5-mat-distance-adventure-v1"
CATALOGUE_VERSION = "g5-mat-distance-misconceptions-v1"
FEATURE_VERSION = "g5-mat-distance-features-v1"
MAPPING_VERSION = "g5-mat-distance-source-mapping-v1"
MODEL_VERSION = "g5-mat-distance-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-distance-deterministic-support-v1"
SCORING_VERSION = "g5-mat-distance-trace-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-distance-parallel-v1"
Chapter = Literal["unit_path", "distance_calculation", "distance_problems"]

@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str; chapter: Chapter; name_si: str; difficulty: str; response_kind: str

ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-LENGTH-RELATION-01", "unit_path", "ඒකක සම්බන්ධය", "easy", "unit_relationship"),
    AtomicSkill("G5-MAT-LENGTH-CONVERT-01", "unit_path", "දුර මාරු කරමු", "easy_medium", "distance_conversion"),
    AtomicSkill("G5-MAT-LENGTH-ADD-01", "distance_calculation", "දුර එකතු කරමු", "medium", "distance_arithmetic"),
    AtomicSkill("G5-MAT-LENGTH-SUBTRACT-01", "distance_calculation", "දුර අඩු කරමු", "medium_hard", "distance_arithmetic"),
    AtomicSkill("G5-MAT-LENGTH-PROBLEM-01", "distance_problems", "දුර කතාව විසඳමු", "hard", "distance_story"),
)
SKILLS = {s.skill_id: s for s in ATOMIC_SKILLS}
MISCONCEPTIONS = (
    "unit_selected_incorrectly", "conversion_direction_reversed", "incorrect_conversion_factor",
    "incorrect_kilometre_grouping", "incorrect_remainder_metres", "missing_zero_padding",
    "misaligned_columns", "kilometres_added_to_metres", "thousand_treated_as_hundred",
    "failed_to_regroup", "subtracted_without_borrowing", "borrowed_only_hundred_metres",
    "kilometre_column_not_reduced", "wrong_story_operation", "correct_result_invalid_working", "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")

@dataclass(frozen=True, slots=True)
class DistanceItem:
    item_id: str; revision_id: str; parallel_family_id: str; skill_id: str; chapter: Chapter
    measurement_role: Literal["unsupported_before", "unsupported_after"]; prompt_si: str
    options: tuple[tuple[str, str], ...]; correct_option_id: str; error_codes: dict[str, str]; game_data: dict[str, object]

def validate_distance(kilometres: object, metres: object) -> tuple[int, int]:
    if type(kilometres) is not int or type(metres) is not int: raise ValueError("DISTANCE_MUST_BE_INTEGER")
    if kilometres < 0 or metres < 0 or kilometres > 999 or metres > 9999: raise ValueError("DISTANCE_OUT_OF_RANGE")
    return kilometres, metres

def split_metres(total_metres: int) -> tuple[int, int]:
    if type(total_metres) is not int or total_metres < 0: raise ValueError("DISTANCE_OUT_OF_RANGE")
    return divmod(total_metres, 1000)

def normalize_distance(kilometres: int, metres: int) -> tuple[int, int]:
    kilometres, metres = validate_distance(kilometres, metres)
    carry, remainder = divmod(metres, 1000)
    return kilometres + carry, remainder

def format_metres_component(metres: int) -> str:
    if type(metres) is not int or not 0 <= metres < 1000: raise ValueError("METRES_COMPONENT_OUT_OF_RANGE")
    return f"{metres:03d}"

def canonical_arithmetic(operation: str, left_km: int, left_m: int, right_km: int, right_m: int) -> dict[str, object]:
    validate_distance(left_km, left_m); validate_distance(right_km, right_m)
    if operation == "add":
        subtotal = left_m + right_m; exchange = subtotal >= 1000; carry = subtotal // 1000
        result_km, result_m = left_km + right_km + carry, subtotal % 1000
        steps = [f"metres:{left_m}+{right_m}={subtotal}", f"regroup:{carry}", f"kilometres:{left_km}+{right_km}+{carry}={result_km}"]
    elif operation == "subtract":
        if left_km * 1000 + left_m < right_km * 1000 + right_m: raise ValueError("NEGATIVE_DISTANCE")
        exchange = left_m < right_m; carry = 1 if exchange else 0
        adjusted_km, adjusted_m = left_km - carry, left_m + 1000 * carry
        subtotal = adjusted_m - right_m; result_km, result_m = adjusted_km - right_km, subtotal
        steps = [f"borrow:{carry}", f"metres:{adjusted_m}-{right_m}={result_m}", f"kilometres:{adjusted_km}-{right_km}={result_km}"]
    else: raise ValueError("INVALID_DISTANCE_OPERATION")
    return {"operation": operation, "metre_subtotal_or_adjustment": subtotal, "exchange_or_regrouping_used": exchange,
            "carried_or_borrowed_kilometres": carry, "result_kilometres": result_km, "result_metres": result_m, "working_steps": steps}

def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big"))

def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> DistanceItem | None:
    """The same distance skill with whole kilometres or no metre exchange.

    The km-to-m relationship chain is a single fixed fact, so it has no smaller form.
    """
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than
    if SKILLS[skill_id].response_kind == "unit_relationship":
        return None
    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(skill_id: str, *, role: str, seed: int, simpler: bool = False) -> DistanceItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}: raise ValueError("DISTANCE_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "unit_relationship":
        prompt = "මීටර්, සෙන්ටිමීටර් සහ කිලෝමීටර් සම්බන්ධය ගොඩනගන්න."
        game = {"relation_id": "metric_bridge", "left_unit": "km", "right_unit": "m", "conversion_factor": 1000}
    elif skill.response_kind == "distance_conversion":
        total = rng.choice((1000, 2000, 3000) if simpler else (2021, 4075, 6308, 8040)); prompt = f"{total} m, km සහ m ලෙස ලියන්න."
        game = {"source_value": total, "source_unit": "m"}
    else:
        operation = "add" if skill.skill_id == "G5-MAT-LENGTH-ADD-01" else "subtract"
        if skill.response_kind == "distance_story": operation = rng.choice(("add", "subtract"))
        if operation == "add": left_km, left_m, right_km, right_m = rng.choice(((3, 650, 2, 475), (4, 725, 1, 390)))
        else: left_km, left_m, right_km, right_m = rng.choice(((8, 125, 3, 460), (7, 210, 2, 545)))
        # The simpler version needs no exchange between metres and kilometres.
        if simpler: left_km, left_m, right_km, right_m = (2, 300, 1, 400) if operation == "add" else (5, 600, 2, 200)
        prompt = (f"{left_km} km {left_m:03d} m සහ {right_km} km {right_m:03d} m " + ("එකතු කරන්න." if operation == "add" else "අඩු කරන්න."))
        game = {"operation": operation, "left_kilometres": left_km, "left_metres": left_m, "right_kilometres": right_km, "right_metres": right_m}
        if skill.response_kind == "distance_story":
            game.update(problem_id="route_distance", context_mode="journey_total" if operation == "add" else "distance_remaining")
            prompt = "සලකුණු කළ දුර දෙක බලන්න. කතාවට ගැළපෙන ක්‍රියාව තෝරා වගුවෙන් විසඳන්න."
    game.update(response_kind=skill.response_kind)
    revision = f"{skill_id}:{role}{':simpler' if simpler else ''}:{seed % 100000}@v1"
    return DistanceItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)

def _strict(response: Mapping[str, object], keys: set[str]) -> None:
    if set(response) != keys: raise ValueError("MALFORMED_DISTANCE_RESPONSE")
def _int(value: object, maximum: int = 99999) -> int:
    if type(value) is not int or not 0 <= value <= maximum: raise ValueError("DISTANCE_VALUE_OUT_OF_RANGE")
    return value

def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "unit_relationship": return {"kind": kind, "left_unit": "km", "right_unit": "m", "conversion_factor": 1000, "placements": ["1 km", "1000 m", "1 m", "100 cm"]}
    if kind == "distance_conversion":
        km, m = split_metres(int(game["source_value"]))
        return {"kind": kind, "source_value": int(game["source_value"]), "source_unit": "m", "kilometres": km, "metres": m, "total_metres": int(game["source_value"]), "formal_metres": format_metres_component(m)}
    working = canonical_arithmetic(str(game["operation"]), int(game["left_kilometres"]), int(game["left_metres"]), int(game["right_kilometres"]), int(game["right_metres"]))
    arithmetic = {"kind": "distance_arithmetic", "left_kilometres": int(game["left_kilometres"]), "left_metres": int(game["left_metres"]), "right_kilometres": int(game["right_kilometres"]), "right_metres": int(game["right_metres"]), **working}
    if kind == "distance_arithmetic": return arithmetic
    return {"kind": kind, "problem_id": str(game["problem_id"]), "operation": working["operation"], "working_steps": arithmetic, "result_kilometres": working["result_kilometres"], "result_metres": working["result_metres"], "contextual_answer": f"{game['context_mode']}:{working['result_kilometres']}:{working['result_metres']}"}

def validate_constructed_response(item: Mapping[str, object] | DistanceItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, DistanceItem) else item["game_data"]; assert isinstance(game, Mapping)
    expected = correct_response(game); kind = str(game["response_kind"])
    if response.get("kind") != kind: raise ValueError("WRONG_RESPONSE_KIND")
    expected_keys = set(expected); _strict(response, expected_keys)
    normalized = dict(response)
    if kind == "unit_relationship":
        if not isinstance(response["placements"], list): raise ValueError("INVALID_PLACEMENTS")
        error = "incorrect_conversion_factor" if response["conversion_factor"] != 1000 else "unit_selected_incorrectly"
        focus = "conversion"
    elif kind == "distance_conversion":
        for key in ("source_value", "kilometres", "metres", "total_metres"): _int(response[key])
        if response["source_unit"] != "m": error = "conversion_direction_reversed"
        elif response["kilometres"] != expected["kilometres"]: error = "incorrect_kilometre_grouping"
        elif response["metres"] != expected["metres"]: error = "incorrect_remainder_metres"
        elif response["formal_metres"] != expected["formal_metres"]: error = "missing_zero_padding"
        else: error = "correct_result_invalid_working"
        focus = "conversion"
    else:
        actual_work = response["working_steps"] if kind == "distance_story" else response
        expected_work = expected["working_steps"] if kind == "distance_story" else expected
        if not isinstance(actual_work, Mapping): raise ValueError("INVALID_DISTANCE_WORKING")
        if actual_work.get("operation") != expected_work.get("operation"): error = "wrong_story_operation" if kind == "distance_story" else "misaligned_columns"
        elif actual_work.get("exchange_or_regrouping_used") != expected_work.get("exchange_or_regrouping_used"):
            error = "failed_to_regroup" if game["operation"] == "add" else "subtracted_without_borrowing"
        elif actual_work.get("carried_or_borrowed_kilometres") != expected_work.get("carried_or_borrowed_kilometres"):
            error = "borrowed_only_hundred_metres" if game["operation"] == "subtract" else "failed_to_regroup"
        elif actual_work.get("metre_subtotal_or_adjustment") != expected_work.get("metre_subtotal_or_adjustment"): error = "incorrect_remainder_metres"
        elif actual_work.get("result_kilometres") != expected_work.get("result_kilometres"): error = "kilometre_column_not_reduced"
        elif actual_work.get("working_steps") != expected_work.get("working_steps"): error = "correct_result_invalid_working"
        else: error = "wrong_story_operation" if kind == "distance_story" else "correct_result_invalid_working"
        focus = "metres" if error not in {"kilometre_column_not_reduced", "misaligned_columns"} else "kilometres"
    correct = normalized == expected
    normalized["_feedback_column"] = focus
    return correct, "correct" if correct else error, normalized

def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = .8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"; confidence = 1 / len(MISCONCEPTIONS) if sparse else min(.72, max(.2, evidence_quality * .72)); other = (1-confidence)/(len(MISCONCEPTIONS)-1)
    probabilities = {name: confidence if name == primary else other for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}

def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}

def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    if game["response_kind"] == "unit_relationship": return ["1 km කොටස 1000 m සමඟ සම්බන්ධ කරන්න.", "1 m කොටස 100 cm සමඟ සම්බන්ධ කරන්න."]
    if game["response_kind"] == "distance_conversion": return ["මීටර් 1000 බැගින් km කණ්ඩායම් කරන්න.", "ඉතිරි m කොටස ඉලක්කම් තුනකින් ලියන්න."]
    return ["km සහ m නිවැරදි තීරුවල තබන්න.", "පළමුව m තීරුව ගණනය කරන්න.", "1000 m නම් 1 km ලෙස හුවමාරු කරන්න.", "km තීරුව ගණනය කර අවසාන පේළිය ලියන්න."]

def package_hash() -> str:
    return hashlib.sha256(json.dumps({"version": PACKAGE_VERSION, "skills": list(SKILLS), "misconceptions": MISCONCEPTIONS}, sort_keys=True).encode()).hexdigest()

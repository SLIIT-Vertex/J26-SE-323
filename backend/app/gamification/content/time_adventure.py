"""Development-only, source-linked time activities for G5-AREA-MAT-07."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-07"
UNIVERSAL_SKILL_ID = "MAT-TIME"
PACKAGE_VERSION = "g5-mat-time-adventure-draft-v1"
CATALOGUE_VERSION = "g5-mat-time-misconceptions-v1"
FEATURE_VERSION = "g5-mat-time-features-v1"
MAPPING_VERSION = "g5-mat-time-source-mapping-v1"
MODEL_VERSION = "g5-mat-time-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-time-deterministic-support-v1"
SCORING_VERSION = "g5-mat-time-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-time-parallel-v1"

Chapter = Literal["time_tools", "twenty_four_hour_mission", "time_journey"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    source_page: int
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-TIME-UNITS-01", "time_tools", "කාල ඒකක යුගල", "easy", 73, "time_unit_match"),
    AtomicSkill("G5-MAT-TIME-ANALOG-01", "time_tools", "ඔරලෝසු අත් සකසමු", "easy", 73, "analog_clock"),
    AtomicSkill("G5-MAT-TIME-24H-01", "twenty_four_hour_mission", "පැය 24 ඔරලෝසුව", "medium", 73, "time_conversion"),
    AtomicSkill("G5-MAT-TIME-ELAPSED-01", "time_journey", "ගමනේ ගත වූ කාලය", "medium", 74, "elapsed_time"),
    AtomicSkill("G5-MAT-TIME-ARITHMETIC-01", "time_journey", "කාල අභියෝගය", "hard", 74, "time_arithmetic"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
MISCONCEPTIONS = (
    "unit_relationship_confused",
    "hour_minute_hands_confused",
    "minute_marks_miscounted",
    "twelve_twenty_four_conversion_error",
    "midday_midnight_confused",
    "start_end_reversed",
    "minutes_treated_as_base_100",
    "regrouping_omitted",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class TimeItem:
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


UNIT_RELATIONSHIPS = (
    (60, "seconds", 1, "minutes"),
    (60, "minutes", 1, "hours"),
    (24, "hours", 1, "days"),
    (7, "days", 1, "weeks"),
    (4, "weeks", 1, "months"),
    (12, "months", 1, "years"),
    (365, "days", 1, "ordinary_years"),
    (366, "days", 1, "leap_years"),
)


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> TimeItem:
    """The same time skill with fewer unit pairs, whole or half hours, or no regrouping."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(skill_id: str, *, role: str, seed: int, simpler: bool = False) -> TimeItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("TIME_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    game: dict[str, object] = {
        "response_kind": skill.response_kind,
        "source_page": skill.source_page,
        "mapping_basis": "photographed_textbook_pages_73_74",
    }
    if skill.response_kind == "time_unit_match":
        indices = rng.sample(range(len(UNIT_RELATIONSHIPS)), 2 if simpler else 4)
        relationships = [UNIT_RELATIONSHIPS[index] for index in indices]
        left_options = [[row[0], row[1]] for row in relationships]
        right_options = [[row[2], row[3]] for row in relationships]
        rng.shuffle(right_options)
        game.update(
            left_options=left_options,
            right_options=right_options,
            correct_matches=[right_options.index([row[2], row[3]]) for row in relationships],
        )
        prompt = "ගැළපෙන කාල ඒකක සම්බන්ධතා සකසන්න."
    elif skill.response_kind == "analog_clock":
        minutes = (0, 30) if simpler else (0, 5, 10, 20, 25, 35, 40, 50, 55)
        hour, minute = rng.randint(1, 12), rng.choice(minutes)
        game.update(target_hour=hour, target_minute=minute)
        prompt = f"ඔරලෝසුව {hour}:{minute:02d} වේලාවට සකසන්න."
    elif skill.response_kind == "time_conversion":
        hour12, minute, period = rng.randint(1, 12), rng.choice((0, 15, 30, 45)), rng.choice(("am", "pm"))
        if simpler:
            # A whole hour in the afternoon: only the hour changes.
            hour12, minute, period = rng.randint(1, 11), 0, "pm"
        game.update(source_hour=hour12, source_minute=minute, period=period)
        prompt = "පෙන්වා ඇති වේලාව පැය 24 ආකාරයට සකසන්න."
    elif skill.response_kind == "elapsed_time":
        start_hour, start_minute = rng.choice((7, 8, 9, 13)), rng.choice((0, 10, 20, 30))
        duration_hours, duration_minutes = rng.choice((1, 2, 3)), rng.choice((10, 20, 30))
        if simpler:
            start_minute, duration_hours, duration_minutes = 0, 1, rng.choice((0, 30))
        end_total = start_hour * 60 + start_minute + duration_hours * 60 + duration_minutes
        game.update(start_hour=start_hour, start_minute=start_minute, end_hour=end_total // 60, end_minute=end_total % 60)
        prompt = "ගමනේ ගත වූ පැය සහ මිනිත්තු සකසන්න."
    else:
        operation = rng.choice(("add", "subtract"))
        # The simpler version keeps the one regroup this skill is about, with smaller times.
        if operation == "add":
            left, right = ((1, 40), (1, 30)) if simpler else ((3, 45), (2, 35))
        else:
            left, right = ((3, 10), (1, 30)) if simpler else ((6, 20), (2, 45))
        game.update(operation=operation, left_hours=left[0], left_minutes=left[1], right_hours=right[0], right_minutes=right[1])
        prompt = "පැය හා මිනිත්තු වගුව භාවිත කර පිළිතුර සකසන්න."
    revision = f"{skill_id}:{role}{':simpler' if simpler else ''}:{seed % 100000}@v1"
    return TimeItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)


def _strict(response: Mapping[str, object], keys: set[str]) -> None:
    if set(response) != keys:
        raise ValueError("MALFORMED_TIME_RESPONSE")


def _integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("TIME_VALUE_OUT_OF_RANGE")
    return value


def _to_24(hour: int, period: str) -> int:
    if period == "am":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def validate_constructed_response(item: Mapping[str, object] | TimeItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, TimeItem) else item["game_data"]
    assert isinstance(game, Mapping)
    kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    if kind == "time_unit_match":
        _strict(response, {"kind", "matches"})
        matches = response["matches"]
        if not isinstance(matches, list) or any(type(value) is not int for value in matches):
            raise ValueError("INVALID_MATCHES")
        expected = list(game["correct_matches"])
        correct = matches == expected
        return correct, "correct" if correct else "unit_relationship_confused", {"kind": kind, "matches": list(matches)}
    if kind == "analog_clock":
        _strict(response, {"kind", "hour", "minute"})
        hour, minute = _integer(response["hour"], 1, 12), _integer(response["minute"], 0, 59)
        correct = hour == game["target_hour"] and minute == game["target_minute"]
        error = "hour_minute_hands_confused" if minute == game["target_hour"] else "minute_marks_miscounted"
        return correct, "correct" if correct else error, {"kind": kind, "hour": hour, "minute": minute}
    if kind == "time_conversion":
        _strict(response, {"kind", "hour24", "minute"})
        hour24, minute = _integer(response["hour24"], 0, 23), _integer(response["minute"], 0, 59)
        expected = _to_24(int(game["source_hour"]), str(game["period"]))
        correct = hour24 == expected and minute == game["source_minute"]
        error = "midday_midnight_confused" if int(game["source_hour"]) == 12 else "twelve_twenty_four_conversion_error"
        return correct, "correct" if correct else error, {"kind": kind, "hour24": hour24, "minute": minute}
    if kind == "elapsed_time":
        _strict(response, {"kind", "hours", "minutes"})
        hours, minutes = _integer(response["hours"], 0, 23), _integer(response["minutes"], 0, 59)
        elapsed = (int(game["end_hour"]) * 60 + int(game["end_minute"])) - (int(game["start_hour"]) * 60 + int(game["start_minute"]))
        correct = hours == elapsed // 60 and minutes == elapsed % 60
        return correct, "correct" if correct else "start_end_reversed", {"kind": kind, "hours": hours, "minutes": minutes}
    _strict(response, {"kind", "hours", "minutes", "regrouped"})
    hours, minutes = _integer(response["hours"], 0, 23), _integer(response["minutes"], 0, 59)
    if game["operation"] == "add":
        total = (int(game["left_hours"]) + int(game["right_hours"])) * 60 + int(game["left_minutes"]) + int(game["right_minutes"])
    else:
        total = (int(game["left_hours"]) * 60 + int(game["left_minutes"])) - (int(game["right_hours"]) * 60 + int(game["right_minutes"]))
    correct = hours == total // 60 and minutes == total % 60 and response["regrouped"] is True
    return correct, "correct" if correct else "regrouping_omitted", {"kind": kind, "hours": hours, "minutes": minutes, "regrouped": response["regrouped"] is True}


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "time_unit_match":
        return {"kind": kind, "matches": list(game["correct_matches"])}
    if kind == "analog_clock":
        return {"kind": kind, "hour": int(game["target_hour"]), "minute": int(game["target_minute"])}
    if kind == "time_conversion":
        return {"kind": kind, "hour24": _to_24(int(game["source_hour"]), str(game["period"])), "minute": int(game["source_minute"])}
    if kind == "elapsed_time":
        elapsed = (int(game["end_hour"]) * 60 + int(game["end_minute"])) - (int(game["start_hour"]) * 60 + int(game["start_minute"]))
        return {"kind": kind, "hours": elapsed // 60, "minutes": elapsed % 60}
    if game["operation"] == "add":
        total = (int(game["left_hours"]) + int(game["right_hours"])) * 60 + int(game["left_minutes"]) + int(game["right_minutes"])
    else:
        total = int(game["left_hours"]) * 60 + int(game["left_minutes"]) - (int(game["right_hours"]) * 60 + int(game["right_minutes"]))
    return {"kind": kind, "hours": total // 60, "minutes": total % 60, "regrouped": True}


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else remainder for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del seed
    selected = "worked_parallel_example" if skill_id == "G5-MAT-TIME-ARITHMETIC-01" else "visual_guidance"
    return {"selected_action": selected, "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def package_hash() -> str:
    payload = {"version": PACKAGE_VERSION, "skills": [[s.skill_id, s.source_page, s.difficulty] for s in ATOMIC_SKILLS], "misconceptions": MISCONCEPTIONS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    kind = game["response_kind"]
    if kind == "time_unit_match":
        return ["කුඩා ඒකකය හඳුනාගන්න.", "එම ඒකක කීයක් විශාල ඒකකයකට සමානද බලන්න.", "ගැළපෙන යුගලය සකසන්න."]
    if kind == "analog_clock":
        return ["මිනිත්තු කටුවේ ලකුණු ගණන් කරන්න.", "මිනිත්තු කටුව සකසන්න.", "පැය කටුව නිවැරදි පැය අතරට සකසන්න."]
    if kind == "time_conversion":
        return ["වේලාව දහවල්ට පෙරද පසුද බලන්න.", "දහවල්ට පසු නම් පැයට 12 එකතු කරන්න.", "මිනිත්තු වෙනස් නොකර පරීක්ෂා කරන්න."]
    if kind == "elapsed_time":
        return ["ආරම්භක වේලාවෙන් සම්පූර්ණ පැය පනින්න.", "ඉතිරි මිනිත්තු පනින්න.", "පැය හා මිනිත්තු එකතු කරන්න."]
    prefix = "මෙය ඔබේ ප්‍රශ්නයේම පියවරයි." if scaffold_type != "visual_guidance" else "මිනිත්තු තීරුව බලන්න."
    return [prefix, "මිනිත්තු 60ක් පැය 1ක් ලෙස හුවමාරු කරන්න.", "පැය සහ මිනිත්තු තීරු වෙන වෙනම ගණනය කරන්න."]

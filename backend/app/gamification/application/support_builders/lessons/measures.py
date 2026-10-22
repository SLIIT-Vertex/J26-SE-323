"""Measurement areas: Time (MAT-07), Distance (MAT-09), Money (MAT-10), Capacity (MAT-11), and
Mass (MAT-12). Distance, money, capacity and mass share one two-unit calculation: the small unit
first, exchanging one big unit when the small one overflows or runs short."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.gamification.application.support_builders.lessons.common import (
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    cents_text,
    int_list,
    num,
)

TIME_AREA_ID = "G5-AREA-MAT-07"
DISTANCE_AREA_ID = "G5-AREA-MAT-09"
MONEY_AREA_ID = "G5-AREA-MAT-10"
CAPACITY_AREA_ID = "G5-AREA-MAT-11"
MASS_AREA_ID = "G5-AREA-MAT-12"

TIME_UNITS_SKILL = "G5-MAT-TIME-UNITS-01"
LENGTH_RELATION_SKILL = "G5-MAT-LENGTH-RELATION-01"
CAPACITY_CONVERT_SKILL = "G5-MAT-CAPACITY-CONVERT-01"
MASS_CONVERT_SKILL = "G5-MAT-MASS-CONVERT-01"
MONEY_COMPOSE_SKILL = "G5-MAT-MONEY-COMPOSE-01"

UNIT_NAMES = {
    "seconds": "තත්පර",
    "minutes": "මිනිත්තු",
    "hours": "පැය",
    "days": "දින",
    "weeks": "සති",
    "months": "මාස",
    "years": "අවුරුදු",
    "ordinary_years": "සාමාන්‍ය අවුරුද්ද",
    "leap_years": "අධික අවුරුද්ද",
}


@dataclass(frozen=True)
class TwoUnits:
    big: str
    small: str
    factor: int
    # Field-name stems in the game data, such as ``kilometres`` and ``metres``.
    big_key: str
    small_key: str
    repair_skill: str


DISTANCE = TwoUnits("km", "m", 1000, "kilometres", "metres", LENGTH_RELATION_SKILL)
CAPACITY = TwoUnits("l", "ml", 1000, "litres", "millilitres", CAPACITY_CONVERT_SKILL)
MASS = TwoUnits("kg", "g", 1000, "kilograms", "grams", MASS_CONVERT_SKILL)
MONEY = TwoUnits("රුපියල්", "සත", 100, "rupees", "cents", MONEY_COMPOSE_SKILL)
TIME = TwoUnits("පැය", "මිනිත්තු", 60, "hours", "minutes", TIME_UNITS_SKILL)


def _amount(units: TwoUnits, big: int, small: int) -> str:
    if units is MONEY:
        return f"රු. {big}.{small:02d}"
    if units is TIME:
        return f"පැය {big} මිනිත්තු {small}"
    return f"{big} {units.big} {small} {units.small}"


def two_unit_working(
    units: TwoUnits, operation: str, left: tuple[int, int], right: tuple[int, int]
) -> tuple[list[str], tuple[int, int], bool]:
    """Working steps, the result, and whether an exchange was needed."""

    (lb, ls), (rb, rs) = left, right
    lines: list[str] = []
    if operation == "add":
        small = ls + rs
        lines.append(f"{units.small} මුලින්: {ls} + {rs} = {small} {units.small}.")
        exchanged = small >= units.factor
        if exchanged:
            lines.append(
                f"{small} {units.small} = {units.factor} {units.small} + {small - units.factor} {units.small}"
                f" = 1 {units.big} {small - units.factor} {units.small} (1 × {units.factor} = {units.factor})."
                f" 1 {units.big} ගෙන යන්න."
            )
            small -= units.factor
        big = lb + rb + (1 if exchanged else 0)
        carried = " + 1" if exchanged else ""
        lines.append(f"{units.big}: {lb} + {rb}{carried} = {big} {units.big}.")
        return lines, (big, small), exchanged
    exchanged = ls < rs
    if exchanged:
        lines.append(
            f"{ls} {units.small} වලින් {rs} {units.small} අඩු කළ නොහැක. 1 {units.big} ක් "
            f"{units.factor} {units.small} ලෙස මාරු කරන්න: {lb} {units.big} → {lb - 1} {units.big}, "
            f"{ls} → {ls + units.factor} {units.small}."
        )
        ls += units.factor
        lb -= 1
    lines.append(f"{units.small}: {ls} − {rs} = {ls - rs} {units.small}.")
    lines.append(f"{units.big}: {lb} − {rb} = {lb - rb} {units.big}.")
    return lines, (lb - rb, ls - rs), exchanged


def _two_unit_lesson(units: TwoUnits, game: Game, operation: str) -> Lesson:
    left = (int(game[f"left_{units.big_key}"]), int(game[f"left_{units.small_key}"]))
    right = (int(game[f"right_{units.big_key}"]), int(game[f"right_{units.small_key}"]))
    lines, result, _ = two_unit_working(units, operation, left, right)
    sign = "+" if operation == "add" else "−"
    return Lesson(
        steps=(
            f"{units.big} එක් තීරුවක, {units.small} තවත් තීරුවක, එක යට එක ලියන්න.",
            *lines,
        ),
        answer=f"{_amount(units, *left)} {sign} {_amount(units, *right)} = {_amount(units, *result)}",
        hints=(f"මතක තබාගන්න: 1 {units.big} = {units.factor} {units.small}.", lines[0]),
        another_view=(
            (f"සියල්ල {units.small} වලට හරවන්න: {left[0] * units.factor + left[1]} {sign} "
            f"{right[0] * units.factor + right[1]} = "
            f"{result[0] * units.factor + result[1]} {units.small}."),
        ),
    )


def _two_unit_diagnose(
    units: TwoUnits, game: Game, operation: str, response: Mapping[str, object]
) -> Diagnosis | None:
    big = as_int(response.get(f"result_{units.big_key}"))
    small = as_int(response.get(f"result_{units.small_key}"))
    if big is None or small is None:
        return None
    left = (int(game[f"left_{units.big_key}"]), int(game[f"left_{units.small_key}"]))
    right = (int(game[f"right_{units.big_key}"]), int(game[f"right_{units.small_key}"]))
    _, (want_big, want_small), exchanged = two_unit_working(units, operation, left, right)
    if (big, small) == (want_big, want_small):
        return None
    you = f"ඔබේ පිළිතුර {_amount(units, big, small)}"
    if operation == "add" and exchanged and small == left[1] + right[1]:
        went = f"{small} {units.small} යනු 1 {units.big} ට වඩා වැඩියි; 1 {units.big} = {units.factor} {units.small} ලෙස මාරු කළ යුතුයි."
    elif operation != "add" and exchanged and small == right[1] - left[1]:
        went = f"ඔබ {right[1]} න් {left[1]} අඩු කළා. 1 {units.big} ක් {units.factor} {units.small} ලෙස ණයට ගත යුතුයි."
    elif exchanged and units.factor != 100 and small in {
        left[1] + 100 - right[1],
        left[1] + right[1] - 100,
    }:
        went = f"1 {units.big} = {units.factor} {units.small} මිස 100 නොවේ."
    elif small == want_small:
        went = f"{units.small} හරි; {units.big} ගණනයේදී මාරු කළ 1 අමතක විය." if exchanged else f"{units.big} ගණනය නැවත බලන්න."
    else:
        went = f"{units.small} ගණනය වැරදුණා; එය {want_small} විය යුතුයි."
    return Diagnosis(you_did=you, went_wrong=went, prerequisite_skill_id=units.repair_skill)


def _greedy(target: int, parts: list[int], unit: str) -> list[str]:
    lines: list[str] = []
    remaining = target
    for part in sorted(parts, reverse=True):
        count = remaining // part
        if count:
            remaining -= count * part
            lines.append(f"{part} {unit} × {count} → ඉතිරි {remaining} {unit}.")
    return lines


def _split(total: int, units: TwoUnits) -> str:
    big, small = divmod(total, units.factor)
    return (
        f"{total} {units.small} = {big} × {units.factor} {units.small} + {small} {units.small}"
        f" = {big} {units.big} {small} {units.small}"
    )


# Time.


def _time(hour: int, minute: int) -> str:
    return f"{hour}:{minute:02d}"


def time_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "time_unit_match":
        lefts = game.get("left_options", [])
        rights = game.get("right_options", [])
        pairs = [
            f"{lefts[index][0]} {UNIT_NAMES.get(lefts[index][1], lefts[index][1])} = "  # type: ignore[index]
            f"{rights[match][0]} {UNIT_NAMES.get(rights[match][1], rights[match][1])}"  # type: ignore[index]
            for index, match in enumerate(int_list(solution.get("matches")))
        ]
        return Lesson(
            steps=tuple(f"{pair}." for pair in pairs),
            answer="; ".join(pairs),
            hints=("පැය 1 = මිනිත්තු 60, සතිය = දින 7, සාමාන්‍ය අවුරුද්ද = දින 365.",),
            another_view=("කුඩා ඒකකය ගණනින් වැඩියි; විශාල ඒකකය 1 යි.",),
        )
    if kind == "analog_clock":
        hour, minute = int(solution["hour"]), int(solution["minute"])
        steps = (
            f"දිග කටුව මිනිත්තු පෙන්වයි: {minute} ÷ 5 = {minute // 5} (පරීක්ෂාව: {minute // 5} × 5 = {minute // 5 * 5}), එබැවින් දිග කටුව {minute // 5 or 12} අංකයට.",
            f"කෙටි කටුව පැය පෙන්වයි: {hour} ට"
            + (f", මිනිත්තු {minute} නිසා {hour} ත් {hour % 12 + 1} ත් අතරට ටිකක් ගමන් කර." if minute else "."),
        )
        return Lesson(
            steps=steps,
            answer=f"වේලාව {_time(hour, minute)}",
            hints=("දිග කටුවේ සෑම අංකයක්ම මිනිත්තු 5 කි.", steps[0]),
            another_view=(f"{_time(hour, minute)} = පැය {hour} පසු වී මිනිත්තු {minute}.",),
        )
    if kind == "time_conversion":
        hour, minute = int(game["source_hour"]), int(game["source_minute"])
        result = int(solution["hour24"])
        afternoon = game.get("period") == "pm"
        if afternoon and hour != 12:
            step = f"ප.ව. වේලාවකට 12 එකතු කරන්න: {hour} + 12 = {result}."
        elif not afternoon and hour == 12:
            step = "මධ්‍යම රාත්‍රී 12 පැය 24 ආකාරයේ 00 වේ."
        else:
            step = f"පෙ.ව. වේලාව එලෙසම තබන්න: {result:02d}."
        return Lesson(
            steps=(f"දී ඇති වේලාව {_time(hour, minute)} {'ප.ව.' if afternoon else 'පෙ.ව.'}", step, "මිනිත්තු වෙනස් නොවේ."),
            answer=f"{result:02d}:{minute:02d}",
            hints=("පස්වරු වේලාවල පැයට 12 එකතු වේ.",),
            another_view=("දවසට පැය 24: මධ්‍යම රාත්‍රියේ 00:00 සිට 23:59 දක්වා ගණන් කරන්න.",),
        )
    if kind == "elapsed_time":
        start = (int(game["start_hour"]), int(game["start_minute"]))
        end = (int(game["end_hour"]), int(game["end_minute"]))
        lines, result, _ = two_unit_working(TIME, "subtract", end, start)
        return Lesson(
            steps=(f"ගත වූ කාලය = අවසන් වේලාව − ආරම්භ වේලාව: {_time(*end)} − {_time(*start)}.", *lines),
            answer=f"ගත වූ කාලය පැය {result[0]} මිනිත්තු {result[1]}",
            hints=("මිනිත්තු මුලින් අඩු කරන්න.", "පැය 1 = මිනිත්තු 60."),
            another_view=(
                (f"{_time(*start)} සිට ඉදිරියට ගණන් කරන්න: පැය {result[0]} කින් {_time(start[0] + result[0], start[1])}, "
                f"තවත් මිනිත්තු {result[1]} කින් {_time(*end)}."),
            ),
        )
    if kind == "time_arithmetic":
        operation = str(game["operation"])
        lesson = _two_unit_lesson(TIME, game, operation)
        return Lesson(
            steps=lesson.steps,
            answer=lesson.answer,
            hints=("පැය 1 = මිනිත්තු 60 (100 නොවේ).", *lesson.hints[1:]),
            another_view=lesson.another_view,
        )
    return None


def time_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "time_arithmetic":
        return _two_unit_diagnose(TIME, game, str(game["operation"]), response)
    if kind == "elapsed_time":
        hours, minutes = as_int(response.get("hours")), as_int(response.get("minutes"))
        if hours is None or minutes is None:
            return None
        if (hours, minutes) == (int(solution["hours"]), int(solution["minutes"])):
            return None
        start_minute, end_minute = int(game["start_minute"]), int(game["end_minute"])
        if end_minute < start_minute and minutes == start_minute - end_minute:
            went = "ඔබ අවසන් මිනිත්තුවලින් ආරම්භ මිනිත්තු අඩු කිරීම වෙනුවට ප්‍රතිවිරුද්ධව අඩු කළා. පැය 1 ක් මිනිත්තු 60 ලෙස මාරු කරන්න."
        else:
            went = f"ගත වූ කාලය පැය {solution['hours']} මිනිත්තු {solution['minutes']} විය යුතුයි."
        return Diagnosis(you_did=f"ඔබේ පිළිතුර පැය {hours} මිනිත්තු {minutes}", went_wrong=went, prerequisite_skill_id=TIME_UNITS_SKILL)
    if kind == "time_conversion":
        given = as_int(response.get("hour24"))
        if given is not None and given != int(solution["hour24"]):
            return Diagnosis(
                you_did=f"ඔබ පැය {given} ලෙස තැබුවා",
                went_wrong="ප.ව. වේලාවකට පැයට 12 එකතු කළ යුතුයි.",
            )
    if kind == "analog_clock":
        hour, minute = as_int(response.get("hour")), as_int(response.get("minute"))
        if hour is not None and minute is not None and minute != int(solution["minute"]) and minute == int(solution["minute"]) // 5:
            return Diagnosis(
                you_did=f"ඔබ දිග කටුව මිනිත්තු {minute} ට තැබුවා",
                went_wrong="දිග කටුවේ සෑම අංකයක්ම මිනිත්තු 5 කි; අංකය 5 න් ගුණ කරන්න.",
            )
    return None


# Distance.


def distance_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "unit_relationship":
        return Lesson(
            steps=("1 km = 1000 m.", "1 m = 100 cm.", "1 cm = 10 mm."),
            answer="1 km = 1000 m; 1 m = 100 cm",
            hints=("'කිලෝ' යනු දහසයි: කිලෝමීටරයක මීටර 1000.",),
            another_view=("පාසල් ධාවන පථයේ වට කිහිපයක් ≈ 1 km; ඔබේ උස ≈ 1 m 30 cm.",),
        )
    if kind == "distance_conversion":
        total = int(solution["total_metres"])
        return Lesson(
            steps=(
                "1 km = 1000 m. මීටරවල දහස් කොටස කිලෝමීටර වේ.",
                _split(total, DISTANCE) + ".",
            ),
            answer=f"{num(total)} m = {solution['kilometres']} km {solution['metres']} m",
            hints=(f"{num(total)} තුළ 1000 කී වරක් තිබේද?",),
            another_view=(f"{num(total)} m = {total / 1000:g} km.",),
        )
    if kind == "distance_arithmetic":
        return _two_unit_lesson(DISTANCE, game, str(game["operation"]))
    if kind == "distance_story":
        operation = str(game["operation"])
        inner = _two_unit_lesson(DISTANCE, game, operation)
        word = "එකතු කිරීම (මුළු දුර)" if operation == "add" else "අඩු කිරීම (ඉතිරි දුර හෝ වෙනස)"
        return Lesson(
            steps=(f"කතාව කියවා ක්‍රියාව තෝරන්න: {word}.", *inner.steps),
            answer=inner.answer,
            hints=(f"මෙම කතාවට අවශ්‍ය ක්‍රියාව: {word}.", *inner.hints),
            another_view=inner.another_view,
        )
    return None


def distance_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "distance_arithmetic":
        return _two_unit_diagnose(DISTANCE, game, str(game["operation"]), response)
    if kind == "distance_story":
        if response.get("operation") not in {None, game.get("operation")}:
            return Diagnosis(
                you_did="ඔබ වෙනත් ක්‍රියාවක් තෝරා ගත්තා",
                went_wrong="කතාවේ ප්‍රශ්නය නැවත කියවන්න: 'ඉතිරි' හෝ 'වෙනස' යනු අඩු කිරීමයි; 'මුළු' යනු එකතු කිරීමයි.",
            )
        working = response.get("working_steps")
        if isinstance(working, Mapping):
            return _two_unit_diagnose(DISTANCE, game, str(game["operation"]), working)
    if kind == "distance_conversion":
        km, m = as_int(response.get("kilometres")), as_int(response.get("metres"))
        if km is not None and m is not None and (km, m) != (int(solution["kilometres"]), int(solution["metres"])):
            return Diagnosis(
                you_did=f"ඔබේ පිළිතුර {km} km {m} m",
                went_wrong="1 km = 1000 m. මීටර ගණන 1000 න් බෙදා km සොයන්න; ඉතිරිය m වේ.",
                prerequisite_skill_id=LENGTH_RELATION_SKILL,
            )
    return None


# Money.


def _money_name(denomination: str) -> str:
    kind, _, value = denomination.partition("-")
    return f"රු. {value} {'කාසිය' if kind == 'coin' else 'නෝට්ටුව'}"


def money_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "currency_recognition":
        placements = sorted(
            solution.get("placements", []),  # type: ignore[arg-type]
            key=lambda row: int(row["ordered_position"]),
        )
        names = [_money_name(str(row["denomination_id"])) for row in placements]
        return Lesson(
            steps=(
                "කාසි සහ නෝට්ටුවල ලියා ඇති අගය කියවන්න.",
                "අගය කුඩාවේ සිට විශාලයට පෙළගස්වන්න: " + " < ".join(names) + ".",
            ),
            answer=" < ".join(names),
            hints=("කාසිවල අගය කුඩායි; නෝට්ටු රු. 20 සිට පටන් ගනී.",),
            another_view=("ප්‍රමාණය නොව, ලියා ඇති අංකය අගය තීරණය කරයි.",),
        )
    if kind == "amount_construction":
        target = int(solution["target_in_cents"])
        counts = {str(key): int(value) for key, value in dict(solution.get("denomination_counts", {})).items()}  # type: ignore[arg-type]
        parts = sorted(counts, key=lambda name: -int(name.partition("-")[2]))
        lines = []
        remaining = target
        for name in parts:
            value = int(name.partition("-")[2]) * 100
            remaining -= value * counts[name]
            lines.append(f"{_money_name(name)} × {counts[name]} → ඉතිරි {cents_text(remaining)}.")
        return Lesson(
            steps=("විශාලතම නෝට්ටුවෙන් පටන් ගන්න; ඉලක්කය ඉක්මවන්න එපා.", *lines),
            answer=" + ".join(f"{_money_name(name)} × {counts[name]}" for name in parts) + f" = {cents_text(target)}",
            hints=("ඉලක්කයට වඩා අඩු විශාලතම නෝට්ටුව මුලින් තබන්න.",),
            another_view=(f"{cents_text(target)} = " + " + ".join(f"{int(name.partition('-')[2]) * counts[name]}" for name in parts) + ".",),
        )
    if kind == "money_arithmetic":
        left, right = int(solution["left_amount_in_cents"]), int(solution["right_amount_in_cents"])
        operation = str(solution["operation"])
        game_like = {
            "left_rupees": left // 100,
            "left_cents": left % 100,
            "right_rupees": right // 100,
            "right_cents": right % 100,
        }
        return _two_unit_lesson(MONEY, game_like, operation)
    if kind == "shopping_calculation":
        names = {
            str(product["product_id"]): str(product["name_si"])  # type: ignore[index]
            for product in game.get("products", [])  # type: ignore[union-attr]
        }
        lines = [
            f"{names.get(str(product), product)}: {cents_text(price)} × {quantity} = {cents_text(line)}."
            for product, quantity, price, line in zip(
                solution.get("selected_products", []),  # type: ignore[arg-type]
                int_list(solution.get("quantities")),
                int_list(solution.get("unit_prices_in_cents")),
                int_list(solution.get("line_totals_in_cents")),
                strict=False,
            )
        ]
        total = int(solution["total_in_cents"])
        paid = int(solution["amount_paid_in_cents"])
        change = int(solution.get("change_in_cents", 0))
        lines.append("මුළු මිල: " + " + ".join(cents_text(value) for value in int_list(solution.get("line_totals_in_cents"))) + f" = {cents_text(total)}.")
        lines.append(f"ඉතිරි මුදල: {cents_text(paid)} − {cents_text(total)} = {cents_text(change)}.")
        return Lesson(
            steps=tuple(lines),
            answer=f"මුළු මිල {cents_text(total)}, ඉතිරි මුදල {cents_text(change)}",
            hints=("සෑම භාණ්ඩයකම මිල × ප්‍රමාණය මුලින් සොයන්න.", lines[0] if lines else ""),
            another_view=("ඉතිරි මුදල = දුන් මුදල − මුළු මිල.",),
        )
    return None


def money_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "money_arithmetic":
        left, right = int(solution["left_amount_in_cents"]), int(solution["right_amount_in_cents"])
        game_like = {
            "left_rupees": left // 100,
            "left_cents": left % 100,
            "right_rupees": right // 100,
            "right_cents": right % 100,
        }
        return _two_unit_diagnose(MONEY, game_like, str(solution["operation"]), response)
    if kind == "amount_construction":
        total = as_int(response.get("constructed_total_in_cents"))
        target = int(solution["target_in_cents"])
        if total is not None and total != target:
            return Diagnosis(
                you_did=f"ඔබ සෑදුවේ {cents_text(total)}",
                went_wrong=("එය ඉලක්කයට වඩා වැඩියි" if total > target else "එය ඉලක්කයට වඩා අඩුයි") + f"; {cents_text(target)} අවශ්‍යයි.",
            )
    if kind == "shopping_calculation":
        lines = int_list(response.get("line_totals_in_cents"))
        wanted = int_list(solution.get("line_totals_in_cents"))
        for index, (given, right) in enumerate(zip(lines, wanted, strict=False)):
            if given != right:
                return Diagnosis(
                    you_did=f"පේළිය {index + 1} සඳහා ඔබේ මිල {cents_text(given)}",
                    went_wrong=f"මිල × ප්‍රමාණය = {cents_text(right)} විය යුතුයි.",
                )
    return None


# Capacity.


def capacity_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "vessel_reading":
        target, tick = int(solution["selected_tick_ml"]), int(game["tick_interval_ml"])
        return Lesson(
            steps=(
                f"භාජනයේ සෑම සලකුණක්ම {tick} ml බැගින් වැඩි වේ.",
                f"පතුලේ සිට සලකුණු ගණන් කරන්න: {', '.join(str(tick * n) for n in range(1, target // tick + 1))}.",
                f"{target} ml සලකුණට දියරය සකසන්න.",
            ),
            answer=f"දියර මට්ටම {target} ml",
            hints=(f"සලකුණු {tick} ml බැගින්.",),
            another_view=(f"{target} ml = {target // tick} × {tick} ml.",),
        )
    if kind in {"capacity_composition", "capacity_delivery"}:
        target = int(solution.get("target_ml") or solution.get("requested_total_ml"))  # type: ignore[arg-type]
        chosen = int_list(solution.get("selected_portions_ml") or solution.get("selected_containers_ml"))
        steps = ["විශාලතම භාජනයෙන් පටන් ගන්න; ඉලක්කය ඉක්මවන්න එපා.", *_greedy(target, chosen, "ml")]
        if kind == "capacity_delivery":
            steps.append(_split(target, CAPACITY) + ".")
        return Lesson(
            steps=tuple(steps),
            answer=" + ".join(f"{value} ml" for value in chosen) + f" = {target} ml",
            hints=("1 l = 1000 ml.", steps[1] if len(steps) > 1 else ""),
            another_view=(_split(target, CAPACITY) + ".",),
        )
    if kind == "capacity_conversion":
        total = int(solution["source_total_ml"])
        return Lesson(
            steps=("1 l = 1000 ml.", _split(total, CAPACITY) + "."),
            answer=f"{solution['result_litres']} l {solution['result_millilitres']} ml",
            hints=(f"{total} ml තුළ 1000 ml කී වරක් තිබේද?",),
            another_view=(f"{total} ml = {total / 1000:g} l.",),
        )
    if kind == "capacity_arithmetic":
        return _two_unit_lesson(CAPACITY, game, str(game["operation"]))
    return None


def capacity_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "capacity_arithmetic":
        return _two_unit_diagnose(CAPACITY, game, str(game["operation"]), response)
    if kind in {"capacity_composition", "capacity_delivery"}:
        total = as_int(response.get("constructed_total_ml") or response.get("delivered_total_ml"))
        target = int(solution.get("target_ml") or solution.get("requested_total_ml"))  # type: ignore[arg-type]
        if total is not None and total != target:
            return Diagnosis(
                you_did=f"ඔබ එකතු කළේ {total} ml",
                went_wrong=("ඉලක්කය ඉක්මවා ගියා" if total > target else "තව අවශ්‍යයි") + f"; ඉලක්කය {target} ml.",
                prerequisite_skill_id=CAPACITY_CONVERT_SKILL,
            )
    return None


# Mass.

INSTRUMENTS = {
    "two_pan_balance": ("තැටි දෙකේ තරාදිය", "සම්මත බර සමඟ සසඳා බර සොයයි"),
    "spring_balance": ("දුනු තරාදිය", "හුක්කේ එල්ලා බර කරයි"),
    "dial_scale": ("කටු තරාදිය", "තැටියේ තබන බඳුන් බර කරයි"),
    "digital_scale": ("ඩිජිටල් තරාදිය", "වේදිකාවේ තැබූ විට බර අංකයෙන් පෙන්වයි"),
    "platform_scale": ("ඉලෙක්ට්‍රොනික වේදිකා තරාදිය", "විශාල, බර දේවල් බර කරයි"),
}
OBJECTS = {
    "hanging-bag": "එල්ලා බර කරන බෑගය",
    "market-crate": "වෙළඳ පෙට්ටිය",
    "flour-bowl": "පිටි බඳුන",
    "small-parcel": "කුඩා පාර්සලය",
    "sealed-package": "මුද්‍රිත පැකේජය",
}


def mass_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "mass_instrument":
        name, why = INSTRUMENTS.get(str(solution["instrument_type"]), (str(solution["instrument_type"]), ""))
        thing = OBJECTS.get(str(solution["object_id"]), str(solution["object_id"]))
        return Lesson(
            steps=(
                f"වස්තුව: {thing}. එය තබන්නේ, එල්ලන්නේ හෝ සසඳන්නේ කෙසේදැයි සිතන්න.",
                f"{name} {why}.",
            ),
            answer=f"{thing} → {name}",
            hints=(f"{thing} තැබිය හැකි හෝ එල්ලිය හැකි කොටස සොයන්න.",),
            another_view=tuple(f"{label}: {reason}." for label, reason in INSTRUMENTS.values()),
        )
    if kind == "mass_balance":
        target = int(solution["target_mass_g"])
        chosen = int_list(solution.get("selected_mass_denominations_g"))
        return Lesson(
            steps=(
                f"වස්තුවේ බර {target} g. අනෙක් තැටියට සම්මත බර දමා සමබර කරන්න.",
                "ඉලක්කයට නොවැඩි විශාලතම බරෙන් පටන් ගන්න.",
                *_greedy(target, chosen, "g"),
            ),
            answer=" + ".join(f"{value} g" for value in chosen) + f" = {target} g",
            hints=("තැටි දෙක එකම උසට ආ විට සමබරයි.",),
            another_view=(f"{target} g = " + " + ".join(map(str, chosen)) + ".",),
        )
    if kind == "mass_conversion":
        total = int(solution["source_total_g"])
        return Lesson(
            steps=("1 kg = 1000 g.", _split(total, MASS) + "."),
            answer=f"{solution['result_kilograms']} kg {solution['result_grams']} g",
            hints=(f"{total} g තුළ 1000 g කී වරක් තිබේද?",),
            another_view=(f"{total} g = {total / 1000:g} kg.",),
        )
    if kind == "mass_arithmetic":
        return _two_unit_lesson(MASS, game, str(game["operation"]))
    if kind == "mass_market_mission":
        masses = int_list(solution.get("item_masses_g"))
        total = int(solution["total_mass_g"])
        capacity = as_int(game.get("cart_capacity_g"))
        remaining = as_int(solution.get("remaining_capacity_g"))
        steps = [
            "භාණ්ඩවල බර: " + ", ".join(f"{value} g" for value in masses) + ".",
            "මුළු බර: " + " + ".join(map(str, masses)) + f" = {total} g = {_split(total, MASS).split(' = ')[-1]}.",
        ]
        if capacity is not None and remaining is not None:
            steps.append(f"රථයේ ඉතිරි ධාරිතාව: {capacity} − {total} = {remaining} g.")
        return Lesson(
            steps=tuple(steps),
            answer=f"මුළු බර {total} g" + (f", ඉතිරි ධාරිතාව {remaining} g" if remaining is not None else ""),
            hints=("මුලින් භාණ්ඩ දෙකේ බර එකතු කරන්න.",),
            another_view=("1000 g = 1 kg: ග්‍රෑම් 1000 සෑම විටම කිලෝග්‍රෑම් 1 කි.",),
        )
    return None


def mass_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "mass_arithmetic":
        return _two_unit_diagnose(MASS, game, str(game["operation"]), response)
    if kind == "mass_instrument" and response.get("instrument_type") not in {None, solution["instrument_type"]}:
        name = INSTRUMENTS.get(str(response["instrument_type"]), ("එම තරාදිය", ""))[0]
        return Diagnosis(
            you_did=f"ඔබ තෝරා ගත්තේ {name}",
            went_wrong="වස්තුව තබන හෝ එල්ලන ආකාරයට ගැළපෙන තරාදිය තෝරන්න.",
        )
    if kind == "mass_balance":
        total = as_int(response.get("selected_total_g"))
        target = int(solution["target_mass_g"])
        if total is not None and total != target:
            return Diagnosis(
                you_did=f"ඔබ දැමූ බර {total} g",
                went_wrong=("තරාදිය සම්මත බර පැත්තට බර වැඩියි" if total > target else "තව බර අවශ්‍යයි") + f"; {target} g අවශ්‍යයි.",
            )
    return None

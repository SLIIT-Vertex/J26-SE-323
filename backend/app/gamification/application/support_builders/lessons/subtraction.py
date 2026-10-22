"""Subtraction Adventure (G5-AREA-MAT-04): column subtraction with exchanges, expanded form, and
difference stories."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    PLACES,
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    column_subtraction,
    expanded,
    int_list,
    num,
)

AREA_ID = "G5-AREA-MAT-04"
NO_EXCHANGE_SKILL = "G5-MAT-SUB-NO-REGROUP-01"
EXPANDED_SKILL = "G5-MAT-SUB-EXPANDED-01"
ONE_EXCHANGE_SKILL = "G5-MAT-C07-L01-O01"
DIFFERENCE_SKILL = "G5-MAT-SUB-DIFF-BETWEEN-01"


def _operands(game: Game, solution: Solution) -> tuple[int, int] | None:
    if "minuend" in game:
        return int(game["minuend"]), int(game["subtrahend"])
    quantities = {
        str(row["source"]): int(row["value"])  # type: ignore[index]
        for row in game.get("quantities", [])  # type: ignore[union-attr]
    }
    top = quantities.get(str(solution.get("minuend_source")))
    bottom = quantities.get(str(solution.get("subtrahend_source")))
    return None if top is None or bottom is None else (top, bottom)


def _check(top: int, bottom: int) -> str:
    return f"පරීක්ෂාව: {num(top - bottom)} + {num(bottom)} = {num(top)}."


def lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    operands = _operands(game, solution)
    if operands is None:
        return None
    top, bottom = operands
    result = top - bottom
    columns = column_subtraction(top, bottom)
    if kind == "column_subtraction":
        return Lesson(
            steps=(
                "විශාල සංඛ්‍යාව උඩින්, කුඩා සංඛ්‍යාව යටින්, ස්ථාන ගැළපී ලියන්න.",
                *columns,
                _check(top, bottom),
            ),
            answer=f"{num(top)} − {num(bottom)} = {num(result)}",
            hints=("එකක තීරුවෙන් පටන් ගන්න.", columns[0]),
            another_view=(
                expanded(top),
                expanded(bottom),
                "එකම ස්ථානයේ කොටසින් කොටස අඩු කරන්න.",
            ),
        )
    if kind == "expanded_subtraction":
        top_terms = int_list(solution.get("minuend_terms"))
        bottom_terms = int_list(solution.get("subtrahend_terms"))
        adjusted = int_list(solution.get("adjusted_minuend_terms"))
        results = int_list(solution.get("result_terms"))
        steps = [
            f"{num(top)} = " + " + ".join(map(num, top_terms)) + ".",
            f"{num(bottom)} = " + " + ".join(map(num, bottom_terms)) + ".",
        ]
        if adjusted and adjusted != top_terms:
            steps.append("ණයට ගැනීමෙන් පසු: " + " + ".join(map(num, adjusted)) + ".")
        steps.extend(
            f"{num(a)} − {num(b)} = {num(c)}."
            for a, b, c in zip(adjusted or top_terms, bottom_terms, results, strict=False)
        )
        return Lesson(
            steps=tuple(steps),
            answer=" + ".join(map(num, results)) + f" = {num(result)}",
            hints=tuple(steps[:2]),
            another_view=columns[:2],
        )
    if kind == "difference_story":
        labels = {
            str(row["source"]): str(row.get("label_si", ""))  # type: ignore[union-attr]
            for row in game.get("quantities", [])  # type: ignore[union-attr]
        }
        top_label = labels.get(str(solution.get("minuend_source")), "")
        bottom_label = labels.get(str(solution.get("subtrahend_source")), "")
        return Lesson(
            steps=(
                f"සංඛ්‍යා දෙක: {top_label} {num(top)}, {bottom_label} {num(bottom)}.",
                f"'වෙනස' හෝ 'කොපමණ වැඩිද' යනු විශාල ගණනින් කුඩා ගණන අඩු කිරීමයි: {num(top)} − {num(bottom)}.",
                *columns,
            ),
            answer=f"{num(top)} − {num(bottom)} = {num(result)}",
            hints=(
                f"විශාල ගණන {num(top)}; එය උඩින් ලියන්න.",
                columns[0],
            ),
            another_view=(
                f"{num(bottom)} සිට {num(top)} දක්වා ඉදිරියට ගණන් කළොත් කොපමණ පියවර යනවාද? එයයි වෙනස.",
            ),
        )
    return None


def diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    operands = _operands(game, solution)
    if operands is None:
        return None
    top, bottom = operands
    if solution.get("kind") == "difference_story" and response.get("minuend_source") not in {
        None,
        solution.get("minuend_source"),
    }:
        return Diagnosis(
            you_did="ඔබ කුඩා ගණනින් විශාල ගණන අඩු කිරීමට උත්සාහ කළා",
            went_wrong=f"විශාල ගණන {num(top)} උඩින් තබා {num(bottom)} අඩු කළ යුතුයි.",
            prerequisite_skill_id=DIFFERENCE_SKILL,
        )
    digits = int_list(response.get("result_digits"))
    given = as_int(response.get("result"))
    if given is None and digits:
        given = int("".join(map(str, digits)))
    if given is None or given == top - bottom:
        return None
    width = len(str(top))
    top_digits = [int(d) for d in str(top).rjust(width, "0")][::-1]
    bottom_digits = [int(d) for d in str(bottom).rjust(width, "0")][::-1]
    right_digits = [int(d) for d in str(top - bottom).rjust(width, "0")][::-1]
    child_digits = [int(d) for d in str(given).rjust(width, "0")[-width:]][::-1]
    for place in range(width):
        if child_digits[place] == right_digits[place]:
            continue
        name = PLACES[place]
        if top_digits[place] < bottom_digits[place] and child_digits[place] == bottom_digits[place] - top_digits[place]:
            return Diagnosis(
                you_did=f"ඔබේ පිළිතුර {num(given)}",
                went_wrong=(
                    f"{name} තීරුවේ ඔබ {bottom_digits[place]} න් {top_digits[place]} අඩු කළා (යට ඉලක්කමෙන් උඩ ඉලක්කම). "
                    "උඩ ඉලක්කම කුඩා නම් වම් තීරුවෙන් 1 ක් ණයට ගත යුතුයි."
                ),
                prerequisite_skill_id=ONE_EXCHANGE_SKILL,
            )
        if child_digits[place] == (right_digits[place] + 1) % 10:
            return Diagnosis(
                you_did=f"ඔබේ පිළිතුර {num(given)}",
                went_wrong=f"{name} තීරුවෙන් 1 ක් ණයට දුන් පසු, එම තීරුවේ ඉලක්කම 1 කින් අඩු කිරීමට අමතක විය.",
                prerequisite_skill_id=ONE_EXCHANGE_SKILL,
            )
        return Diagnosis(
            you_did=f"ඔබේ පිළිතුර {num(given)}",
            went_wrong=f"{name} තීරුවේ අඩු කිරීම වැරදුණා; එය {right_digits[place]} විය යුතුයි.",
            prerequisite_skill_id=NO_EXCHANGE_SKILL,
        )
    return None

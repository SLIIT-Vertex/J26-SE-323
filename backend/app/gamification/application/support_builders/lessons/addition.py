"""Addition Adventure (G5-AREA-MAT-02): facts, column addition with carrying, running totals and
table totals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.gamification.application.support_builders.lessons.common import (
    PLACES,
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    column_addition,
    expanded,
    int_list,
    num,
)

AREA_ID = "G5-AREA-MAT-02"
FACTS_SKILL = "G5-MAT-ADD-MENTAL-01"
CARRY_SKILL = "G5-MAT-C06-L01-O01"


def _chain(start: int, values: Sequence[int]) -> list[str]:
    lines: list[str] = []
    total = start
    for value in values:
        lines.append(f"{num(total)} + {num(value)} = {num(total + value)}")
        total += value
    return lines


def _cell(row: int, column: int) -> str:
    return f"r{row}c{column}"


def lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "combine_quantities":
        left, right = int_list(game.get("addends"))[:2]
        total = int(solution["total"])
        big, small = max(left, right), min(left, right)
        counting = ", ".join(str(big + step) for step in range(1, small + 1))
        steps = (
            f"විශාල සංඛ්‍යාව {big} මනසේ තබා ගන්න.",
            f"{small} ක් ඉදිරියට ගණන් කරන්න: {counting}.",
        )
        return Lesson(
            steps=steps,
            answer=f"{left} + {right} = {total}",
            hints=steps[:1],
            another_view=(
                f"{left} ක් සහ {right} ක් ගෙඩි ගොඩ දෙකක් ලෙස සිතා, ගොඩවල් දෙක එකට දමා ගණන් කරන්න.",
            ),
        )
    if kind == "regroup_carry":
        addends = int_list(game.get("addends"))
        total = int(solution["total"])
        lines, _ = column_addition(addends)
        return Lesson(
            steps=(
                "සංඛ්‍යා එක යට එක ලියන්න — එකක එකක යටට, දහය දහය යටට.",
                *lines,
            ),
            answer=" + ".join(num(value) for value in addends) + f" = {num(total)}",
            hints=("එකක තීරුවෙන් පටන් ගන්න.", lines[0]),
            another_view=tuple(f"{expanded(value)}" for value in addends)
            + ("එකම ස්ථානයේ කොටස් එකට එකතු කරන්න.",),
        )
    if kind == "route_progression":
        start = int(game["start"])
        stops = int_list(game.get("stops"))
        totals = int_list(solution.get("totals"))
        lines = _chain(start, stops)
        return Lesson(
            steps=tuple(f"නැවතුම {index + 1}: {line}." for index, line in enumerate(lines)),
            answer="සමුච්චිත එකතු: " + ", ".join(num(value) for value in totals),
            hints=(
                "සෑම නැවතුමකදීම පෙර එකතුවට නව සංඛ්‍යාව එකතු කරන්න.",
                f"නැවතුම 1: {lines[0]}." if lines else "",
            ),
            another_view=(
                "මෙය ගමනක් වගේ: සෑම නැවතුමකදීම බසයට තවත් අය නඟිති; මුළු ගණන වැඩි වෙයි.",
            ),
        )
    if kind == "cargo_loading":
        addends = int_list(game.get("addends"))
        total = int(solution["total"])
        lines = _chain(addends[0], addends[1:]) if addends else []
        return Lesson(
            steps=(
                "කතාවේ සියලු කාණ්ඩ ගණන් තෝරන්න: " + ", ".join(num(value) for value in addends) + ".",
                *(f"{line}." for line in lines),
            ),
            answer=f"මුළු ගණන {num(total)}",
            hints=("'මුළු' යනු සියල්ල එකතු කිරීමයි.", f"{lines[0]}." if lines else ""),
            another_view=(
                "සංඛ්‍යා එක යට එක ලියා තීරු අනුව එකතු කළ හැකිය.",
            ),
        )
    if kind == "data_cell_selection":
        return _table_lesson(game, solution)
    return None


def _table_lesson(game: Game, solution: Solution) -> Lesson | None:
    table = [int_list(row) for row in game.get("table", [])]  # type: ignore[union-attr]
    rows = [str(label) for label in game.get("row_labels", [])]  # type: ignore[union-attr]
    columns = [str(label) for label in game.get("column_labels", [])]  # type: ignore[union-attr]
    target = game.get("target_type")
    total = as_int(solution.get("total"))
    if not table or total is None:
        return None
    if target == "difference":
        first, second = int_list(game.get("comparison_rows"))[:2]
        sums = [sum(table[first]), sum(table[second])]
        return Lesson(
            steps=(
                f"{rows[first]} පේළිය: " + " + ".join(map(num, table[first])) + f" = {num(sums[0])}.",
                f"{rows[second]} පේළිය: " + " + ".join(map(num, table[second])) + f" = {num(sums[1])}.",
                f"වෙනස: {num(max(sums))} − {num(min(sums))} = {num(total)}.",
            ),
            answer=f"වෙනස {num(total)}",
            hints=(f"මුලින් {rows[first]} පේළියේ කොටු තුනම එකතු කරන්න.",),
            another_view=("වෙනස යනු විශාල එකතුවෙන් කුඩා එකතුව අඩු කිරීමයි.",),
        )
    if target == "maximum_row":
        sums = [sum(row) for row in table]
        best = sums.index(max(sums))
        return Lesson(
            steps=tuple(
                f"{rows[index]}: " + " + ".join(map(num, row)) + f" = {num(sums[index])}."
                for index, row in enumerate(table)
            )
            + (f"විශාලතම එකතුව {num(max(sums))}; එය {rows[best]} පේළියයි.",),
            answer=f"{rows[best]} (එකතුව {num(total)})",
            hints=("සෑම පේළියකම එකතුව වෙන වෙනම සොයන්න.",),
            another_view=("තනි කොටු නොව, පේළියේ මුළු එකතුව සසඳන්න.",),
        )
    selected = [str(cell) for cell in solution.get("selected_cells", [])]  # type: ignore[union-attr]
    values = [table[int(cell[1])][int(cell.split("c")[1])] for cell in selected]
    if target == "column" and selected:
        column = int(selected[0].split("c")[1])
        where = f"{columns[column]} තීරුවේ"
    elif selected:
        row = int(selected[0][1])
        where = f"{rows[row]} පේළියේ"
    else:
        where = ""
    return Lesson(
        steps=(
            f"{where} කොටු තෝරන්න: " + ", ".join(map(num, values)) + ".",
            " + ".join(map(num, values)) + f" = {num(total)}.",
        ),
        answer=f"මුළු එකතුව {num(total)}",
        hints=(f"{where} කොටු පමණක් තෝරන්න; අනෙක් ඒවා මඟ හරින්න.",),
        another_view=("වගුවේ ශීර්ෂය බලා අවශ්‍ය තීරුව හෝ පේළිය සොයන්න.",),
    )


def diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind in {"regroup_carry", "cargo_loading", "combine_quantities"}:
        given = as_int(response.get("total"))
        addends = int_list(game.get("addends"))
        wanted = as_int(solution.get("total"))
        if given is None or wanted is None or given == wanted or not addends:
            return None
        place, forgot_carry = _first_wrong_column(addends, given)
        if place is None:
            return None
        name = PLACES[place] if place < len(PLACES) else "ඉහළ"
        if forgot_carry:
            return Diagnosis(
                you_did=f"ඔබේ එකතුව {num(given)}",
                went_wrong=f"{name} තීරුවට ගෙන ආ 1 එකතු කිරීමට අමතක විය.",
                prerequisite_skill_id=CARRY_SKILL,
            )
        return Diagnosis(
            you_did=f"ඔබේ එකතුව {num(given)}",
            went_wrong=f"{name} තීරුවේ එකතු කිරීම වැරදුණා; එම තීරුවේ ඉලක්කම් නැවත එකතු කරන්න.",
            prerequisite_skill_id=FACTS_SKILL,
        )
    if kind == "route_progression":
        given = int_list(response.get("totals"))
        wanted = int_list(solution.get("totals"))
        for index, (left, right) in enumerate(zip(given, wanted, strict=False)):
            if left != right:
                return Diagnosis(
                    you_did=f"නැවතුම {index + 1} හි ඔබේ එකතුව {num(left)}",
                    went_wrong=f"එය {num(right)} විය යුතුයි; පෙර එකතුවෙන් පටන් ගන්න.",
                    prerequisite_skill_id=FACTS_SKILL,
                )
    if kind == "data_cell_selection":
        given = sorted(str(cell) for cell in response.get("selected_cells", []) or [])  # type: ignore[union-attr]
        wanted = sorted(str(cell) for cell in solution.get("selected_cells", []) or [])  # type: ignore[union-attr]
        if given and given != wanted:
            return Diagnosis(
                you_did=f"ඔබ කොටු {len(given)} ක් තෝරා ගත්තා",
                went_wrong="තෝරාගත් කොටු ප්‍රශ්නයේ තීරුවට හෝ පේළියට ගැළපෙන්නේ නැත.",
                prerequisite_skill_id="G5-MAT-ADD-TABLE-TOTAL-01",
            )
    return None


def _first_wrong_column(addends: Sequence[int], given: int) -> tuple[int | None, bool]:
    """The first column (from the ones) where the child's total differs, and whether the child's
    digit there is exactly what a forgotten carry gives."""

    carry = 0
    width = max(len(str(sum(addends))), len(str(given)))
    for place in range(width):
        column = sum((value // 10**place) % 10 for value in addends)
        right = (column + carry) % 10
        child = (given // 10**place) % 10
        if child != right:
            return place, carry > 0 and child == column % 10
        carry = (column + carry) // 10
    return None, False

"""Nimo's Sky Adventure (G5-AREA-MAT-02): quick addition facts and column addition with carrying."""

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
    return None


def diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    """A forgotten carry sends the child to the carrying skill; a wrong column sum to quick facts."""

    if solution.get("kind") not in {"regroup_carry", "combine_quantities"}:
        return None
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

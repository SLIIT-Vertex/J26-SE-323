"""Number Patterns (G5-AREA-MAT-03): constant-difference and constant-ratio patterns."""

from __future__ import annotations

import itertools
from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    int_list,
    num,
)

AREA_ID = "G5-AREA-MAT-03"
ADD_SKILL = "G5-MAT-PAT-DIFF-ASC-01"
DOUBLE_SKILL = "G5-MAT-PAT-RATIO-2-01"


def _rule(solution: Solution) -> tuple[str, int, str]:
    """The sign, the step and the rule in words."""

    if solution.get("kind") == "constant_ratio_pattern":
        step = int(solution["multiplier"])
        return "×", step, f"සෑම පදයක්ම පෙර පදය මෙන් {step} ගුණයකි (× {step})"
    step = int(solution["difference"])
    if solution.get("operation") == "subtract":
        return "−", step, f"සෑම පදයක්ම පෙර පදයට වඩා {step} කින් අඩුයි (− {step})"
    return "+", step, f"සෑම පදයක්ම පෙර පදයට වඩා {step} කින් වැඩියි (+ {step})"


def _apply(sign: str, value: int, step: int) -> int:
    return value * step if sign == "×" else value - step if sign == "−" else value + step


def lesson(game: Game, solution: Solution) -> Lesson | None:
    if solution.get("kind") not in {"constant_difference_pattern", "constant_ratio_pattern"}:
        return None
    terms = list(game.get("visible_terms", []))  # type: ignore[call-overload]
    answers = int_list(solution.get("completed_terms"))
    sign, step, words = _rule(solution)
    known = [as_int(term) for term in terms]
    pairs = [
        f"{num(left)} → {num(right)}"
        for left, right in itertools.pairwise(known)
        if left is not None and right is not None
    ][:3]
    filled: list[str] = []
    remaining = iter(answers)
    previous: int | None = None
    for term in known:
        if term is None:
            value = next(remaining, None)
            if previous is not None and value is not None:
                filled.append(f"{num(previous)} {sign} {step} = {num(value)}.")
            term = value
        previous = term
    if sign == "×":
        another = tuple(
            f"{num(left)} × {step} = " + " + ".join([num(left)] * step) + f" = {num(left * step)}"
            for left in [value for value in known if value is not None][:2]
        )
    else:
        another = (
            "සංඛ්‍යා රේඛාවක සෑම පදයකටම "
            + ("දකුණට" if sign == "+" else "වමට")
            + f" පියවර {step} බැගින් පනින්න.",
        )
    return Lesson(
        steps=(
            "දන්නා පද අතර වෙනස බලන්න: " + ", ".join(pairs) + ".",
            f"නීතිය: {words}.",
            *filled,
        ),
        answer="හිස් තැන්: " + ", ".join(num(value) for value in answers),
        hints=(
            "දන්නා පද දෙකක් අතර කුමක් සිදුවේදැයි බලන්න — එකතු වෙනවාද, අඩු වෙනවාද, ගුණ වෙනවාද?",
            f"නීතිය {sign} {step} යි. එය අන්තිම දන්නා පදයට යොදන්න.",
        ),
        another_view=another,
    )


def diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    given = int_list(response.get("completed_terms"))
    wanted = int_list(solution.get("completed_terms"))
    if not given or given == wanted:
        return None
    sign, step, words = _rule(solution)
    known = [term for term in (as_int(term) for term in game.get("visible_terms", [])) if term is not None]  # type: ignore[union-attr]
    # Adding the gap between the last two known terms, instead of multiplying, is the usual slip.
    added_gap = len(known) >= 2 and given[0] == known[-1] + (known[-1] - known[-2])
    if sign == "×" and added_gap:
        return Diagnosis(
            you_did="ඔබේ පද: " + ", ".join(map(num, given)),
            went_wrong=f"ඔබ එකම ගණනක් එකතු කළා. මෙහි නීතිය ගුණ කිරීමයි: {words}.",
            prerequisite_skill_id=DOUBLE_SKILL,
        )
    rule_given = (
        response.get("multiplier") if sign == "×" else response.get("difference")
    )
    if as_int(rule_given) is not None and as_int(rule_given) != step:
        return Diagnosis(
            you_did=f"ඔබ සොයාගත් නීතිය {sign} {rule_given}",
            went_wrong=f"නිවැරදි නීතිය: {words}. දන්නා පද දෙකක් නැවත සසඳන්න.",
            prerequisite_skill_id=ADD_SKILL if sign != "×" else DOUBLE_SKILL,
        )
    index = next(
        (index for index, (a, b) in enumerate(zip(given, wanted, strict=False)) if a != b), 0
    )
    return Diagnosis(
        you_did="ඔබේ පද: " + ", ".join(map(num, given)),
        went_wrong=f"නීතිය හරි, නමුත් {index + 1} වන හිස් තැනේ ගණනය වැරදුණා; එය {num(wanted[index])} විය යුතුයි.",
        prerequisite_skill_id=None,
    )

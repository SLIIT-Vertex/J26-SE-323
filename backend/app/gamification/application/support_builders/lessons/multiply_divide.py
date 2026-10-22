"""Multiplication Adventure (G5-AREA-MAT-06) and Division Adventure (G5-AREA-MAT-08)."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    PLACES,
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    int_list,
    num,
)

MULTIPLICATION_AREA_ID = "G5-AREA-MAT-06"
DIVISION_AREA_ID = "G5-AREA-MAT-08"
TABLE_SKILL = "G5-MAT-MUL-TABLE-01"
BY_2_3_SKILL = "G5-MAT-MUL-BY-2-3-01"
SHARE_SKILL = "G5-MAT-DIV-SHARE-01"
PLAN_SKILL = "G5-MAT-DIV-PLAN-01"


def _repeated(value: int, times: int) -> str:
    if times > 12:
        return ""
    return " + ".join([num(value)] * times) + f" = {num(value * times)}"


def _column_multiplication(multiplicand: int, multiplier: int) -> list[str]:
    lines: list[str] = []
    carry = 0
    text = str(multiplicand)
    for place, digit in enumerate(int(d) for d in reversed(text)):
        product = digit * multiplier + carry
        carried = f" + ගෙන ආ {carry}" if carry else ""
        # The digit stands for digit × place: 6 tens × 3 = 18 tens = 180.
        worth = (
            f" ({digit} {PLACES[place]} × {multiplier} = {digit * multiplier} {PLACES[place]}"
            f" = {num(digit * multiplier * 10**place)})"
            if place
            else ""
        )
        last = place == len(text) - 1
        if last:
            lines.append(f"{PLACES[place]}: {digit} × {multiplier}{carried} = {product}{worth} → {product} ලියන්න.")
        elif product >= 10:
            lines.append(
                f"{PLACES[place]}: {digit} × {multiplier}{carried} = {product}{worth} → {product % 10} ලියා "
                f"{product // 10} ක් {PLACES[place + 1]} තීරුවට ගෙන යන්න."
            )
        else:
            lines.append(f"{PLACES[place]}: {digit} × {multiplier}{carried} = {product}{worth} → {product} ලියන්න.")
        carry = product // 10
    return lines


def multiplication_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "multiplication_fact":
        left, right = int(solution["multiplicand"]), int(solution["multiplier"])
        product = int(solution["product"])
        small, big = sorted((left, right))
        return Lesson(
            steps=(
                f"{left} × {right} යනු {big} ක් {small} වරක් එකතු කිරීමයි.",
                _repeated(big, small) + "." if small else "ඕනෑම සංඛ්‍යාවක් × 0 = 0.",
            ),
            answer=f"{left} × {right} = {product}",
            hints=(f"{big} ගුණන වගුව {big}, {big * 2}, {big * 3} … ලෙස කියවන්න.",),
            another_view=(
                f"වගුවේ {left} පේළිය සහ {right} තීරුව හමුවන කොටුව බලන්න.",
                f"{left} × {right} = {right} × {left}.",
            ),
        )
    if kind == "written_multiplication":
        multiplicand, multiplier = int(solution["multiplicand"]), int(solution["multiplier"])
        product = int(solution["product"])
        lines = _column_multiplication(multiplicand, multiplier)
        parts = [
            int(digit) * 10 ** (len(str(multiplicand)) - index - 1)
            for index, digit in enumerate(str(multiplicand))
            if digit != "0"
        ]
        return Lesson(
            steps=("එකක තීරුවෙන් පටන් ගෙන එක් එක් ඉලක්කම ගුණ කරන්න.", *lines),
            answer=f"{num(multiplicand)} × {multiplier} = {num(product)}",
            hints=("එකක තීරුවෙන් පටන් ගන්න.", lines[0]),
            another_view=(
                f"{num(multiplicand)} = " + " + ".join(map(num, parts)) + ".",
                " + ".join(f"({num(part)} × {multiplier})" for part in parts)
                + " = "
                + " + ".join(num(part * multiplier) for part in parts)
                + f" = {num(product)}.",
            ),
        )
    if kind == "multiplication_story":
        size, count = int(solution["group_size"]), int(solution["group_count"])
        product = int(solution["product"])
        label = str(game.get("label_si", "දේවල්"))
        return Lesson(
            steps=(
                f"කණ්ඩායම් {count} ක් ඇත; එක් කණ්ඩායමක {label} {size} බැගින්.",
                f"සමාන කණ්ඩායම් යනු ගුණ කිරීමයි: {count} × {size}.",
                f"{_repeated(size, count) or f'{count} × {size} = {product}'}.",
            ),
            answer=f"{count} × {size} = {product} {label}",
            hints=(f"කණ්ඩායම් ගණන {count}; එක කණ්ඩායමක ගණන {size}.",),
            another_view=(f"{size} න් {size} ට ගණන් කරන්න: " + ", ".join(str(size * n) for n in range(1, min(count, 12) + 1)) + ".",),
        )
    return None


def multiplication_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    given = as_int(response.get("product"))
    digits = int_list(response.get("result_digits"))
    if given is None and digits:
        given = int("".join(map(str, digits)))
    wanted = as_int(solution.get("product"))
    if given is None or wanted is None or given == wanted:
        return None
    if kind != "written_multiplication":
        return Diagnosis(
            you_did=f"ඔබේ පිළිතුර {num(given)}",
            went_wrong=f"ගුණන වගුව නැවත බලන්න: පිළිතුර {num(wanted)} විය යුතුයි.",
            prerequisite_skill_id=TABLE_SKILL,
        )
    multiplicand, multiplier = int(solution["multiplicand"]), int(solution["multiplier"])
    carry = 0
    for place, digit in enumerate(int(d) for d in reversed(str(multiplicand))):
        product = digit * multiplier + carry
        right = product % 10
        child = (given // 10**place) % 10
        if child != right:
            if carry and child == (digit * multiplier) % 10:
                return Diagnosis(
                    you_did=f"ඔබේ පිළිතුර {num(given)}",
                    went_wrong=f"{PLACES[place]} තීරුවට ගෙන ආ {carry} එකතු කිරීමට අමතක විය.",
                    prerequisite_skill_id=BY_2_3_SKILL,
                )
            return Diagnosis(
                you_did=f"ඔබේ පිළිතුර {num(given)}",
                went_wrong=f"{PLACES[place]} තීරුවේ {digit} × {multiplier} ගුණ කිරීම වැරදුණා; {digit} × {multiplier} = {digit * multiplier}.",
                prerequisite_skill_id=TABLE_SKILL,
            )
        carry = product // 10
    return None


def _working(solution: Solution) -> Mapping[str, object]:
    working = solution.get("written_working")
    return working if isinstance(working, Mapping) else solution


def _division_steps(working: Mapping[str, object], divisor: int) -> list[str]:
    lines: list[str] = []
    for step in working.get("working_steps", []):  # type: ignore[union-attr]
        partial = int(step["partial_dividend"])  # type: ignore[index]
        digit = int(step["quotient_digit"])  # type: ignore[index]
        product = int(step["partial_product"])  # type: ignore[index]
        rest = int(step["subtraction_result"])  # type: ignore[index]
        down = step.get("brought_down_digit")  # type: ignore[union-attr]
        line = (
            f"{partial} ÷ {divisor}: {divisor} × {digit} = {product} ({partial} ට නොවැඩි). "
            f"{partial} − {product} = {rest}."
        )
        if down is not None:
            line += f" ඊළඟ ඉලක්කම {down} පහළට ගෙන එන්න → {rest * 10 + int(down)}."
        lines.append(line)
    return lines


def division_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    dividend, divisor = int(game["dividend"]), int(game["divisor"])
    if kind == "equal_sharing":
        quotient = int(solution["quotient"])
        remainder = int(solution.get("remainder", 0))
        return Lesson(
            steps=(
                f"{dividend} ක් කණ්ඩායම් {divisor} කට සමානව බෙදන්න.",
                f"{divisor} × ? = {dividend} සොයන්න: {divisor} × {quotient} = {divisor * quotient}.",
                f"සෑම කණ්ඩායමකටම {quotient} බැගින්" + (f", ඉතිරි {remainder}." if remainder else "."),
            ),
            answer=f"{dividend} ÷ {divisor} = {quotient}" + (f", ඉතිරි {remainder}" if remainder else ""),
            hints=(f"{divisor} ගුණන වගුවෙන් {dividend} ට ළඟම ගණන සොයන්න.",),
            another_view=(
                f"{dividend} න් {divisor} බැගින් අඩු කරන්න; කී වරක් අඩු කළ හැකිද? එය {quotient}.",
            ),
        )
    working = _working(solution)
    if kind in {"written_division", "division_story"}:
        lines = _division_steps(working, divisor)
        quotient = as_int(working.get("final_quotient"))
        remainder = as_int(working.get("final_remainder")) or 0
        partial_only = bool(game.get("trace_limit"))
        if partial_only:
            answer = "පළමු පියවර: " + (lines[0] if lines else "")
        elif kind == "division_story":
            groups = str(game.get("group_label_si", "කණ්ඩායම්"))
            objects = str(game.get("object_label_si", "දේවල්"))
            answer = f"{dividend} ÷ {divisor} = {quotient}, ඉතිරි {remainder} → සම්පූර්ණ {groups} {quotient}, ඉතිරි {objects} {remainder}"
        else:
            answer = f"{dividend} ÷ {divisor} = {quotient}" + (f", ඉතිරි {remainder}" if remainder else "")
        intro = (f"{dividend} ÷ {divisor}: වම් ඉලක්කමේ සිට එකින් එක බෙදන්න.",)
        if kind == "division_story":
            intro = (
                f"{game.get('object_label_si', 'දේවල්')} {dividend} ක්, එක් {game.get('group_label_si', 'කණ්ඩායම')} කට {divisor} බැගින්: {dividend} ÷ {divisor}.",
                *intro,
            )
        check = (
            f"පරීක්ෂාව: {divisor} × {quotient} = {divisor * quotient}"
            + (
                f"; {divisor * quotient} + ඉතිරි {remainder} = {divisor * quotient + remainder}"
                if remainder
                else ""
            )
            + " ✓"
            if quotient is not None and not partial_only
            else ""
        )
        return Lesson(
            steps=(*intro, *lines, *((check,) if check else ())),
            answer=answer,
            hints=(intro[-1], f"{divisor} ගුණන වගුව: " + ", ".join(str(divisor * n) for n in range(1, 10)) + "."),
            another_view=(
                f"පරීක්ෂාව: {divisor} × {quotient} + {remainder} = {dividend}." if quotient is not None and not partial_only else
                "බෙදීම ගුණ කිරීමේ ප්‍රතිවිරුද්ධයයි.",
            ),
        )
    return None


def division_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    working = _working(solution)
    given_working = response.get("written_working")
    given = given_working if isinstance(given_working, Mapping) else response
    divisor = int(game["divisor"])
    checks = (
        ("quotient_digits", "ලබ්ධියේ ඉලක්කම", SHARE_SKILL, f"{divisor} ගුණන වගුවෙන් කොටසට නොවැඩි ළඟම ගුණිතය සොයන්න."),
        ("partial_products", "ගුණිතය", SHARE_SKILL, f"{divisor} × ලබ්ධියේ ඉලක්කම නැවත ගණනය කරන්න."),
        ("subtraction_results", "අඩු කිරීම", PLAN_SKILL, "කොටසෙන් ගුණිතය අඩු කරන්න."),
        ("brought_down_digits", "පහළට ගෙන ඒම", PLAN_SKILL, "ඊළඟ ඉලක්කම පහළට ගෙන එන්න අමතක නොකරන්න."),
    )
    for key, name, skill, advice in checks:
        child = int_list(given.get(key))
        right = int_list(working.get(key))
        for index, (left, value) in enumerate(zip(child, right, strict=False)):
            if left != value:
                return Diagnosis(
                    you_did=f"පියවර {index + 1} හි ඔබේ {name} {left}",
                    went_wrong=f"එය {value} විය යුතුයි. {advice}",
                    prerequisite_skill_id=skill,
                )
    quotient = as_int(given.get("final_quotient") if given is not response else response.get("quotient"))
    wanted = as_int(working.get("final_quotient"))
    if quotient is not None and wanted is not None and quotient != wanted:
        return Diagnosis(
            you_did=f"ඔබේ පිළිතුර {quotient}",
            went_wrong=f"{game['dividend']} ÷ {divisor} = {wanted}. පියවරෙන් පියවර නැවත බෙදන්න.",
            prerequisite_skill_id=SHARE_SKILL,
        )
    return None

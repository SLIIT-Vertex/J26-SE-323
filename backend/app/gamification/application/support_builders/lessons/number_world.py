"""Number World (G5-AREA-MAT-01): place value, the abacus, expanded form, and ordering."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    PLACES,
    Diagnosis,
    Game,
    Lesson,
    Solution,
    first_mismatch,
    int_list,
    num,
)

AREA_ID = "G5-AREA-MAT-01"
ROD_PLACES = ("ලක්ෂ", "දසදහස", "දහස", "සියය", "දහය", "එකක")


def _digit_line(digit: int, place: int) -> str:
    """``4 ඇත්තේ දහස තැනේ → 4 × 1 000 = 4 000``"""

    return (
        f"{digit} ඇත්තේ {PLACES[place]} තැනේ → {digit} × {num(10**place)} = {num(digit * 10**place)}"
    )


def place_lines(number: int) -> tuple[str, ...]:
    """Every digit of the number with its place and the value it stands for, from the left."""

    text = str(number)
    return tuple(
        _digit_line(int(digit), len(text) - index - 1) + "." for index, digit in enumerate(text)
    )


def _sum_line(number: int) -> str:
    text = str(number)
    terms = [
        num(int(digit) * 10 ** (len(text) - index - 1))
        for index, digit in enumerate(text)
        if digit != "0"
    ]
    return " + ".join(terms) + f" = {num(number)}"


def lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "drag_to_slot" and "selected_place" in solution:
        number, digit = int(game["number"]), int(game["digit"])
        place = int(solution["selected_place"])
        return Lesson(
            steps=(
                f"{num(number)} හි සෑම ඉලක්කමකටම තැනක් සහ අගයක් ඇත:",
                *place_lines(number),
                f"{digit} ඉලක්කම සොයන්න: එය දකුණේ සිට {place + 1} වන ඉලක්කමයි, එනම් {PLACES[place]} තැන.",
                (
                    f"පරීක්ෂාව: {digit} × {num(10**place)} = {num(digit * 10**place)} — "
                    f"{PLACES[place]} තැනේ ඉලක්කමකට එම අගය ලැබේ."
                ),
            ),
            answer=f"{digit} තිබෙන්නේ {PLACES[place]} ස්ථානයේ ({digit} × {num(10**place)}).",
            hints=(
                "දකුණේ අන්තිම ඉලක්කම එකක (× 1) තැනයි; වමට යන සෑම තැනක්ම 10 ගුණයකි: × 10, × 100, × 1 000, × 10 000.",
                f"{digit} ඉලක්කමට ඇඟිල්ල තබා දකුණේ සිට තැන් ගණන් කරන්න.",
            ),
            another_view=(f"විහිදුණු ආකාරය: {_sum_line(number)}.",),
        )
    if kind == "drag_to_slot" and "represented_value" in solution:
        number, digit = int(game["number"]), int(game["digit"])
        value = int(solution["represented_value"])
        place = len(str(value // digit)) - 1 if digit else 0
        return Lesson(
            steps=(
                f"{num(number)} හි ඉලක්කම් සහ ඒවායේ අගයන්:",
                *place_lines(number),
                f"{digit} තිබෙන්නේ {PLACES[place]} තැනේ; එම තැනේ අගය {num(10**place)}.",
                f"ඉලක්කම × ස්ථානීය අගය: {digit} × {num(10**place)} = {num(value)}.",
            ),
            answer=f"{digit} න් නිරූපණය වන අගය {num(value)} ({digit} × {num(10**place)}).",
            hints=(
                f"{digit} තිබෙන තැන මුලින් සොයන්න.",
                "ඉලක්කම එහි තැනේ අගයෙන් ගුණ කරන්න: ඉලක්කම × ස්ථානීය අගය.",
            ),
            another_view=(f"විහිදුණු ආකාරය: {_sum_line(number)}. {digit} ට අදාළ කොටස {num(value)}.",),
        )
    if kind == "bead_placement":
        rods = int_list(solution.get("rods"))
        number = int(game["number"])
        lines = tuple(
            f"{ROD_PLACES[index]} දණ්ඩට පබළු {count} → {count} × {num(10 ** (len(rods) - index - 1))}"
            f" = {num(count * 10 ** (len(rods) - index - 1))}."
            for index, count in enumerate(rods)
            if index < len(ROD_PLACES)
        )
        return Lesson(
            steps=(f"{num(number)} හි ඉලක්කම් තැන් අනුව බෙදන්න:", *lines, f"එකතුව: {_sum_line(number)}."),
            answer="දඬු (වමේ සිට): " + ", ".join(str(count) for count in rods),
            hints=(
                "දකුණේ අන්තිම දණ්ඩ එකක (× 1) තැනයි.",
                "0 ඉලක්කම ඇති තැනේ දණ්ඩ හිස්ව තබන්න (0 × කුමක් වුවත් = 0).",
            ),
            another_view=(f"විහිදුණු ආකාරය: {_sum_line(number)}.",),
        )
    if kind == "number_order":
        values = int_list(game.get("values"))
        order = int_list(solution.get("order"))
        ascending = bool(game.get("ascending"))
        width = max(len(str(value)) for value in values)
        place = next(
            (
                index
                for index in range(width)
                if len({str(value).rjust(width, "0")[index] for value in values}) > 1
            ),
            width - 1,
        )
        power = width - place - 1
        column = [
            f"{num(value)}: {str(value).rjust(width, '0')[place]} × {num(10**power)}"
            f" = {num(int(str(value).rjust(width, '0')[place]) * 10**power)}"
            for value in values
        ]
        sign = " < " if ascending else " > "
        return Lesson(
            steps=(
                "සංඛ්‍යා වමේ තැනේ සිට සසඳන්න; එකම ඉලක්කම් ඇති තැන් මඟ හරින්න.",
                f"මුලින්ම වෙනස් වන්නේ {PLACES[power]} තැනයි:",
                *column,
                "එම අගයන් අනුව " + ("කුඩාවේ සිට විශාලයට" if ascending else "විශාලයේ සිට කුඩාට") + " පෙළගස්වන්න.",
            ),
            answer=sign.join(num(value) for value in order),
            hints=(
                "සියලු සංඛ්‍යාවල එකම ඉලක්කම් ඇති තැන් මඟ හරින්න.",
                f"{PLACES[power]} තැනේ ඉලක්කම් සසඳන්න.",
            ),
            another_view=(
                "සංඛ්‍යා රේඛාවක: "
                + ("වම් පැත්තේ ඇති සංඛ්‍යා කුඩායි." if ascending else "දකුණු පැත්තේ ඇති සංඛ්‍යා විශාලයි."),
            ),
        )
    return None


def diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "number_order":
        given = int_list(response.get("order"))
        wanted = int_list(solution.get("order"))
        index = first_mismatch(given, wanted)
        if given and index is not None:
            return Diagnosis(
                you_did="ඔබේ පිළිවෙළ: " + ", ".join(num(value) for value in given),
                went_wrong=f"{index + 1} වන තැනට {num(wanted[index])} යා යුතුයි; ස්ථාන එකින් එක සසඳන්න.",
                prerequisite_skill_id="G5-MAT-NUM-POSITION-01",
            )
    if kind == "bead_placement":
        given = int_list(response.get("rods"))
        wanted = int_list(solution.get("rods"))
        index = first_mismatch(given, wanted)
        if given and index is not None and index < len(wanted):
            return Diagnosis(
                you_did="ඔබේ පබළු: " + ", ".join(map(str, given)),
                went_wrong=f"{ROD_PLACES[index]} දණ්ඩට පබළු {wanted[index]} ක් අවශ්‍යයි.",
                prerequisite_skill_id="G5-MAT-NUM-POSITION-01",
            )
    return None

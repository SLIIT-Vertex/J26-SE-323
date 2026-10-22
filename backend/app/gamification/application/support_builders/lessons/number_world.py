"""Number World (G5-AREA-MAT-01): place value, the abacus, expanded form, and ordering."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    PLACES,
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    column_addition,
    first_mismatch,
    int_list,
    num,
)

AREA_ID = "G5-AREA-MAT-01"
ROD_PLACES = ("ලක්ෂ", "දසදහස", "දහස", "සියය", "දහය", "එකක")


def _place_table(number: int) -> str:
    text = str(number)
    return ", ".join(
        f"{digit} → {PLACES[len(text) - index - 1]}" for index, digit in enumerate(text)
    )


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
    if kind == "constructed_number":
        answer = int(solution["constructed_number"])
        base = as_int(game.get("milestone_base")) or answer - 1
        columns, _ = column_addition([base, 1])
        return Lesson(
            steps=(f"{num(base)} + 1 තීරු අනුව එකතු කරමු:", *columns, *place_lines(answer)),
            answer=f"{num(base)} + 1 = {num(answer)}.",
            hints=(
                "9 ට 1 ක් එකතු කළ විට 10 වේ; 0 ලියා 1 ඊළඟ තැනට ගෙන යන්න.",
                columns[0],
            ),
            another_view=(
                "රටාව: "
                + ", ".join(
                    f"{num(answer // 10**k - 1)} + 1 = {num(answer // 10**k)}"
                    for k in range(len(str(answer)) - 2, 0, -1)
                    if answer % 10**k == 0 and answer // 10**k > 1
                )
                + f" — එලෙසම {num(base)} + 1 = {num(answer)}.",
            ),
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
    if kind == "expanded_form":
        number = int(game["number"])
        terms = int_list(solution.get("terms"))
        lines = place_lines(number)
        return Lesson(
            steps=(*lines, f"ශුන්‍ය නොවන කොටස් එකතු කරන්න: {_sum_line(number)}."),
            answer=f"{num(number)} = " + " + ".join(num(term) for term in terms if term),
            hints=(lines[0], "0 ඇති තැන 0 × … = 0; එය කිසිවක් එකතු නොකරයි."),
            another_view=(f"ස්ථානීය අගය වගුව: {_place_table(number)}.",),
        )
    if kind == "digit_order":
        given = int_list(game.get("digits"))
        answer = int_list(solution.get("digits"))
        greatest = bool(game.get("greatest"))
        built = int("".join(map(str, answer)))
        if greatest:
            steps = (
                f"ඉලක්කම් {', '.join(map(str, given))} විශාලයේ සිට කුඩාට පෙළගස්වන්න.",
                "විශාලතම ඉලක්කම විශාලතම අගය ඇති වම් තැනට යයි.",
            )
        else:
            steps = (
                f"ඉලක්කම් {', '.join(map(str, given))} කුඩාවේ සිට විශාලයට පෙළගස්වන්න.",
                "කුඩාතම ඉලක්කම විශාලතම අගය ඇති වම් තැනට යයි.",
            )
            if 0 in given:
                steps += (
                    (
                        "නමුත් 0 මුලට තැබුවොත් සංඛ්‍යාවේ ඉලක්කමක් අඩු වේ. එබැවින් 0 නොවන කුඩාතම "
                        f"ඉලක්කම {answer[0]} මුලට තබා, ඉන්පසු 0 තබන්න."
                    ),
                )
        steps += ("ඒ අනුව තැනින් තැන:", *place_lines(built))
        return Lesson(
            steps=steps,
            answer=("විශාලතම" if greatest else "කුඩාතම") + f" සංඛ්‍යාව {num(built)}.",
            hints=steps[:1],
            another_view=(f"{_sum_line(built)} — වම් තැනේ ඉලක්කම විශාලතම අගය දරයි.",),
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
    if kind == "digit_order":
        given = int_list(response.get("digits"))
        wanted = int_list(solution.get("digits"))
        if not given:
            return None
        if given and given[0] == 0:
            return Diagnosis(
                you_did="ඔබ ගොඩනැගුවේ " + "".join(map(str, given)),
                went_wrong="0 මුලට තැබූ විට එය සම්පූර්ණ ඉලක්කම් ගණනේ සංඛ්‍යාවක් නොවේ.",
                prerequisite_skill_id="G5-MAT-NUM-EXTREME-01",
            )
        index = first_mismatch(given, wanted)
        if index is not None:
            return Diagnosis(
                you_did="ඔබ ගොඩනැගුවේ " + "".join(map(str, given)),
                went_wrong=f"වමේ සිට {index + 1} වන තැනට {wanted[index]} යා යුතුයි.",
                prerequisite_skill_id="G5-MAT-NUM-POSITION-01",
            )
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
    if kind == "expanded_form":
        given = int_list(response.get("terms"))
        wanted = int_list(solution.get("terms"))
        index = first_mismatch(given, wanted)
        if given and index is not None and index < len(wanted):
            return Diagnosis(
                you_did="ඔබේ කොටස්: " + " + ".join(num(term) for term in given),
                went_wrong=f"{index + 1} වන කොටස {num(wanted[index])} විය යුතුයි.",
                prerequisite_skill_id="G5-MAT-NUM-REPRESENTED-01",
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

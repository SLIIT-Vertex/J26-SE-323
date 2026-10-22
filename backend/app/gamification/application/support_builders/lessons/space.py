"""Shapes (G5-AREA-MAT-13), Directions (G5-AREA-MAT-14) and Roman numerals (G5-AREA-MAT-16)."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
)

SHAPE_AREA_ID = "G5-AREA-MAT-13"
DIRECTION_AREA_ID = "G5-AREA-MAT-14"
ROMAN_AREA_ID = "G5-AREA-MAT-16"
MAIN_DIRECTION_SKILL = "G5-MAT-DIRECTION-MAIN-01"
ROMAN_MATCH_SKILL = "G5-MAT-ROMAN-MATCH-01"

SOLIDS = {
    "cube": "ඝනකය",
    "cuboid": "ඝනකාභය",
    "cylinder": "සිලින්ඩරය",
    "triangular_pyramid": "ත්‍රිකෝණ පිරමීඩය",
}
NETS = {
    "cube": "සමාන සමචතුරස්‍ර 6 ක්",
    "cuboid": "සෘජුකෝණාස්‍ර 6 ක් (සමාන යුගල 3 ක්)",
    "cylinder": "රවුම් 2 ක් සහ සෘජුකෝණාස්‍රයක්",
    "triangular_pyramid": "ත්‍රිකෝණ 4 ක්",
}
EXAMPLES = {
    "spirit_level": "ස්පිරිතු ලෙවලය",
    "shelf": "මේසයේ මතුපිට",
    "plumb_line": "ලඹය",
    "wall_edge": "බිත්තියේ සිරස් දාරය",
}
ORIENTATIONS = {"horizontal": "තිරස්", "vertical": "සිරස්"}
DIRECTIONS = {
    "north": "උතුර",
    "north_east": "ඊසාන",
    "east": "නැගෙනහිර",
    "south_east": "ගිනිකොණ",
    "south": "දකුණ",
    "south_west": "නිරිත",
    "west": "බස්නාහිර",
    "north_west": "වයඹ",
}
POSITIONS = {
    "top": "උඩ",
    "right": "දකුණු පැත්ත",
    "bottom": "පහළ",
    "left": "වම් පැත්ත",
    "top_right": "උඩ දකුණු කොන",
    "bottom_right": "පහළ දකුණු කොන",
    "bottom_left": "පහළ වම් කොන",
    "top_left": "උඩ වම් කොන",
}
BETWEEN = {
    "north_east": "උතුර සහ නැගෙනහිර",
    "south_east": "දකුණ සහ නැගෙනහිර",
    "south_west": "දකුණ සහ බස්නාහිර",
    "north_west": "උතුර සහ බස්නාහිර",
}


def _rows(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def shape_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "shape_property_table":
        lines = tuple(
            f"{SOLIDS.get(str(row['solid_id']), row['solid_id'])}: මුහුණත් {row['faces']}, "
            f"ශීර්ෂ {row['vertices']}, දාර {row['edges']}."
            for row in _rows(solution.get("rows"))
        )
        return Lesson(
            steps=(
                "මුහුණත් = පැතලි හෝ වක්‍ර පෘෂ්ඨ; ශීර්ෂ = කොන්; දාර = මුහුණත් දෙකක් හමුවන රේඛා.",
                *lines,
            ),
            answer=" ".join(lines),
            hints=(
                "ඝනකයක් දාදු කැටයක් වගේ: එහි පැති 6 ගණන් කරන්න.",
                "ගණන් කළ කොනට ඇඟිල්ලෙන් ලකුණක් තබන්න; එවිට දෙවරක් ගණන් නොවේ.",
            ),
            another_view=("ඝනකයට සහ ඝනකාභයට එකම ගණන් ඇත; වෙනස වන්නේ මුහුණත්වල ප්‍රමාණය පමණි.",),
        )
    if kind == "orientation_identification":
        lines = tuple(
            f"{EXAMPLES.get(str(row['example_id']), row['example_id'])} → "
            f"{ORIENTATIONS.get(str(row['orientation']), row['orientation'])}."
            for row in _rows(solution.get("selections"))
        )
        return Lesson(
            steps=(
                "තිරස් = බිමට සමාන්තරව, ජල මට්ටම වගේ වැතිරී ඇති.",
                "සිරස් = එල්ලා ඇති ලඹයක් වගේ, උඩ සිට පහළට කෙළින්.",
                *lines,
            ),
            answer=" ".join(lines),
            hints=("බිම මත වැතිරී ඇත්නම් තිරස්; කෙළින් සිටගෙන ඇත්නම් සිරස්.",),
            another_view=("ඔබ නිදාගෙන සිටින විට තිරස්; සිටගෙන සිටින විට සිරස්.",),
        )
    if kind == "solid_net_match":
        lines = tuple(
            f"{SOLIDS.get(str(row['solid_id']), row['solid_id'])} ← {NETS.get(str(row['net_id']), row['net_id'])}."
            for row in _rows(solution.get("matches"))
        )
        return Lesson(
            steps=("පතරොම නවා වසා ගත් විට ඝන වස්තුව සෑදේ. එහි හැඩතල ගණන් කරන්න.", *lines),
            answer=" ".join(lines),
            hints=("සිලින්ඩරයේ පතරොමේ රවුම් දෙකක් ඇත; පිරමීඩයේ ත්‍රිකෝණ පමණි.",),
            another_view=("කඩදාසි පෙට්ටියක් දිග හැරියොත් ලැබෙන්නේ එහි පතරොමයි.",),
        )
    return None


def shape_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "shape_property_table":
        given = {str(row.get("solid_id")): row for row in _rows(response.get("rows"))}
        for row in _rows(solution.get("rows")):
            child = given.get(str(row["solid_id"]))
            if child is None:
                continue
            for field, name in (("faces", "මුහුණත්"), ("vertices", "ශීර්ෂ"), ("edges", "දාර")):
                if as_int(child.get(field)) not in {None, as_int(row[field])}:
                    solid = SOLIDS.get(str(row["solid_id"]), str(row["solid_id"]))
                    return Diagnosis(
                        you_did=f"{solid} සඳහා ඔබේ {name} ගණන {child.get(field)}",
                        went_wrong=f"{solid} හි {name} {row[field]} යි.",
                    )
    if kind == "orientation_identification":
        given = {str(row.get("example_id")): row.get("orientation") for row in _rows(response.get("selections"))}
        for row in _rows(solution.get("selections")):
            if given.get(str(row["example_id"])) not in {None, row["orientation"]}:
                name = EXAMPLES.get(str(row["example_id"]), str(row["example_id"]))
                return Diagnosis(
                    you_did=f"{name} ඔබ {ORIENTATIONS.get(str(given[str(row['example_id'])]), '')} ලෙස තෝරා ගත්තා",
                    went_wrong=f"{name} {ORIENTATIONS[str(row['orientation'])]} යි. තිරස් සහ සිරස් මාරු වී ඇත.",
                )
    if kind == "solid_net_match":
        given = {str(row.get("solid_id")): row.get("net_id") for row in _rows(response.get("matches"))}
        for row in _rows(solution.get("matches")):
            if given.get(str(row["solid_id"])) not in {None, row["net_id"]}:
                return Diagnosis(
                    you_did=f"{SOLIDS.get(str(row['solid_id']))} වෙනත් පතරොමකට ගැළපුවා",
                    went_wrong=f"{SOLIDS.get(str(row['solid_id']))} පතරොම {NETS.get(str(row['net_id']))}.",
                )
    return None


def direction_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    selections = _rows(solution.get("selections"))
    if kind in {"main_direction_compass", "secondary_direction_compass"}:
        lines = tuple(
            f"{POSITIONS.get(str(row['position']), row['position'])} → {DIRECTIONS.get(str(row['direction']), row['direction'])}"
            + (f" ({BETWEEN[str(row['direction'])]} අතර)" if str(row["direction"]) in BETWEEN else "")
            + "."
            for row in selections
        )
        return Lesson(
            steps=(
                "මාලිමාවේ උඩ උතුරයි. ඔරලෝසු කටු යන දිශාවට: උතුර → නැගෙනහිර → දකුණ → බස්නාහිර.",
                *(("අනු දිශාව ප්‍රධාන දිශා දෙක අතර: ඊසාන, ගිනිකොණ, නිරිත, වයඹ.",) if kind == "secondary_direction_compass" else ()),
                *lines,
            ),
            answer=" ".join(lines),
            hints=("උඩ උතුරයි; එයින් පටන් ගෙන දකුණට කැරකෙන්න.",),
            another_view=("උතුරට මුහුණලා සිටින විට දකුණු අත නැගෙනහිර, වම් අත බස්නාහිර, පිටුපස දකුණ.",),
        )
    if kind == "place_direction_scene":
        labels = {
            str(row.get("place_id")): str(row.get("label_si", row.get("place_id")))
            for row in _rows(game.get("placements"))
        }
        lines = tuple(
            f"{labels.get(str(row['place_id']), row['place_id'])} → {DIRECTIONS.get(str(row['selected_direction']), row['selected_direction'])}."
            for row in selections
        )
        return Lesson(
            steps=("ළමයා මැද සිටී. ඉහළ පැත්ත උතුරයි.", *lines),
            answer=" ".join(lines),
            hints=("ස්ථානය ළමයාගෙන් උඩද, පහළද, දකුණටද, වමටද බලන්න; කොනක නම් අනු දිශාවකි.",),
            another_view=("මාලිමාව ළමයා මත තබා ඇති ලෙස සිතන්න.",),
        )
    return None


def direction_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    key = "selected_direction" if solution.get("kind") == "place_direction_scene" else "direction"
    anchor = "place_id" if key == "selected_direction" else "position"
    given = {str(row.get(anchor)): row.get(key) for row in _rows(response.get("selections"))}
    for row in _rows(solution.get("selections")):
        child = given.get(str(row[anchor]))
        if child not in {None, row[key]}:
            if {str(child), str(row[key])} in ({"east", "west"}, {"north_east", "north_west"}, {"south_east", "south_west"}):
                went = "නැගෙනහිර සහ බස්නාහිර මාරු වී ඇත. උතුරට මුහුණලා සිටින විට නැගෙනහිර දකුණු අතටයි."
            else:
                went = f"එය {DIRECTIONS.get(str(row[key]))} විය යුතුයි."
            return Diagnosis(
                you_did=f"ඔබ {DIRECTIONS.get(str(child), child)} තෝරා ගත්තා",
                went_wrong=went,
                prerequisite_skill_id=MAIN_DIRECTION_SKILL,
            )
    return None


ROMAN = ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def to_roman(value: int) -> tuple[str, list[str]]:
    """The numeral, and its parts such as ``10 (X)``."""

    parts: list[str] = []
    text = ""
    for amount, symbol in ROMAN:
        while value >= amount:
            value -= amount
            text += symbol
            parts.append(f"{amount} ({symbol})")
    return text, parts


def from_roman(text: str) -> tuple[int, str]:
    """The value, and how it was read: adding, or subtracting a small symbol before a big one."""

    symbols = text.upper()
    total = 0
    reading: list[str] = []
    for index, symbol in enumerate(symbols):
        value = ROMAN_VALUES.get(symbol, 0)
        following = ROMAN_VALUES.get(symbols[index + 1], 0) if index + 1 < len(symbols) else 0
        if value < following:
            total -= value
            reading.append(f"− {value}")
        else:
            total += value
            reading.append(f"+ {value}")
    return total, " ".join(reading).lstrip("+ ").strip()


def _explain(value: int) -> str:
    numeral, parts = to_roman(value)
    return f"{value} = " + " + ".join(parts) + f" → {numeral}"


def roman_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "roman_numeral_match":
        lines = tuple(_explain(int(row["arabic_value"])) + "." for row in _rows(solution.get("matches")))
        return Lesson(
            steps=("I = 1, V = 5, X = 10. සංඛ්‍යාව දහය, පහ, එක ලෙස කඩන්න.", *lines),
            answer="; ".join(
                f"{row['arabic_value']} → {str(row['selected_roman']).upper()}" for row in _rows(solution.get("matches"))
            ),
            hints=("කුඩා සංකේතයක් විශාල එකකට පෙර ආවොත් අඩු කරන්න: IV = 4, IX = 9.",),
            another_view=("XVII = 10 + 5 + 1 + 1. වමේ සිට එකතු කරමින් කියවන්න.",),
        )
    if kind == "emoji_quantity_to_roman":
        quantity = int(solution["quantity"])
        return Lesson(
            steps=(
                f"රූප එකින් එක ගණන් කරන්න: 1, 2, … {quantity}.",
                _explain(quantity) + ".",
            ),
            answer=f"{quantity} → {str(solution['final_roman']).upper()}",
            hints=("රූප පහ බැගින් කණ්ඩායම් කළොත් ගණන් කිරීම පහසුයි: පහක් = V, දහයක් = X.",),
            another_view=(f"{quantity} = " + " + ".join(to_roman(quantity)[1]) + ".",),
        )
    if kind == "roman_arithmetic":
        left, right = str(solution["left_roman"]), str(solution["right_roman"])
        left_value, left_reading = from_roman(left)
        right_value, right_reading = from_roman(right)
        result = int(solution["final_value"])
        sign = "+" if solution.get("operation") == "add" else "−"
        return Lesson(
            steps=(
                f"{left.upper()} = {left_reading} = {left_value}.",
                f"{right.upper()} = {right_reading} = {right_value}.",
                f"{left_value} {sign} {right_value} = {result}.",
                _explain(result) + ".",
            ),
            answer=f"{left.upper()} {sign} {right.upper()} = {str(solution['final_roman']).upper()} ({result})",
            hints=("මුලින් රෝම සංඛ්‍යා දෙක සාමාන්‍ය අංක බවට හරවන්න.", f"{left.upper()} = {left_value}."),
            another_view=("ගණනය සාමාන්‍ය අංකවලින් කර, පිළිතුර නැවත රෝම සංඛ්‍යාවක් කරන්න.",),
        )
    return None


def roman_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "roman_arithmetic":
        given = str(response.get("final_roman") or "").upper()
        if given and given != str(solution["final_roman"]).upper():
            for side in ("left", "right"):
                read = as_int(response.get(f"{side}_value_work"))
                value, reading = from_roman(str(solution[f"{side}_roman"]))
                if read is not None and read != value:
                    return Diagnosis(
                        you_did=f"ඔබ {str(solution[f'{side}_roman']).upper()} = {read} ලෙස කියෙව්වා",
                        went_wrong=f"{str(solution[f'{side}_roman']).upper()} = {reading} = {value}. කුඩා සංකේතය විශාල එකකට පෙර නම් අඩු කරන්න.",
                        prerequisite_skill_id=ROMAN_MATCH_SKILL,
                    )
            return Diagnosis(
                you_did=f"ඔබේ පිළිතුර {given}",
                went_wrong=f"ගණනය හරි නම්, {solution['final_value']} රෝම සංඛ්‍යාවක් ලෙස ලියන්න: {_explain(int(solution['final_value']))}.",
                prerequisite_skill_id=ROMAN_MATCH_SKILL,
            )
    if kind == "roman_numeral_match":
        given = {as_int(row.get("arabic_value")): str(row.get("selected_roman")) for row in _rows(response.get("matches"))}
        for row in _rows(solution.get("matches")):
            child = given.get(int(row["arabic_value"]))
            if child not in {None, str(row["selected_roman"])}:
                return Diagnosis(
                    you_did=f"{row['arabic_value']} ඔබ {child.upper()} ට ගැළපුවා",
                    went_wrong=_explain(int(row["arabic_value"])) + ".",
                )
    if kind == "emoji_quantity_to_roman":
        given = str(response.get("final_roman") or "").upper()
        if given and given != str(solution["final_roman"]).upper():
            return Diagnosis(
                you_did=f"ඔබ ගොඩනැගුවේ {given} ({from_roman(given)[0]})",
                went_wrong=f"රූප {solution['quantity']} කි: {_explain(int(solution['quantity']))}.",
                prerequisite_skill_id=ROMAN_MATCH_SKILL,
            )
    return None

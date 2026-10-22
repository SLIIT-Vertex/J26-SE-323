"""Fraction Adventure (G5-AREA-MAT-05) and Decimal Adventure (G5-AREA-MAT-15)."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    Diagnosis,
    Game,
    Lesson,
    Solution,
    as_int,
    int_list,
)

FRACTION_AREA_ID = "G5-AREA-MAT-05"
DECIMAL_AREA_ID = "G5-AREA-MAT-15"
HALF_GROUP_SKILL = "G5-MAT-C03-L01-O01"
QUARTER_GROUP_SKILL = "G5-MAT-C03-L01-O02"
TENTHS_BUILD_SKILL = "G5-MAT-FRC-TENTHS-BUILD-01"
DECIMAL_SHADE_SKILL = "G5-MAT-DECIMAL-SHADE-01"

SHAPES = {"circle": "රවුම", "rectangle": "සෘජුකෝණාස්‍රය"}
FRACTION_WORDS = {2: "බාගය", 4: "කාලය", 10: "දහයෙන් පංගුව"}


def fraction_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind in {"fraction_shading", "tenths_representation"}:
        denominator = int(solution["denominator"])
        shaded = int_list(solution.get("shaded_indices"))
        numerator = as_int(solution.get("numerator")) or len(shaded)
        shape = SHAPES.get(str(solution.get("representation")), "රූපය")
        reading = bool(game.get("stimulus_shaded_indices"))
        if reading:
            steps = (
                f"{shape} සමාන කොටස් {denominator} කට බෙදා ඇත. එය පහළ අංකයයි (හරය).",
                f"පාට කළ කොටස් එකින් එක ගණන් කරන්න: {numerator}. එය ඉහළ අංකයයි (ලවය).",
            )
        else:
            steps = (
                f"{shape} සමාන කොටස් {denominator} කට බෙදා ඇත. එය පහළ අංකයයි (හරය).",
                f"ඉහළ අංකය {numerator}: කොටස් {numerator} ක් එකින් එක පාට කරන්න.",
            )
        return Lesson(
            steps=steps,
            answer=f"{numerator}/{denominator} — කොටස් {denominator} න් {numerator} ක්",
            hints=(steps[0], "කොටස් සියල්ලම පාට කළොත් එය සම්පූර්ණයයි, භාගයක් නොවේ."),
            another_view=(
                f"{numerator}/{denominator} = දශම ලෙස 0.{numerator}" if denominator == 10 else
                f"සමාන කොටස් {denominator} න් එකක් {FRACTION_WORDS.get(denominator, 'කොටසක්')}යි.",
            ),
        )
    if kind == "equal_grouping":
        total, groups = int(game["total"]), int(game["denominator"])
        share = total // groups
        return Lesson(
            steps=(
                f"ඇපල් {total}, කණ්ඩායම් {groups}.",
                f"එක් ඇපලයක් බැගින් කණ්ඩායම් {groups} ට මාරුවෙන් මාරුවට දමන්න.",
                f"{total} ÷ {groups} = {share}: සෑම කණ්ඩායමකටම ඇපල් {share} බැගින්.",
                f"පරීක්ෂාව: {groups} × {share} = {groups * share} ✓ — ඇපල් සියල්ල බෙදී ඇත.",
            ),
            answer=f"කණ්ඩායම් {groups} ට ඇපල් {share} බැගින්",
            hints=(
                "එක් කණ්ඩායමකට ඇපල් දෙකක් දෙන්න එපා; සෑම කණ්ඩායමකටම එක බැගින් රවුමට දෙන්න.",
                "සියලු ඇපල් කණ්ඩායම්වලට දමන්න; එකක්වත් ඉතිරි නොවිය යුතුයි.",
            ),
            another_view=(
                f"{total} හි 1/{groups} = {total} ÷ {groups} = {share}.",
                f"පරීක්ෂාව: {share} × {groups} = {total}.",
            ),
        )
    if kind == "fraction_quantity_table":
        total = int(solution["total"])
        values = int_list(solution.get("quarter_values"))
        quarter = total // 4
        return Lesson(
            steps=(
                f"¼ = සම්පූර්ණය සමාන කොටස් 4 කින් එකක්: {total} ÷ 4 = {quarter}.",
                f"2/4 = කාල දෙකක්: {quarter} × 2 = {values[1]}.",
                f"3/4 = කාල තුනක්: {quarter} × 3 = {values[2]}.",
            ),
            answer="¼ = {}, 2/4 = {}, 3/4 = {}".format(*values),
            hints=(f"මුලින් ¼ සොයන්න: {total} ÷ 4.",),
            another_view=(
                f"2/4 යනු බාගයයි: {total} හි බාගය {total // 2}.",
            ),
        )
    return None


def fraction_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "equal_grouping":
        assignments = int_list(response.get("assignments"))
        groups = int(game["denominator"])
        total = int(game["total"])
        sizes = [assignments.count(group) for group in range(groups)]
        if assignments.count(-1):
            return Diagnosis(
                you_did=f"ඔබ ඇපල් {total - assignments.count(-1)} ක් පමණක් බෙදුවා",
                went_wrong=f"ඇපල් {assignments.count(-1)} ක් ඉතිරි විය. සියල්ලම බෙදිය යුතුයි.",
                prerequisite_skill_id=HALF_GROUP_SKILL,
            )
        if sizes and len(set(sizes)) > 1:
            return Diagnosis(
                you_did="ඔබේ කණ්ඩායම්: " + ", ".join(map(str, sizes)),
                went_wrong=f"කණ්ඩායම් සමාන නැත; සෑම කණ්ඩායමකටම {total // groups} බැගින් විය යුතුයි.",
                prerequisite_skill_id=HALF_GROUP_SKILL,
            )
    if kind in {"fraction_shading", "tenths_representation"}:
        shaded = int_list(response.get("shaded_indices"))
        denominator = int(solution["denominator"])
        wanted = as_int(solution.get("numerator")) or len(int_list(solution.get("shaded_indices")))
        given = as_int(response.get("numerator"))
        count = given if given is not None else len(shaded)
        if count == wanted:
            return None
        if count == denominator:
            went = "ඔබ සියලු කොටස් තෝරා ගත්තා; එය සම්පූර්ණයයි."
        elif count == denominator - wanted:
            went = "ඔබ ගණන් කළේ පාට නොකළ කොටස් බව පෙනේ."
        else:
            went = f"කොටස් {wanted} ක් විය යුතුයි."
        return Diagnosis(
            you_did=f"ඔබ කොටස් {count} ක් ගත්තා",
            went_wrong=went,
            prerequisite_skill_id=TENTHS_BUILD_SKILL if denominator == 10 else None,
        )
    if kind == "fraction_quantity_table":
        given = int_list(response.get("quarter_values"))
        wanted = int_list(solution.get("quarter_values"))
        if given and given != wanted:
            if given[0] != wanted[0]:
                went = f"¼ ම වැරදුණා: {solution['total']} ÷ 4 = {wanted[0]}."
            else:
                went = "¼ හරි; 2/4 සහ 3/4 සඳහා ¼ ගුණ කරන්න."
            return Diagnosis(
                you_did="ඔබේ වගුව: " + ", ".join(map(str, given)),
                went_wrong=went,
                prerequisite_skill_id=QUARTER_GROUP_SKILL,
            )
    return None


def _decimal(tenths: int) -> str:
    return f"0.{tenths}"


def decimal_lesson(game: Game, solution: Solution) -> Lesson | None:
    kind = solution.get("kind")
    if kind == "decimal_reading_match":
        labels = {
            str(tile["reading_id"]): str(tile["label_si"])  # type: ignore[index]
            for tile in game.get("reading_tiles", [])  # type: ignore[union-attr]
        }
        pairs = [
            (int(match["decimal_tenths"]), labels.get(str(match["reading_id"]), ""))  # type: ignore[index]
            for match in solution.get("matches", [])  # type: ignore[union-attr]
        ]
        return Lesson(
            steps=(
                "දශම තිතට පෙර 0 'බින්දුව' ලෙස කියවේ. තිතට පසු ඉලක්කම 'දශම …' ලෙස කියවේ.",
                *(f"{_decimal(value)} → {label}" for value, label in pairs),
            ),
            answer="; ".join(f"{_decimal(value)} → {label}" for value, label in pairs),
            hints=(
                "තිතට පසු ඉලක්කම පමණක් බලන්න; එය කියවීමේ අවසාන වචනයයි.",
                f"{_decimal(pairs[0][0])} → {pairs[0][1]}" if pairs else "",
            ),
            another_view=tuple(f"{_decimal(value)} = {value}/10" for value, _ in pairs[:2]),
        )
    if kind == "decimal_tenths_shading":
        tenths = int(solution["decimal_tenths"])
        return Lesson(
            steps=(
                f"{_decimal(tenths)} යනු දහයෙන් {tenths} කි: {tenths}/10.",
                "රූපය සමාන කොටස් 10 කට බෙදා ඇත.",
                f"කොටස් {tenths} ක් එකින් එක පාට කරන්න.",
            ),
            answer=f"කොටස් 10 න් {tenths} ක් පාට කරන්න",
            hints=(f"තිතට පසු ඉලක්කම {tenths}; පාට කරන කොටස් ගණන එයයි.",),
            another_view=(f"{_decimal(tenths)} = {tenths}/10 — දහයෙන් කොටස් {tenths}.",),
        )
    if kind == "tenths_fraction_to_decimal":
        numerator = int(solution["numerator"])
        return Lesson(
            steps=(
                f"{numerator}/10 යනු දහයෙන් කොටස් {numerator} කි.",
                "දහයෙන් කොටස් ලියන්නේ දශම තිතට පසු පළමු තැනේ.",
                f"සම්පූර්ණ එකක් නැති නිසා තිතට පෙර 0: {_decimal(numerator)}.",
            ),
            answer=f"{numerator}/10 = {_decimal(numerator)}",
            hints=("ඉහළ අංකය දශම තිතට පසු තැනට යයි.",),
            another_view=(f"කොටස් 10 කින් {numerator} ක් පාට කළ රූපයක් සිතන්න.",),
        )
    if kind == "decimal_to_tenths_fraction":
        tenths = int(solution["decimal_tenths"])
        return Lesson(
            steps=(
                f"{_decimal(tenths)} හි තිතට පසු ඉලක්කම {tenths}; එය දහයෙන් පංගු ගණනයි.",
                f"ඉහළ අංකය {tenths}, පහළ අංකය 10.",
            ),
            answer=f"{_decimal(tenths)} = {tenths}/10",
            hints=("දශම තිතට පසු පළමු තැන 'දහයෙන්' තැනයි; එබැවින් පහළ අංකය 10.",),
            another_view=(f"කොටස් 10 කින් {tenths} ක් පාට කළ රූපයක් සිතන්න.",),
        )
    return None


def decimal_diagnose(game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    kind = solution.get("kind")
    if kind == "decimal_tenths_shading":
        given = as_int(response.get("selected_count")) or len(int_list(response.get("selected_part_indices")))
        wanted = int(solution["decimal_tenths"])
        if given != wanted:
            return Diagnosis(
                you_did=f"ඔබ කොටස් {given} ක් පාට කළා",
                went_wrong=f"{_decimal(wanted)} සඳහා කොටස් {wanted} ක් අවශ්‍යයි.",
            )
    if kind == "decimal_to_tenths_fraction":
        denominator = as_int(response.get("entered_denominator"))
        if denominator not in {None, 10}:
            return Diagnosis(
                you_did=f"ඔබ පහළ අංකය {denominator} ලෙස තැබුවා",
                went_wrong="දශම තිතට පසු පළමු තැන දහයෙන් පංගුවයි; පහළ අංකය 10 විය යුතුයි.",
                prerequisite_skill_id=DECIMAL_SHADE_SKILL,
            )
    if kind == "decimal_reading_match":
        given = {
            int(match["decimal_tenths"]): str(match.get("reading_id"))  # type: ignore[index, union-attr]
            for match in response.get("matches", []) or []  # type: ignore[union-attr]
            if isinstance(match, Mapping)
        }
        for match in solution.get("matches", []):  # type: ignore[union-attr]
            value = int(match["decimal_tenths"])  # type: ignore[index]
            if given.get(value) not in {None, str(match["reading_id"])}:  # type: ignore[index]
                return Diagnosis(
                    you_did=f"{_decimal(value)} ඔබ වෙනත් කියවීමකට ගැළපුවා",
                    went_wrong=f"{_decimal(value)} හි තිතට පසු ඉලක්කම {value}; කියවීමේ අවසාන වචනය එයයි.",
                    prerequisite_skill_id=DECIMAL_SHADE_SKILL,
                )
    return None

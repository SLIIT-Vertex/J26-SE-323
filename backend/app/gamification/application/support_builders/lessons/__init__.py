"""Concrete mathematics lessons, one module per game, looked up by area id."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.lessons import (
    addition,
    english,
    fractions,
    measures,
    multiply_divide,
    number_world,
    patterns,
    space,
    subtraction,
)
from app.gamification.application.support_builders.lessons.common import (
    DiagnoseFn,
    Diagnosis,
    Lesson,
    LessonFn,
)

_REGISTRY: dict[str, tuple[LessonFn, DiagnoseFn]] = {
    number_world.AREA_ID: (number_world.lesson, number_world.diagnose),
    addition.AREA_ID: (addition.lesson, addition.diagnose),
    patterns.AREA_ID: (patterns.lesson, patterns.diagnose),
    subtraction.AREA_ID: (subtraction.lesson, subtraction.diagnose),
    fractions.FRACTION_AREA_ID: (fractions.fraction_lesson, fractions.fraction_diagnose),
    multiply_divide.MULTIPLICATION_AREA_ID: (
        multiply_divide.multiplication_lesson,
        multiply_divide.multiplication_diagnose,
    ),
    measures.TIME_AREA_ID: (measures.time_lesson, measures.time_diagnose),
    multiply_divide.DIVISION_AREA_ID: (
        multiply_divide.division_lesson,
        multiply_divide.division_diagnose,
    ),
    measures.DISTANCE_AREA_ID: (measures.distance_lesson, measures.distance_diagnose),
    measures.MONEY_AREA_ID: (measures.money_lesson, measures.money_diagnose),
    measures.CAPACITY_AREA_ID: (measures.capacity_lesson, measures.capacity_diagnose),
    measures.MASS_AREA_ID: (measures.mass_lesson, measures.mass_diagnose),
    space.SHAPE_AREA_ID: (space.shape_lesson, space.shape_diagnose),
    space.DIRECTION_AREA_ID: (space.direction_lesson, space.direction_diagnose),
    fractions.DECIMAL_AREA_ID: (fractions.decimal_lesson, fractions.decimal_diagnose),
    space.ROMAN_AREA_ID: (space.roman_lesson, space.roman_diagnose),
}


def lesson_for(area_id: str, game: Mapping[str, object], solution: object) -> Lesson | None:
    """The item's lesson, or ``None`` when the area or this board has none. A lesson is help, so a
    malformed item never breaks the round: it falls back to the generic cues."""

    entry = _REGISTRY.get(area_id)
    if area_id.startswith("G5-AREA-ENG-"):
        entry = (
            lambda g, sol: english.lesson(area_id, g, sol),
            lambda g, sol, response: english.diagnose(area_id, g, sol, response),
        )
    if entry is None or not isinstance(solution, Mapping):
        return None
    try:
        lesson = entry[0](game, solution)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None
    if lesson is None:
        return None
    return Lesson(
        steps=tuple(step for step in lesson.steps if step),
        answer=lesson.answer,
        hints=tuple(hint for hint in lesson.hints if hint),
        another_view=tuple(line for line in lesson.another_view if line),
    )


def diagnosis_for(
    area_id: str,
    game: Mapping[str, object],
    solution: object,
    response: object,
) -> Diagnosis | None:
    entry = _REGISTRY.get(area_id)
    if area_id.startswith("G5-AREA-ENG-"):
        entry = (
            lambda g, sol: english.lesson(area_id, g, sol),
            lambda g, sol, given: english.diagnose(area_id, g, sol, given),
        )
    if entry is None or not isinstance(solution, Mapping) or not isinstance(response, Mapping):
        return None
    try:
        return entry[1](game, solution, response)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None


__all__ = ["Diagnosis", "Lesson", "diagnosis_for", "lesson_for"]

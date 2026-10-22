"""The ``lesson`` block a mathematics help stage shows above or below the board.

Each help type picks different parts of the same item lesson: a worked example and visual
guidance show every step and the answer, a re-explanation shows theory and hints but never the
answer, prerequisite repair starts from what the child did.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.gamification.application.support_builders.context import SupportBuildContext
from app.gamification.application.support_builders.lessons import (
    Diagnosis,
    Lesson,
    diagnosis_for,
    lesson_for,
)

# Subjects whose help teaches with lessons: worked answers, theory, hints and the child's mistake.
TEACHING_SUBJECTS = frozenset({"MAT", "ENG"})


def item_lesson(context: SupportBuildContext, record: Mapping[str, object]) -> Lesson | None:
    if context.subject not in TEACHING_SUBJECTS:
        return None
    game = context.source.support_activity(record)["game"]
    solution = context.source.support_solution(record).get("correct_response")
    return lesson_for(context.area_id, game, solution)  # type: ignore[arg-type]


def failed_diagnosis(context: SupportBuildContext) -> Diagnosis | None:
    if context.subject not in TEACHING_SUBJECTS or context.failed_response is None:
        return None
    record = context.failed_record
    game = context.source.support_activity(record)["game"]
    solution = context.source.support_solution(record).get("correct_response")
    return diagnosis_for(context.area_id, game, solution, context.failed_response)  # type: ignore[arg-type]


def lesson_block(
    title_si: str,
    *,
    steps: Sequence[str] = (),
    answer: str | None = None,
    hints: Sequence[str] = (),
    another_view: Sequence[str] = (),
    notes: Sequence[tuple[str, str]] = (),
    diagnosis: Diagnosis | None = None,
    continue_label_si: str | None = None,
) -> dict[str, object]:
    return {
        "title_si": title_si,
        "notes": [{"title_si": title, "text_si": text} for title, text in notes if text],
        "steps_si": [step for step in steps if step],
        "answer_si": answer,
        "hints_si": [hint for hint in hints if hint],
        "another_view_si": [line for line in another_view if line],
        "diagnosis": None
        if diagnosis is None
        else {"you_did_si": diagnosis.you_did, "went_wrong_si": diagnosis.went_wrong},
        "continue_label_si": continue_label_si,
    }

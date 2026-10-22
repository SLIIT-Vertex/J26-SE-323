"""Guided reasoning: the failed game again, each short question answered for this game."""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportPlan,
    answer_reveal,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for
from app.gamification.application.support_builders.teaching import item_lesson


class StepByStepGuidanceBuilder:
    scaffold_type = "step_by_step_guidance"

    def build(self, context: SupportBuildContext) -> SupportPlan:
        cues = cues_for(context.subject)
        questions = (
            *cues.guided_questions[:3],
            cues.focus(context.reason_family),
            *cues.guided_questions[3:],
        )
        lesson = item_lesson(context, context.failed_record)
        guidance = _taught(context, questions, lesson) if lesson else _answered(context, questions)
        return SupportPlan(
            scaffold_type="step_by_step_guidance",
            title_si="ප්‍රශ්නවලින් මඟ පෙන්වීම",
            stages=(target_stage(context, (), guidance=guidance),),
        )


def _taught(context: SupportBuildContext, questions: tuple[str, ...], lesson) -> tuple[tuple[str, str], ...]:  # type: ignore[no-untyped-def]
    """Mathematics: one question per real step of this item, answered with its own numbers."""

    prompt = str(context.source.support_activity(context.failed_record)["prompt_si"])
    steps = tuple(
        ("පළමුව කළ යුත්තේ කුමක්ද?" if index == 0 else f"ඊළඟට කුමක්ද? (පියවර {index + 1})", step)
        for index, step in enumerate(lesson.steps)
    )
    return ((questions[0], prompt), *steps, (questions[-1], "පිළිතුර: " + lesson.answer))


def _answered(
    context: SupportBuildContext, questions: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """The first question is answered by the game's own prompt, the last by the real answer, and
    the ones between by the game's solving steps, in order, each step used once."""

    record = context.failed_record
    prompt = str(context.source.support_activity(record)["prompt_si"])
    steps = list(
        dict.fromkeys(
            str(step)
            for step in context.source.support_solution(
                record, scaffold_type="step_by_step_guidance"
            ).get("steps_si", ())
        )
    )
    reveal = answer_reveal(context, record, "tint")
    answer = (
        "පිළිතුර: " + "; ".join(reveal["lines"])
        if reveal and reveal["lines"]
        else (steps[-1] if steps else prompt)
    )
    # A question with no step of its own to answer it is left out rather than repeating a step.
    middle = questions[1:-1][: max(len(steps), 1)]
    middle_answers = steps[: len(middle)] or [prompt]
    return (
        (questions[0], prompt),
        *zip(middle, middle_answers, strict=True),
        (questions[-1], answer),
    )

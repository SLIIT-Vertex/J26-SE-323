"""Guided reasoning: the failed game again, each short question answered for this game."""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportPlan,
    answer_reveal,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for


class StepByStepGuidanceBuilder:
    scaffold_type = "step_by_step_guidance"

    def build(self, context: SupportBuildContext) -> SupportPlan:
        cues = cues_for(context.subject)
        questions = (
            *cues.guided_questions[:3],
            cues.focus(context.reason_family),
            *cues.guided_questions[3:],
        )
        return SupportPlan(
            scaffold_type="step_by_step_guidance",
            title_si="ප්‍රශ්නවලින් මඟ පෙන්වීම",
            stages=(target_stage(context, (), guidance=_answered(context, questions)),),
        )


def _answered(
    context: SupportBuildContext, questions: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """The first question is answered by the game's own prompt, the last by the real answer, and
    the ones between by the game's solving steps, in order."""

    record = context.failed_record
    prompt = str(context.source.support_activity(record)["prompt_si"])
    steps = [
        str(step)
        for step in context.source.support_solution(
            record, scaffold_type="step_by_step_guidance"
        ).get("steps_si", ())
    ]
    reveal = answer_reveal(context, record, "tint")
    answer = "පිළිතුර: " + "; ".join(reveal["lines"]) if reveal else (steps[-1] if steps else prompt)
    middle = questions[1:-1]
    middle_answers = [
        steps[min(index, len(steps) - 1)] if steps else prompt for index in range(len(middle))
    ]
    return (
        (questions[0], prompt),
        *zip(middle, middle_answers, strict=True),
        (questions[-1], answer),
    )

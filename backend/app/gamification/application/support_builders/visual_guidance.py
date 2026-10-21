"""Visual guidance: the failed game again, with its structure pointed out and no answer."""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportPlan,
    answer_tokens,
    target_stage,
    without_answer,
)
from app.gamification.application.support_builders.cues import cues_for


class VisualGuidanceBuilder:
    scaffold_type = "visual_guidance"

    def build(self, context: SupportBuildContext) -> SupportPlan:
        # The game's own visual cues, minus any line that would carry the scored answer.
        cues = context.source.support_solution(
            context.failed_record, scaffold_type="visual_guidance"
        ).get("steps_si", ())
        safe = without_answer(tuple(str(line) for line in cues), answer_tokens(context))
        return SupportPlan(
            scaffold_type="visual_guidance",
            title_si="දෘශ්‍ය මඟ පෙන්වීම",
            stages=(target_stage(context, cues_for(context.subject).visual_opening + safe),),
        )

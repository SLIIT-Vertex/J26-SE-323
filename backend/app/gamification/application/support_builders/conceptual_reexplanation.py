"""Conceptual re-explanation: the same game portrayed another way, then played again.

In mathematics the theory is expanded (idea, rule, reminder), the child's own problem is shown
from another angle (expanded form, repeated addition, a number line), obvious hints give the first
moves, and the board highlights the answer's parts. The final answer itself is not said.
"""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportPlan,
    skill_name,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for
from app.gamification.application.support_builders.teaching import item_lesson, lesson_block
from app.gamification.application.support_builders.theory import theory_for


class ConceptualReexplanationBuilder:
    scaffold_type = "conceptual_reexplanation"

    def build(self, context: SupportBuildContext) -> SupportPlan:
        lines = cues_for(context.subject).reexplanation(context.reason_family)
        stage = target_stage(context, lines)
        lesson = item_lesson(context, context.failed_record)
        if lesson is not None:
            name = skill_name(context, context.skill_id)
            stage = stage.with_lesson(
                lesson_block(
                    "අදහස වෙනත් ආකාරයකින්",
                    notes=((("අපි ඉගෙන ගන්නේ", name),) if name else ()) + theory_for(context.area_id),
                    another_view=lesson.another_view,
                    hints=lesson.hints,
                )
            )
        return SupportPlan(
            scaffold_type="conceptual_reexplanation",
            title_si="අදහස වෙනත් ආකාරයකින්",
            stages=(stage,),
        )

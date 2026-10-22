"""Prerequisite repair: an earlier skill of the same area, then back to the failed skill.

In mathematics the repair starts from what the child did: their failed answer is compared with the
right one to find the step that went wrong (a forgotten carry, a borrow taken the wrong way, a
misread Roman numeral), and the skill that repairs that step is practised. Without a diagnosis it
falls back to the skill just before this one in the area's order.
"""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SUPPORT_SEED_OFFSET,
    SupportBuildContext,
    SupportPlan,
    practice_record,
    practice_stage,
    skill_name,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for
from app.gamification.application.support_builders.teaching import (
    failed_diagnosis,
    item_lesson,
    lesson_block,
)


def earlier_skill(skills: list[str], skill_id: str) -> str | None:
    """The skill just before this one in the area's own teaching order."""

    position = skills.index(skill_id)
    return skills[position - 1] if position > 0 else None


class PrerequisiteRepairBuilder:
    scaffold_type = "prerequisite_repair"

    def build(self, context: SupportBuildContext) -> SupportPlan | None:
        skills = list(context.source.skills)
        diagnosis = failed_diagnosis(context)
        targeted = diagnosis.prerequisite_skill_id if diagnosis else None
        # The diagnosed skill only when it is a different skill this game can serve.
        if targeted == context.skill_id or targeted not in skills:
            targeted = None
        earlier = targeted or earlier_skill(skills, context.skill_id)
        if earlier is None:
            return None
        record = practice_record(
            context, context.source.support_item(earlier, context.seed + SUPPORT_SEED_OFFSET * 3)
        )
        cues = cues_for(context.subject)
        practice = practice_stage(context, record, cues.prerequisite_start)
        target = target_stage(context, cues.prerequisite_return)
        lesson = item_lesson(context, record)
        if lesson is not None:
            name = skill_name(context, earlier)
            practice = practice.with_lesson(
                lesson_block(
                    "වැරදුණු තැන හොයාගෙන මූලික කුසලතාව",
                    diagnosis=diagnosis,
                    notes=(("මූලික කුසලතාව", name),) if name else (),
                    steps=lesson.steps,
                )
            )
            own = item_lesson(context, context.failed_record)
            target = target_stage(
                context,
                cues.prerequisite_return + ("ඔබ දැන් කළ කුසලතාව මෙහි එක් පියවරකි.",),
            ).with_lesson(
                lesson_block(
                    "නැවත ඔබේ ප්‍රශ්නයට",
                    notes=(("මෙවර සැලකිලිමත් වන්න", diagnosis.went_wrong),) if diagnosis else (),
                    hints=own.hints if own else (),
                )
            )
        return SupportPlan(
            scaffold_type="prerequisite_repair",
            title_si="මූලික කුසලතාව නැවත බලමු",
            stages=(practice, target),
        )

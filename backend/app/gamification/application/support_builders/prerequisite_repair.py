"""Prerequisite repair: an earlier skill of the same area, then back to the failed skill."""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SUPPORT_SEED_OFFSET,
    SupportBuildContext,
    SupportPlan,
    practice_record,
    practice_stage,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for


def earlier_skill(skills: list[str], skill_id: str) -> str | None:
    """The skill just before this one in the area's own teaching order."""

    position = skills.index(skill_id)
    return skills[position - 1] if position > 0 else None


class PrerequisiteRepairBuilder:
    scaffold_type = "prerequisite_repair"

    def build(self, context: SupportBuildContext) -> SupportPlan | None:
        earlier = earlier_skill(list(context.source.skills), context.skill_id)
        if earlier is None:
            return None
        record = practice_record(
            context, context.source.support_item(earlier, context.seed + SUPPORT_SEED_OFFSET * 3)
        )
        cues = cues_for(context.subject)
        return SupportPlan(
            scaffold_type="prerequisite_repair",
            title_si="මූලික කුසලතාව නැවත බලමු",
            stages=(
                practice_stage(context, record, cues.prerequisite_start),
                target_stage(context, cues.prerequisite_return),
            ),
        )

"""Conceptual re-explanation: the same idea in other words, then the failed game again."""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportPlan,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for


class ConceptualReexplanationBuilder:
    scaffold_type = "conceptual_reexplanation"

    def build(self, context: SupportBuildContext) -> SupportPlan:
        lines = cues_for(context.subject).reexplanation(context.reason_family)
        return SupportPlan(
            scaffold_type="conceptual_reexplanation",
            title_si="අදහස වෙනත් ආකාරයකින්",
            stages=(target_stage(context, lines),),
        )

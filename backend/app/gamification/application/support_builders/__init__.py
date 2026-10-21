"""One small builder per help type. Adding a type means adding a builder and registering it."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.conceptual_reexplanation import (
    ConceptualReexplanationBuilder,
)
from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportBuilder,
    SupportItemSource,
    SupportPlan,
    SupportStage,
)
from app.gamification.application.support_builders.prerequisite_repair import (
    PrerequisiteRepairBuilder,
    earlier_skill,
)
from app.gamification.application.support_builders.simpler_same_game import (
    SimplerSameGameBuilder,
    difficulty,
)
from app.gamification.application.support_builders.step_by_step_guidance import (
    StepByStepGuidanceBuilder,
)
from app.gamification.application.support_builders.visual_guidance import VisualGuidanceBuilder
from app.gamification.application.support_builders.worked_parallel_example import (
    WorkedParallelExampleBuilder,
)
from app.gamification.content.support_types import SUPPORT_TYPES

SUPPORT_BUILDERS: Mapping[str, SupportBuilder] = {
    builder.scaffold_type: builder
    for builder in (
        VisualGuidanceBuilder(),
        StepByStepGuidanceBuilder(),
        WorkedParallelExampleBuilder(),
        SimplerSameGameBuilder(),
        PrerequisiteRepairBuilder(),
        ConceptualReexplanationBuilder(),
    )
}
assert set(SUPPORT_BUILDERS) == set(SUPPORT_TYPES)

__all__ = [
    "SUPPORT_BUILDERS",
    "SupportBuildContext",
    "SupportBuilder",
    "SupportItemSource",
    "SupportPlan",
    "SupportStage",
    "difficulty",
    "earlier_skill",
]

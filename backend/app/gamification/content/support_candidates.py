from app.gamification.content.records import (
    CANONICAL_SCAFFOLD_ARMS,
    ContentStatus,
    PilotContentPackage,
    ScaffoldDefinition,
    ScaffoldType,
)
from app.gamification.domain.types import ActionId, SupportActionType
from app.gamification.modeling.support_selection.contracts import SupportCandidate

# ADR-0008 maps each research arm to the existing support action vocabulary.
SCAFFOLD_ACTION_TYPES = {
    ScaffoldType.VISUAL_GUIDANCE: SupportActionType.VISUAL_GUIDANCE,
    ScaffoldType.WORKED_EXAMPLE: SupportActionType.SIMILAR_WORKED_EXAMPLE,
    ScaffoldType.STEP_BY_STEP_GUIDANCE: SupportActionType.GUIDED_STEPS,
    ScaffoldType.CONCEPT_REMINDER: SupportActionType.CONCEPTUAL_HINT,
}


def scaffold_support_candidate(scaffold: ScaffoldDefinition) -> SupportCandidate:
    return SupportCandidate(
        action_id=ActionId(scaffold.scaffold_id),
        action_type=SCAFFOLD_ACTION_TYPES[scaffold.scaffold_type],
        languages=(scaffold.language,),
        skill_ids=scaffold.skill_ids,
        misconception_codes=scaffold.target_misconception_ids,
        approved=scaffold.status is ContentStatus.APPROVED,
    )


def skill_support_candidates(
    package: PilotContentPackage, skill_id: str
) -> tuple[SupportCandidate, ...]:
    """Bandit arms for one skill: the canonical A1-A3 scaffolds, in a stable order."""
    arms = [
        scaffold
        for scaffold in package.scaffolds_for_skill(skill_id)
        if scaffold.scaffold_type in CANONICAL_SCAFFOLD_ARMS
    ]
    return tuple(
        scaffold_support_candidate(scaffold)
        for scaffold in sorted(
            arms, key=lambda s: (CANONICAL_SCAFFOLD_ARMS.index(s.scaffold_type), s.scaffold_id)
        )
    )

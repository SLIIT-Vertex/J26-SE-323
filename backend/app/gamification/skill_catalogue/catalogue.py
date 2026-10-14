from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.gamification.skill_catalogue.contracts import (
    ReviewStatus,
    SkillBinding,
    SkillReview,
)


@dataclass(frozen=True, slots=True)
class SkillCatalogue:
    """Validated skill reviews and candidate bindings, independent of persistence."""

    taxonomy_version: str
    skills: Mapping[str, SkillReview]
    bindings: Mapping[str, SkillBinding]

    @classmethod
    def build(
        cls,
        reviews: Sequence[SkillReview],
        bindings: Sequence[SkillBinding],
        *,
        taxonomy_version: str,
    ) -> "SkillCatalogue":
        skills = {review.skill_code: review for review in reviews}
        if len(skills) != len(reviews):
            raise ValueError("skill codes must be unique")
        indices = {review.stable_index for review in reviews}
        if len(indices) != len(reviews):
            raise ValueError("stable skill indices must be unique")
        if any(review.taxonomy_version != taxonomy_version for review in reviews):
            raise ValueError("every skill must use the catalogue taxonomy version")
        binding_map = {binding.skill_candidate_id: binding for binding in bindings}
        if len(binding_map) != len(bindings):
            raise ValueError("skill candidate bindings must be unique")
        for binding in bindings:
            if binding.mapping_version != taxonomy_version:
                raise ValueError("every binding must use the catalogue taxonomy version")
            if binding.knowledge_tracing_skill_id not in skills:
                raise ValueError("binding references an unknown knowledge-tracing skill")
        return cls(taxonomy_version, skills, binding_map)

    def resolve_candidate(self, skill_candidate_id: str, *, allow_draft: bool = False) -> str:
        binding = self.bindings.get(skill_candidate_id)
        if binding is None:
            raise LookupError(f"no skill binding exists for {skill_candidate_id}")
        skill = self.skills[binding.knowledge_tracing_skill_id]
        approved = (
            binding.status is ReviewStatus.APPROVED and skill.status is ReviewStatus.APPROVED
        )
        development_draft = (
            allow_draft
            and binding.status is ReviewStatus.DRAFT
            and skill.status is ReviewStatus.DRAFT
        )
        if not approved and not development_draft:
            raise PermissionError("skill and binding must be approved, or both draft in development")
        return skill.skill_code

    def bind_feature_values(
        self, features: Mapping[str, object], *, allow_draft: bool = False
    ) -> dict[str, object]:
        candidate_id = str(features.get("skill_id", ""))
        bound = dict(features)
        bound["source_skill_candidate_id"] = candidate_id
        bound["skill_id"] = self.resolve_candidate(candidate_id, allow_draft=allow_draft)
        bound["skill_taxonomy_version"] = self.taxonomy_version
        return bound

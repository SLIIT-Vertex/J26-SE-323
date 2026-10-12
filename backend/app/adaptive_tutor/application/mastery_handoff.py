from collections.abc import Collection
from uuid import UUID

from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.domain import SkillMappingStatus
from app.knowledge_tracing.application.mastery import (
    MasteryRetrievalRequest,
    validate_mastery_request_against_taxonomy,
)


def mastery_request_for_mapping(
    learner_id: UUID,
    mapping: SkillMappingResult,
    valid_skill_ids: Collection[str],
) -> MasteryRetrievalRequest | None:
    """Return a validated request only for a confirmed skill mapping."""

    if mapping.status is not SkillMappingStatus.MATCHED:
        return None

    assert mapping.skill_id is not None
    request = MasteryRetrievalRequest(learner_id=learner_id, skill_id=mapping.skill_id)
    validate_mastery_request_against_taxonomy(request, valid_skill_ids)
    return request

from collections.abc import Collection

from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.domain import SkillMappingStatus
from app.curriculum.application import (
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumRetriever,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    Grade,
    IngestionStatus,
    MetadataStatus,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
    validate_curriculum_skill_ids,
    validate_retrieval_result_for_request,
)

__all__ = [
    "CurriculumChunk",
    "CurriculumRetrievalRequest",
    "CurriculumRetrievalResult",
    "CurriculumRetrievalStatus",
    "CurriculumRetriever",
    "CurriculumReviewStatus",
    "CurriculumSourceRecord",
    "IngestionStatus",
    "MetadataStatus",
    "RetrievedCurriculumPassage",
    "UsageRightsStatus",
    "curriculum_request_for_mapping",
    "validate_curriculum_skill_ids",
    "validate_retrieval_result_for_request",
]


def curriculum_request_for_mapping(
    learner_question: str,
    mapping: SkillMappingResult,
    grade: Grade,
    valid_skill_ids: Collection[str],
    requested_language: str | None = None,
    limit: int = 5,
) -> CurriculumRetrievalRequest | None:
    """Create a retrieval request only for a confirmed, taxonomy-valid mapping."""

    if mapping.status is not SkillMappingStatus.MATCHED:
        return None

    assert mapping.skill_id is not None
    request = CurriculumRetrievalRequest(
        learner_question=learner_question,
        skill_id=mapping.skill_id,
        grade=grade,
        requested_language=requested_language,
        required_language=requested_language,
        limit=limit,
    )
    validate_curriculum_skill_ids(request, valid_skill_ids)
    return request

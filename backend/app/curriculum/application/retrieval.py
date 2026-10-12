from collections.abc import Collection
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
Grade = Literal[4, 5]
PositivePage = Annotated[int, Field(strict=True, ge=1)]
RetrievalLimit = Annotated[int, Field(strict=True, ge=1, le=10)]
RetrievalScore = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class MetadataStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    UNKNOWN = "UNKNOWN"


class IngestionStatus(StrEnum):
    NOT_INGESTED = "NOT_INGESTED"
    READY = "READY"
    INGESTED = "INGESTED"
    FAILED = "FAILED"


class CurriculumReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UsageRightsStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"


class CurriculumRetrievalStatus(StrEnum):
    FOUND = "FOUND"
    NO_RELEVANT_PASSAGES = "NO_RELEVANT_PASSAGES"
    NO_APPROVED_SOURCE = "NO_APPROVED_SOURCE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class CurriculumSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    title: NonBlankText
    publisher_authority: NonBlankText | None = None
    grade: Grade | None = None
    subject: NonBlankText | None = None
    language: NonBlankText | None = None
    source_type: NonBlankText
    source_location: NonBlankText | None = None
    source_version: NonBlankText | None = None
    metadata_status: MetadataStatus
    ingestion_status: IngestionStatus
    review_status: CurriculumReviewStatus
    usage_rights_status: UsageRightsStatus


class CurriculumChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: NonBlankText
    source_id: NonBlankText
    source_version: NonBlankText
    content: NonBlankText
    grade: Grade
    subject: NonBlankText
    language: NonBlankText
    skill_ids: tuple[NonBlankText, ...] = Field(min_length=1)
    page_number: PositivePage | None = None
    section_locator: NonBlankText | None = None
    review_status: CurriculumReviewStatus

    @model_validator(mode="after")
    def validate_skill_ids(self) -> Self:
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("chunk skill IDs must be unique")
        return self


class CurriculumRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_question: NonBlankText
    skill_id: NonBlankText
    grade: Grade
    requested_language: NonBlankText | None = None
    limit: RetrievalLimit = 5


class RetrievedCurriculumPassage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: CurriculumChunk
    source: CurriculumSourceRecord
    score: RetrievalScore | None = None

    @model_validator(mode="after")
    def validate_traceability_and_trust(self) -> Self:
        if self.chunk.source_id != self.source.source_id:
            raise ValueError("chunk source_id does not match source reference")
        if self.source.source_version != self.chunk.source_version:
            raise ValueError("chunk source_version does not match source reference")
        if self.source.metadata_status is not MetadataStatus.VERIFIED:
            raise ValueError("retrieved source metadata must be verified")
        if self.source.ingestion_status is not IngestionStatus.INGESTED:
            raise ValueError("retrieved source must be ingested")
        if self.source.review_status is not CurriculumReviewStatus.APPROVED:
            raise ValueError("retrieved source must be approved")
        if self.chunk.review_status is not CurriculumReviewStatus.APPROVED:
            raise ValueError("retrieved chunk must be approved")
        if self.source.usage_rights_status is not UsageRightsStatus.PERMITTED:
            raise ValueError("retrieved source usage rights must be permitted")
        return self


class CurriculumRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CurriculumRetrievalStatus
    passages: tuple[RetrievedCurriculumPassage, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is CurriculumRetrievalStatus.FOUND and not self.passages:
            raise ValueError("FOUND requires at least one passage")
        if self.status is not CurriculumRetrievalStatus.FOUND and self.passages:
            raise ValueError("only FOUND may contain passages")
        return self


class CurriculumRetriever(Protocol):
    def retrieve(self, request: CurriculumRetrievalRequest) -> CurriculumRetrievalResult: ...


def validate_curriculum_skill_ids(
    contract: CurriculumChunk | CurriculumRetrievalRequest,
    valid_skill_ids: Collection[str],
) -> None:
    referenced_ids = contract.skill_ids if isinstance(contract, CurriculumChunk) else (contract.skill_id,)
    unknown_ids = sorted(set(referenced_ids) - set(valid_skill_ids))
    if unknown_ids:
        raise ValueError(f"unknown skill IDs: {', '.join(unknown_ids)}")


def validate_retrieval_result_for_request(
    request: CurriculumRetrievalRequest,
    result: CurriculumRetrievalResult,
) -> None:
    if len(result.passages) > request.limit:
        raise ValueError("retrieval result exceeds requested limit")
    for passage in result.passages:
        if passage.chunk.grade != request.grade:
            raise ValueError("retrieved passage grade does not match request")
        if request.skill_id not in passage.chunk.skill_ids:
            raise ValueError("retrieved passage does not include requested skill")

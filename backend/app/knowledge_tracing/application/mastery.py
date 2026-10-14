from collections.abc import Collection
from enum import StrEnum
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SkillId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
MasteryValue = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]


class MasteryStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_FOUND = "NOT_FOUND"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class MasteryRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: SkillId


class MasteryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: SkillId
    status: MasteryStatus
    mastery: MasteryValue | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is MasteryStatus.AVAILABLE and self.mastery is None:
            raise ValueError("AVAILABLE requires mastery")
        if self.status is not MasteryStatus.AVAILABLE and self.mastery is not None:
            raise ValueError("only AVAILABLE may contain mastery")
        return self


class MasteryProvider(Protocol):
    def get_mastery(self, request: MasteryRetrievalRequest) -> MasteryResult: ...


def validate_mastery_request_against_taxonomy(
    request: MasteryRetrievalRequest,
    valid_skill_ids: Collection[str],
) -> None:
    if request.skill_id not in valid_skill_ids:
        raise ValueError(f"unknown skill ID: {request.skill_id}")


def validate_mastery_result_identity(
    request: MasteryRetrievalRequest,
    result: MasteryResult,
) -> None:
    if (result.learner_id, result.skill_id) != (request.learner_id, request.skill_id):
        raise ValueError("mastery result identity does not match request")

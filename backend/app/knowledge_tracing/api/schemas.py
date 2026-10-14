from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AttemptCreate(BaseModel):
    """One answer given in the game. The server decides source and penalty."""

    model_config = ConfigDict(extra="forbid")

    learner_id: UUID
    question_id: str = Field(min_length=1, max_length=16)
    language: Literal["si", "ta"]
    correct: bool
    time_ms: int | None = Field(default=None, ge=0, le=600_000)
    hints: int | None = Field(default=None, ge=0, le=10)
    answered_at: AwareDatetime


class AttemptCreated(BaseModel):
    attempt_id: int

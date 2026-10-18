from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class AttemptCreate(BaseModel):
    """One answer given in the game. The server decides source and penalty."""

    model_config = ConfigDict(extra="forbid")

    learner_id: UUID
    # Give EITHER a question of the paper question bank, OR (for a game with its own questions)
    # the skill the answer belongs to and its difficulty. Never both, never neither.
    question_id: str | None = Field(default=None, min_length=1, max_length=16)
    skill_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}-[A-Z]{3}$")
    difficulty: Literal["easy", "medium", "hard"] | None = None
    language: Literal["si", "ta"]
    correct: bool
    time_ms: int | None = Field(default=None, ge=0, le=600_000)
    hints: int | None = Field(default=None, ge=0, le=10)
    answered_at: AwareDatetime

    @model_validator(mode="after")
    def one_form_only(self) -> "AttemptCreate":
        with_skill = self.skill_code is not None or self.difficulty is not None
        if (self.question_id is not None) == with_skill:
            raise ValueError("give a question_id, or a skill_code together with a difficulty")
        if with_skill and (self.skill_code is None or self.difficulty is None):
            raise ValueError("a skill_code needs a difficulty, and a difficulty needs a skill_code")
        return self


class AttemptCreated(BaseModel):
    attempt_id: int

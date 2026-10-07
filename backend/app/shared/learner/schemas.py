from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LearnerCreate(BaseModel):
    grade: Literal[4, 5]
    preferred_language: str = Field(min_length=2, max_length=10)


class LearnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grade: int
    preferred_language: str
    created_at: datetime
    updated_at: datetime

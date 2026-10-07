from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Learner:
    id: UUID
    grade: int
    preferred_language: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


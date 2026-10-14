from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

DEFINITION = "Chance of answering a medium-difficulty paper question correctly"


@dataclass(frozen=True, slots=True)
class SkillEstimate:
    code: str
    mastery: float | None  # None: fewer than the minimum attempts, so the model has no basis
    attempts: int


@dataclass(frozen=True, slots=True)
class MasterySnapshot:
    id: int | None
    learner_id: UUID
    computed_at: datetime
    model_version: str
    n_attempts: int
    skills: tuple[SkillEstimate, ...]

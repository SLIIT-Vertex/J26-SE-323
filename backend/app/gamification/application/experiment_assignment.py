"""Learner-level arm assignment. The arm is recorded before any outcome."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.gamification.application.errors import PlayError
from app.gamification.application.evaluation_protocol import (
    FrozenProtocol,
    decision_mode_for_arm,
)
from app.gamification.domain.types import DecisionMode


@dataclass(frozen=True, slots=True)
class ExperimentAssignment:
    experiment_id: UUID
    learner_id: UUID
    arm_key: str
    decision_mode: DecisionMode
    seed: int
    assigned_at: datetime


class AssignmentBook:
    """Process-local assignments. The SQL tables are the durable copy."""

    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, UUID], ExperimentAssignment] = {}
        self._outcomes: set[tuple[UUID, UUID]] = set()

    def get(self, experiment_id: UUID, learner_id: UUID) -> ExperimentAssignment | None:
        return self._rows.get((experiment_id, learner_id))

    def for_learner(self, learner_id: UUID) -> ExperimentAssignment | None:
        matches = [row for (_, owner), row in self._rows.items() if owner == learner_id]
        if not matches:
            return None
        return max(matches, key=lambda row: row.assigned_at)

    def note_outcome(self, experiment_id: UUID, learner_id: UUID) -> None:
        self._outcomes.add((experiment_id, learner_id))

    def has_outcome(self, experiment_id: UUID, learner_id: UUID) -> bool:
        return (experiment_id, learner_id) in self._outcomes

    def save(self, assignment: ExperimentAssignment) -> None:
        self._rows[(assignment.experiment_id, assignment.learner_id)] = assignment


def allocate_arm(learner_id: UUID, seed: int, arms: tuple[str, ...]) -> str:
    digest = hashlib.sha256(f"{learner_id}:{seed}".encode()).digest()
    return arms[int.from_bytes(digest[:8], "big") % len(arms)]


class AssignExperimentArm:
    def __init__(self, *, protocol: FrozenProtocol, book: AssignmentBook) -> None:
        self._protocol = protocol
        self._book = book

    def execute(
        self,
        *,
        experiment_id: UUID,
        learner_id: UUID,
        seed: int,
        protocol_hash: str,
        at: datetime,
    ) -> ExperimentAssignment:
        self._protocol.require_hash(protocol_hash)
        arms = tuple(str(arm["arm_key"]) for arm in self._protocol.document["arms"])  # type: ignore[index]
        chosen = allocate_arm(learner_id, seed, arms)
        existing = self._book.get(experiment_id, learner_id)
        if existing is not None:
            if existing.arm_key != chosen and self._book.has_outcome(experiment_id, learner_id):
                raise PlayError("ASSIGNMENT_LOCKED", 409)
            return existing
        assignment = ExperimentAssignment(
            experiment_id=experiment_id,
            learner_id=learner_id,
            arm_key=chosen,
            decision_mode=decision_mode_for_arm(chosen),
            seed=seed,
            assigned_at=at,
        )
        self._book.save(assignment)
        return assignment

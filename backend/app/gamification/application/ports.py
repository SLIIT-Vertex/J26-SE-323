from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.gamification.application.records import (
    AuditEvent,
    ConsentDecision,
    CurriculumEvidence,
    FeatureSnapshotRecord,
    LearnerStateEvidence,
    MasteryEvidence,
    ModelArtifact,
    NormalizedAttempt,
    PolicyDecisionRecord,
    TutorSupportRequest,
    TutorSupportResult,
)
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ModelId,
    PolicyDecisionId,
    SkillId,
)


class KnowledgeTracingGateway(Protocol):
    def get_mastery(self, *, learner_id: UUID, skill_id: SkillId) -> MasteryEvidence | None: ...

    def record_attempt(self, attempt: NormalizedAttempt) -> None: ...


class LearnerStateGateway(Protocol):
    def get_support_evidence(
        self, *, learner_id: UUID, observed_no_earlier_than: datetime
    ) -> LearnerStateEvidence | None: ...


class TutorSupportGateway(Protocol):
    def create_verified_support(self, request: TutorSupportRequest) -> TutorSupportResult: ...


class ConsentGateway(Protocol):
    def get_consent(self, *, learner_id: UUID, purpose: str) -> ConsentDecision: ...


class ModelRegistry(Protocol):
    def get_approved(self, model_id: ModelId) -> ModelArtifact | None: ...


class FeatureSnapshotStore(Protocol):
    def add(self, snapshot: FeatureSnapshotRecord) -> None: ...

    def get(self, snapshot_id: FeatureSnapshotId) -> FeatureSnapshotRecord | None: ...


class PolicyDecisionStore(Protocol):
    def add(self, decision: PolicyDecisionRecord) -> None: ...

    def get(self, decision_id: PolicyDecisionId) -> PolicyDecisionRecord | None: ...


class CurriculumRetriever(Protocol):
    def find_approved(
        self, *, skill_id: SkillId, language: str, limit: int
    ) -> tuple[CurriculumEvidence, ...]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class AuditOutput(Protocol):
    def write(self, event: AuditEvent) -> None: ...


from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.gamification.application.records import (
    AuditEvent,
    ConsentDecision,
    CurriculumEvidence,
    FeatureSnapshotRecord,
    LearnerStateEvidence,
    SkillMasteryEvidence,
    ModelArtifact,
    GamificationAttempt,
    PolicyDecisionRecord,
    SupportAssetRequest,
    SupportAssetResult,
)
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ItemId,
    ModelId,
    PolicyDecisionId,
    SkillId,
)


class LearningRecordStore(Protocol):
    """Gamification-owned mastery and attempt storage."""

    def get_mastery(
        self, *, learner_id: UUID, skill_id: SkillId
    ) -> SkillMasteryEvidence | None: ...

    def record_attempt(self, attempt: GamificationAttempt) -> None: ...

    def seen_item_ids(self, *, learner_id: UUID) -> tuple[ItemId, ...]: ...


class LearnerStateGateway(Protocol):
    def get_support_evidence(
        self, *, learner_id: UUID, observed_no_earlier_than: datetime
    ) -> LearnerStateEvidence | None: ...


class SupportAssetProvider(Protocol):
    """Gamification-owned support authoring and retrieval boundary."""

    def create_verified_support(self, request: SupportAssetRequest) -> SupportAssetResult: ...


class ConsentStore(Protocol):
    """Gamification-owned purpose-specific consent decisions."""
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


class UnitOfWork(Protocol):
    """Transaction boundary. Adapters live in infrastructure; this protocol does not."""

    learning_records: LearningRecordStore
    audit: AuditOutput

    def begin(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


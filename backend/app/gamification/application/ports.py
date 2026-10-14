from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.gamification.application.records import (
    AuditEvent,
    ConsentDecision,
    FeatureSnapshotRecord,
    GamificationAttempt,
    LearnerEvidenceEvent,
    LearnerSkillSummary,
    LearnerStateEvidence,
    ModelArtifact,
    PolicyDecisionRecord,
    SkillMasteryEvidence,
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
    """Gamification-owned attempt storage and the derived skill-summary read model."""

    def get_skill_summary(
        self, *, learner_id: UUID, skill_id: SkillId
    ) -> LearnerSkillSummary | None: ...

    def record_attempt(self, attempt: GamificationAttempt) -> None: ...

    def seen_item_ids(self, *, learner_id: UUID) -> tuple[ItemId, ...]: ...


class SkillSummaryStore(Protocol):
    def get(self, *, learner_id: UUID, skill_id: str) -> LearnerSkillSummary | None: ...

    def save(self, summary: LearnerSkillSummary) -> None: ...


class MasteryEvidenceGateway(Protocol):
    """Read Knowledge Tracing mastery. ``None`` is missingness, never an episode failure."""

    def get_mastery(
        self, *, learner_id: UUID, skill_id: SkillId
    ) -> SkillMasteryEvidence | None: ...


class LearnerStateGateway(Protocol):
    def get_support_evidence(
        self,
        *,
        learner_id: UUID,
        skill_id: SkillId,
        observed_no_earlier_than: datetime,
    ) -> LearnerStateEvidence | None: ...


class LearnerEvidencePublisher(Protocol):
    def publish(self, event: LearnerEvidenceEvent) -> None: ...


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


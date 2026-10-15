"""Use-case ports for adaptive gamified learning."""

from app.gamification.application.ports import (
    AuditOutput,
    Clock,
    ConsentStore,
    FeatureSnapshotStore,
    LearnerEvidencePublisher,
    LearnerStateGateway,
    LearningRecordStore,
    MasteryEvidenceGateway,
    ModelRegistry,
    PolicyDecisionStore,
    SkillSummaryStore,
    SupportAssetProvider,
)

__all__ = [
    "AuditOutput",
    "Clock",
    "ConsentStore",
    "FeatureSnapshotStore",
    "LearnerEvidencePublisher",
    "LearnerStateGateway",
    "LearningRecordStore",
    "MasteryEvidenceGateway",
    "ModelRegistry",
    "PolicyDecisionStore",
    "SkillSummaryStore",
    "SupportAssetProvider",
]

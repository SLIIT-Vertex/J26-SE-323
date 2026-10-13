"""Use-case ports for adaptive gamified learning."""

from app.gamification.application.ports import (
    AuditOutput,
    Clock,
    ConsentGateway,
    CurriculumRetriever,
    FeatureSnapshotStore,
    KnowledgeTracingGateway,
    LearnerStateGateway,
    ModelRegistry,
    PolicyDecisionStore,
    TutorSupportGateway,
)

__all__ = [
    "AuditOutput",
    "Clock",
    "ConsentGateway",
    "CurriculumRetriever",
    "FeatureSnapshotStore",
    "KnowledgeTracingGateway",
    "LearnerStateGateway",
    "ModelRegistry",
    "PolicyDecisionStore",
    "TutorSupportGateway",
]

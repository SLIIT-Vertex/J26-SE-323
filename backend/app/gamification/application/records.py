from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from app.gamification.domain.types import (
    ActionId,
    CatalogueVersion,
    ContractVersion,
    DecisionMode,
    FeatureSnapshotId,
    ItemId,
    ModelId,
    PolicyDecisionId,
    ProtocolVersion,
    SkillId,
    SupportActionType,
    TaxonomyVersion,
)


@dataclass(frozen=True, slots=True)
class MasteryEvidence:
    learner_id: UUID
    skill_id: SkillId
    mastery_probability: float
    uncertainty: float
    model_version: str
    contract_version: ContractVersion
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedAttempt:
    attempt_id: UUID
    learner_id: UUID
    item_id: ItemId
    skill_ids: tuple[SkillId, ...]
    language: str
    correct: bool
    score: float
    response_time_ms: int | None
    support_exposure: str
    attempted_at: datetime
    contract_version: ContractVersion


@dataclass(frozen=True, slots=True)
class LearnerStateEvidence:
    learner_id: UUID
    support_need: float
    confidence: float
    reliability: float
    observed_at: datetime
    contract_version: ContractVersion


@dataclass(frozen=True, slots=True)
class TutorSupportRequest:
    learner_id: UUID
    skill_id: SkillId
    action_type: SupportActionType
    misconception_probabilities: Mapping[str, float]
    approved_evidence_ids: tuple[str, ...]
    prohibited_content: tuple[str, ...]
    contract_version: ContractVersion

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "misconception_probabilities",
            MappingProxyType(dict(self.misconception_probabilities)),
        )


@dataclass(frozen=True, slots=True)
class TutorSupportResult:
    support_asset_id: str
    content_version: str
    verified: bool
    reason_codes: tuple[str, ...]
    contract_version: ContractVersion


@dataclass(frozen=True, slots=True)
class ConsentDecision:
    learner_id: UUID
    purpose: str
    granted: bool
    consent_version: str
    decided_at: datetime
    expires_at: datetime | None
    contract_version: ContractVersion


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    model_id: ModelId
    model_version: str
    artifact_digest: str
    approved: bool
    registered_at: datetime


@dataclass(frozen=True, slots=True)
class FeatureSnapshotRecord:
    snapshot_id: FeatureSnapshotId
    learner_id: UUID
    skill_id: SkillId
    captured_at: datetime
    protocol_version: ProtocolVersion
    taxonomy_version: TaxonomyVersion
    feature_definition_version: str
    values: Mapping[str, float | int | bool | str | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class PolicyCandidateRecord:
    action_id: ActionId
    action_type: SupportActionType
    propensity: float
    eligible: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyDecisionRecord:
    decision_id: PolicyDecisionId
    feature_snapshot_id: FeatureSnapshotId
    selected_action_id: ActionId
    mode: DecisionMode
    policy_version: str
    support_catalogue_version: CatalogueVersion
    candidates: tuple[PolicyCandidateRecord, ...]
    reason_codes: tuple[str, ...]
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class CurriculumEvidence:
    evidence_id: str
    skill_id: SkillId
    source_version: str
    content_hash: str
    approved: bool
    language: str


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    subject_id: str
    occurred_at: datetime
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str | int | float | bool | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


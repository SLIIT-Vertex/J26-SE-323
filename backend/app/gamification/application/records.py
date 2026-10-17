from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.types import (
    ActionId,
    CatalogueVersion,
    ContractVersion,
    DecisionMode,
    EpisodeId,
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
class SkillMasteryEvidence:
    """Knowledge Tracing mastery for the Universal parent of a gamification skill.

    ``uncertainty`` and ``observed_at`` stay empty when the published mastery result does not
    carry them. This is not a gamification-owned mastery estimate.
    """

    learner_id: UUID
    skill_id: SkillId
    universal_skill_id: str
    mastery_probability: float
    model_version: str
    contract_version: ContractVersion
    uncertainty: float | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GamificationAttempt:
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
    skill_id: SkillId
    universal_skill_id: str
    observed_at: datetime
    contract_version: ContractVersion
    support_need: float | None = None
    confidence: float | None = None
    reliability: float | None = None
    uncertain: bool = False
    recommended_action: str | None = None


@dataclass(frozen=True, slots=True)
class SupportAssetRequest:
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
class SupportAssetResult:
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
    missingness: Mapping[str, bool] = field(default_factory=dict)
    source_as_of: Mapping[str, str] = field(default_factory=dict)
    purpose: str = "policy_decision"

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "missingness", MappingProxyType(dict(self.missingness)))
        object.__setattr__(self, "source_as_of", MappingProxyType(dict(self.source_as_of)))


@dataclass(frozen=True, slots=True)
class PolicyCandidateRecord:
    action_id: ActionId
    action_type: SupportActionType
    propensity: float
    eligible: bool
    reason_codes: tuple[str, ...]
    predicted_reward: float | None = None
    uncertainty: float | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecisionRecord:
    decision_id: PolicyDecisionId
    episode_id: EpisodeId
    feature_snapshot_id: FeatureSnapshotId
    selected_action_id: ActionId
    mode: DecisionMode
    policy_version: str
    support_catalogue_version: CatalogueVersion
    candidates: tuple[PolicyCandidateRecord, ...]
    reason_codes: tuple[str, ...]
    decided_at: datetime
    random_seed: int | None = None


@dataclass(frozen=True, slots=True)
class LearnerSkillSummary:
    """Derived report counts. Not a mastery model."""

    learner_id: UUID
    skill_id: str
    unsupported_attempts: int
    supported_attempts: int
    independent_accuracy: float | None
    supported_accuracy: float | None
    mean_independence_gain: float | None
    support_dependency_index: float | None
    valid_outcome_count: int
    last_practiced_at: datetime | None
    summary_version: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LearnerEvidenceEvent:
    """Outbound learner-profile event. Payloads carry codes and scores, never item text."""

    event_type: str
    learner_id: UUID
    skill_id: str
    universal_skill_id: str
    timestamp: datetime
    model_version: str
    confidence: float | None
    evidence_reference: Mapping[str, str]
    payload: Mapping[str, float | int | bool | str | None]
    contract_version: str = "gamification-learner-evidence-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_reference", MappingProxyType(dict(self.evidence_reference)))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @property
    def idempotency_key(self) -> str:
        attempt_id = self.evidence_reference.get("attempt_id")
        identity = attempt_id or self.evidence_reference["episode_id"]
        return f"{identity}:{self.event_type}"

    def as_contract(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "event_type": self.event_type,
            "learner_id": self.learner_id,
            "skill_id": self.skill_id,
            "universal_skill_id": self.universal_skill_id,
            "timestamp": self.timestamp,
            "source_component": "gamification",
            "model_version": self.model_version,
            "confidence": self.confidence,
            "evidence_reference": dict(self.evidence_reference),
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    subject_id: str
    occurred_at: datetime
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str | int | float | bool | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MisconceptionBeliefEvidence:
    misconception_code: str
    probability: float
    rank: int


@dataclass(frozen=True, slots=True)
class SupportExposureEvidence:
    exposure_id: UUID
    action_id: ActionId
    delivery_status: str
    presented_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    render_version: str
    maximum_duration_ms: int | None = None
    maximum_number_of_steps: int | None = None


@dataclass(frozen=True, slots=True)
class VerificationPairEvidence:
    pair_id: UUID
    baseline_item_id: ItemId
    baseline_item_version: str
    verification_item_id: ItemId
    verification_item_version: str
    equivalence_version: str
    review_status: str
    unseen_verification_item: bool = True
    answer_overlap: float = 0.0


@dataclass(frozen=True, slots=True)
class IndependenceOutcomeEvidence:
    outcome_id: UUID
    validity: str
    baseline_score: float
    verification_score: float
    raw_independence_gain: float | None
    invalid_reason: str | None
    formula_version: str
    calculated_at: datetime
    misconception_resolution: float | None = None


@dataclass(frozen=True, slots=True)
class ItemResponseEvidence:
    response_id: UUID
    item_id: ItemId
    item_version: str
    phase: str
    support_state: str
    answer: Mapping[str, object]
    is_correct: bool
    score: float
    submitted_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer", MappingProxyType(dict(self.answer)))


@dataclass(frozen=True, slots=True)
class EpisodeEvidenceBundle:
    episode: AdaptiveEpisode
    baseline_response: ItemResponseEvidence | None
    verification_response: ItemResponseEvidence | None
    feature_snapshot: FeatureSnapshotRecord | None
    misconception_beliefs: tuple[MisconceptionBeliefEvidence, ...]
    policy_decision: PolicyDecisionRecord | None
    support_exposures: tuple[SupportExposureEvidence, ...]
    verification_pair: VerificationPairEvidence | None
    outcome: IndependenceOutcomeEvidence | None


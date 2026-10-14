from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.gamification.application.records import (
    FeatureSnapshotRecord,
    IndependenceOutcomeEvidence,
    ItemResponseEvidence,
    PolicyDecisionRecord,
    SupportExposureEvidence,
    VerificationPairEvidence,
)
from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.types import DecisionMode
from app.gamification.modeling.shared.contracts import MisconceptionDistribution


@dataclass(frozen=True, slots=True)
class SupportExposureRecord:
    evidence: SupportExposureEvidence
    maximum_duration_ms: int
    maximum_number_of_steps: int
    interaction_count: int


@dataclass(frozen=True, slots=True)
class EpisodeState:
    episode: AdaptiveEpisode
    session_id: UUID
    taxonomy_version: str
    language: str
    trigger_type: str
    trigger_reasons: tuple[str, ...] = ()
    trigger_missing_inputs: tuple[str, ...] = ()
    trigger_skipped_rules: tuple[str, ...] = ()
    trigger_config_version: str | None = None
    baseline_template: str | None = None
    template_reason: str | None = None
    variation_seed: int | None = None
    baseline_response: ItemResponseEvidence | None = None
    baseline_response_time_ms: int | None = None
    learner_requested_help: bool | None = None
    verification_response: ItemResponseEvidence | None = None
    supported_responses: tuple[ItemResponseEvidence, ...] = ()
    feature_snapshot: FeatureSnapshotRecord | None = None
    policy_context_snapshot: FeatureSnapshotRecord | None = None
    belief: MisconceptionDistribution | None = None
    decision: PolicyDecisionRecord | None = None
    exposures: tuple[SupportExposureRecord, ...] = ()
    withdrawn_at: datetime | None = None
    verification_pair: VerificationPairEvidence | None = None
    outcome: IndependenceOutcomeEvidence | None = None
    decision_mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE
    revision: int = 1
    closed_at: datetime | None = None

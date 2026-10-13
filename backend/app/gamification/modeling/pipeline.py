from dataclasses import dataclass
from datetime import datetime

from app.gamification.application.records import (
    FeatureSnapshotRecord,
    PolicyDecisionRecord,
    SupportExposureEvidence,
)
from app.gamification.domain.types import CatalogueVersion, DecisionMode, EpisodeId
from app.gamification.modeling.features import DecisionFeatureInput, FeatureBuilder
from app.gamification.modeling.independence import (
    IndependenceGainInput,
    IndependenceGainResult,
    calculate_independence_gain,
)
from app.gamification.modeling.misconception import (
    MisconceptionDistribution,
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.policy import LearnedPolicy, SafeSupportPolicy, SupportCandidate


@dataclass(frozen=True, slots=True)
class EpisodeModelDecision:
    feature_snapshot: FeatureSnapshotRecord
    misconception: MisconceptionDistribution
    policy: PolicyDecisionRecord


@dataclass(frozen=True, slots=True)
class EpisodeModelCompletion:
    decision: EpisodeModelDecision
    support_exposure: SupportExposureEvidence
    independence_outcome: IndependenceGainResult


class ThreeModelPipeline:
    """Coordinates the three models without persistence or framework dependencies."""

    def __init__(
        self,
        *,
        misconception_model: ProbabilisticMisconceptionModel,
        support_catalogue_version: CatalogueVersion,
        minimum_learned_evidence: int = 20,
    ) -> None:
        self._features = FeatureBuilder()
        self._misconception = misconception_model
        self._policy = SafeSupportPolicy(
            catalogue_version=support_catalogue_version,
            minimum_learned_evidence=minimum_learned_evidence,
        )

    def decide(
        self,
        *,
        episode_id: EpisodeId,
        features: DecisionFeatureInput,
        candidates: tuple[SupportCandidate, ...],
        language: str,
        seed: int,
        decided_at: datetime,
        mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE,
        learned_policy: LearnedPolicy | None = None,
        evidence_count: int = 0,
    ) -> EpisodeModelDecision:
        snapshot = self._features.build(features)
        belief = self._misconception.predict(snapshot)
        decision = self._policy.decide(
            episode_id=episode_id,
            snapshot=snapshot,
            belief=belief,
            candidates=candidates,
            language=language,
            seed=seed,
            decided_at=decided_at,
            mode=mode,
            learned_policy=learned_policy,
            evidence_count=evidence_count,
        )
        return EpisodeModelDecision(snapshot, belief, decision)

    def complete(
        self,
        *,
        decision: EpisodeModelDecision,
        support_exposure: SupportExposureEvidence,
        verification: IndependenceGainInput,
    ) -> EpisodeModelCompletion:
        if support_exposure.action_id != decision.policy.selected_action_id:
            raise ValueError("support exposure does not match selected action")
        if support_exposure.delivery_status not in {"completed", "dismissed"}:
            raise ValueError("support exposure is not terminal")
        return EpisodeModelCompletion(
            decision=decision,
            support_exposure=support_exposure,
            independence_outcome=calculate_independence_gain(verification),
        )

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.gamification.application.records import (
    FeatureSnapshotRecord,
    PolicyDecisionRecord,
    SupportExposureEvidence,
)
from app.gamification.domain.types import DecisionMode, EpisodeId
from app.gamification.modeling.independence_gain.contracts import (
    IndependenceGainCalculator,
    IndependenceGainInput,
    IndependenceGainResult,
)
from app.gamification.modeling.misconception_inference.contracts import MisconceptionPredictor
from app.gamification.modeling.shared.contracts import MisconceptionDistribution
from app.gamification.modeling.shared.feature_building import DecisionFeatureInput
from app.gamification.modeling.support_selection.contracts import (
    SupportCandidate,
    SupportScorer,
    SupportSelector,
)


class DecisionFeatureBuilder(Protocol):
    def build(self, data: DecisionFeatureInput) -> FeatureSnapshotRecord: ...


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
    """Coordinate injected model capabilities without constructing implementations."""

    def __init__(
        self,
        *,
        feature_builder: DecisionFeatureBuilder,
        misconception_predictor: MisconceptionPredictor,
        support_selector: SupportSelector,
        independence_gain_calculator: IndependenceGainCalculator,
    ) -> None:
        self._feature_builder = feature_builder
        self._misconception_predictor = misconception_predictor
        self._support_selector = support_selector
        self._independence_gain_calculator = independence_gain_calculator

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
        learned_policy: SupportScorer | None = None,
        evidence_count: int = 0,
    ) -> EpisodeModelDecision:
        snapshot = self._feature_builder.build(features)
        belief = self._misconception_predictor.predict(snapshot)
        decision = self._support_selector.decide(
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
            independence_outcome=self._independence_gain_calculator.calculate(verification),
        )

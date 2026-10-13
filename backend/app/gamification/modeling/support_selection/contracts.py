from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.gamification.application.records import FeatureSnapshotRecord, PolicyDecisionRecord
from app.gamification.domain.types import (
    ActionId,
    DecisionMode,
    EpisodeId,
    SupportActionType,
)
from app.gamification.modeling.shared.contracts import MisconceptionDistribution

POLICY_VERSION = "safe-support-policy-v1"


@dataclass(frozen=True, slots=True)
class SupportCandidate:
    action_id: ActionId
    action_type: SupportActionType
    languages: tuple[str, ...]
    skill_ids: tuple[str, ...]
    misconception_codes: tuple[str, ...]
    approved: bool


class SupportScorer(Protocol):
    version: str

    def score(
        self,
        snapshot: FeatureSnapshotRecord,
        belief: MisconceptionDistribution,
        candidates: tuple[SupportCandidate, ...],
    ) -> dict[ActionId, tuple[float, float]]: ...


class SupportSelector(Protocol):
    """Selection capability consumed by the episode orchestrator."""

    def decide(
        self,
        *,
        episode_id: EpisodeId,
        snapshot: FeatureSnapshotRecord,
        belief: MisconceptionDistribution,
        candidates: tuple[SupportCandidate, ...],
        language: str,
        seed: int,
        decided_at: datetime,
        mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE,
        learned_policy: SupportScorer | None = None,
        evidence_count: int = 0,
    ) -> PolicyDecisionRecord: ...

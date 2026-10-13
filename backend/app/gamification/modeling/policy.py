import random
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid5

from app.gamification.application.records import (
    FeatureSnapshotRecord,
    PolicyCandidateRecord,
    PolicyDecisionRecord,
)
from app.gamification.domain.types import (
    ActionId,
    CatalogueVersion,
    DecisionMode,
    EpisodeId,
    PolicyDecisionId,
    SupportActionType,
)
from app.gamification.modeling.misconception import MisconceptionDistribution

POLICY_VERSION = "safe-support-policy-v1"
_DECISION_NAMESPACE = UUID("bf00c614-0f5f-4ea6-9549-bd32b64356c2")


@dataclass(frozen=True, slots=True)
class SupportCandidate:
    action_id: ActionId
    action_type: SupportActionType
    languages: tuple[str, ...]
    skill_ids: tuple[str, ...]
    misconception_codes: tuple[str, ...]
    approved: bool


class LearnedPolicy(Protocol):
    version: str

    def score(
        self,
        snapshot: FeatureSnapshotRecord,
        belief: MisconceptionDistribution,
        candidates: tuple[SupportCandidate, ...],
    ) -> dict[ActionId, tuple[float, float]]: ...


class SafeSupportPolicy:
    def __init__(
        self,
        *,
        catalogue_version: CatalogueVersion,
        minimum_learned_evidence: int = 20,
    ) -> None:
        self.catalogue_version = catalogue_version
        self.minimum_learned_evidence = minimum_learned_evidence

    def decide(
        self,
        *,
        episode_id: EpisodeId,
        snapshot: FeatureSnapshotRecord,
        belief: MisconceptionDistribution,
        candidates: tuple[SupportCandidate, ...],
        language: str,
        seed: int,
        decided_at,
        mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE,
        learned_policy: LearnedPolicy | None = None,
        evidence_count: int = 0,
    ) -> PolicyDecisionRecord:
        if not candidates:
            raise ValueError("policy requires the full candidate catalogue")
        top_code = max(belief.probabilities, key=belief.probabilities.__getitem__)
        eligibility: list[tuple[SupportCandidate, tuple[str, ...]]] = []
        for candidate in candidates:
            reasons = []
            if not candidate.approved:
                reasons.append("CONTENT_NOT_APPROVED")
            if language not in candidate.languages:
                reasons.append("LANGUAGE_UNAVAILABLE")
            if str(snapshot.skill_id) not in candidate.skill_ids:
                reasons.append("SKILL_NOT_SUPPORTED")
            if candidate.misconception_codes and top_code not in candidate.misconception_codes:
                reasons.append("MISCONCEPTION_NOT_SUPPORTED")
            eligibility.append((candidate, tuple(reasons)))
        eligible = tuple(candidate for candidate, reasons in eligibility if not reasons)
        if not eligible:
            raise ValueError("no approved eligible support action")

        scores = learned_policy.score(snapshot, belief, eligible) if learned_policy else {}
        reference = sorted(eligible, key=lambda candidate: str(candidate.action_id))[0]
        effective_mode = mode
        reason_codes: tuple[str, ...]
        if mode is DecisionMode.SHADOW:
            selected = reference
            reason_codes = ("SHADOW_REFERENCE_DELIVERY",)
        elif mode is DecisionMode.LEARNED and (
            learned_policy is None or evidence_count < self.minimum_learned_evidence
        ):
            selected = reference
            effective_mode = DecisionMode.CONSERVATIVE_FALLBACK
            reason_codes = ("COLD_START_REFERENCE_FALLBACK",)
        elif mode is DecisionMode.LEARNED:
            rng = random.Random(seed)
            best = max(value[0] for value in scores.values())
            tied = sorted(action for action, value in scores.items() if value[0] == best)
            selected_id = rng.choice(tied)
            selected = next(item for item in eligible if item.action_id == selected_id)
            reason_codes = ("SEEDED_LEARNED_SELECTION",)
        else:
            selected = reference
            reason_codes = ("DETERMINISTIC_REFERENCE",)

        records = tuple(
            PolicyCandidateRecord(
                action_id=candidate.action_id,
                action_type=candidate.action_type,
                propensity=1.0 if candidate.action_id == selected.action_id else 0.0,
                eligible=not reasons,
                reason_codes=("ELIGIBLE",) if not reasons else reasons,
                predicted_reward=(scores.get(candidate.action_id) or (None, None))[0],
                uncertainty=(scores.get(candidate.action_id) or (None, None))[1],
            )
            for candidate, reasons in eligibility
        )
        stable_key = f"{episode_id}|{POLICY_VERSION}|{seed}"
        return PolicyDecisionRecord(
            decision_id=PolicyDecisionId(uuid5(_DECISION_NAMESPACE, stable_key)),
            episode_id=episode_id,
            feature_snapshot_id=snapshot.snapshot_id,
            selected_action_id=selected.action_id,
            mode=effective_mode,
            policy_version=(learned_policy.version if learned_policy else POLICY_VERSION),
            support_catalogue_version=self.catalogue_version,
            candidates=records,
            reason_codes=reason_codes,
            decided_at=decided_at,
            random_seed=seed,
        )

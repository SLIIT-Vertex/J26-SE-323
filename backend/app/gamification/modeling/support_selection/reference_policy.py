import random
from datetime import datetime
from uuid import UUID, uuid5

from app.gamification.application.records import (
    FeatureSnapshotRecord,
    PolicyCandidateRecord,
    PolicyDecisionRecord,
)
from app.gamification.domain.types import (
    CatalogueVersion,
    DecisionMode,
    EpisodeId,
    PolicyDecisionId,
)
from app.gamification.modeling.shared.contracts import MisconceptionDistribution
from app.gamification.modeling.support_selection.contracts import (
    POLICY_VERSION,
    SupportCandidate,
    SupportScorer,
)
from app.gamification.modeling.support_selection.eligibility import (
    evaluate_candidate_eligibility,
)

_DECISION_NAMESPACE = UUID("bf00c614-0f5f-4ea6-9549-bd32b64356c2")


class SafeSupportPolicy:
    """Select only approved eligible support with deterministic fallback behavior."""

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
        decided_at: datetime,
        mode: DecisionMode = DecisionMode.DETERMINISTIC_REFERENCE,
        learned_policy: SupportScorer | None = None,
        evidence_count: int = 0,
    ) -> PolicyDecisionRecord:
        if not candidates:
            raise ValueError("policy requires the full candidate catalogue")
        eligibility = evaluate_candidate_eligibility(
            snapshot=snapshot,
            belief=belief,
            candidates=candidates,
            language=language,
        )
        eligible = tuple(item.candidate for item in eligibility if item.eligible)
        if not eligible:
            raise ValueError("no approved eligible support action")

        scores = learned_policy.score(snapshot, belief, eligible) if learned_policy else {}
        reference = sorted(eligible, key=lambda candidate: str(candidate.action_id))[0]
        effective_mode = mode
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
                action_id=item.candidate.action_id,
                action_type=item.candidate.action_type,
                propensity=1.0 if item.candidate.action_id == selected.action_id else 0.0,
                eligible=item.eligible,
                reason_codes=("ELIGIBLE",) if item.eligible else item.reason_codes,
                predicted_reward=(scores.get(item.candidate.action_id) or (None, None))[0],
                uncertainty=(scores.get(item.candidate.action_id) or (None, None))[1],
            )
            for item in eligibility
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

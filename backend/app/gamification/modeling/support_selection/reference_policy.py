from collections import defaultdict
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
from app.gamification.modeling.support_selection.context import BanditContext
from app.gamification.modeling.support_selection.contracts import (
    POLICY_VERSION,
    SupportCandidate,
    SupportScorer,
)
from app.gamification.modeling.support_selection.eligibility import (
    PROVISIONAL_MISCONCEPTION_FLOOR,
    evaluate_candidate_eligibility,
)
from app.gamification.modeling.support_selection.learned_policy import ContextualBanditPolicy
from app.gamification.modeling.support_selection.reference_table import (
    ReferencePolicyTable,
    action_type_for,
)

_DECISION_NAMESPACE = UUID("bf00c614-0f5f-4ea6-9549-bd32b64356c2")
_REFERENCE_MODES = {
    DecisionMode.DETERMINISTIC_REFERENCE,
    DecisionMode.PERFORMANCE_TRIGGERED_FIXED,
}


class SafeSupportPolicy:
    """Deliver the authored reference action unless an approved bandit is allowed to sample."""

    def __init__(
        self,
        *,
        catalogue_version: CatalogueVersion,
        minimum_learned_evidence: int = 20,
        reference_table: ReferencePolicyTable | None = None,
        probability_floor: float = PROVISIONAL_MISCONCEPTION_FLOOR,
        bandit: ContextualBanditPolicy | None = None,
        artifact_approved: bool = False,
    ) -> None:
        self.catalogue_version = catalogue_version
        self.minimum_learned_evidence = minimum_learned_evidence
        self.reference_table = reference_table
        self.probability_floor = probability_floor
        self.bandit = bandit
        self.artifact_approved = artifact_approved

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
        context: BanditContext | None = None,
        bandit: ContextualBanditPolicy | None = None,
        artifact_approved: bool | None = None,
    ) -> PolicyDecisionRecord:
        if not candidates:
            raise ValueError("policy requires the full candidate catalogue")
        eligibility = evaluate_candidate_eligibility(
            snapshot=snapshot,
            belief=belief,
            candidates=candidates,
            language=language,
            probability_floor=self.probability_floor,
        )
        eligible = tuple(item.candidate for item in eligibility if item.eligible)
        if not eligible:
            raise ValueError("no approved eligible support action")

        active_bandit = self.bandit if bandit is None else bandit
        approved = self.artifact_approved if artifact_approved is None else artifact_approved
        reference, reference_reasons = _reference_choice(
            eligible, snapshot, belief, self.reference_table
        )
        if mode is DecisionMode.DETERMINISTIC_REFERENCE:
            reference_reasons = reference_reasons + ("DETERMINISTIC_REFERENCE_ALIAS",)
        predictions, propensities, would_select, bandit_reasons = _bandit_view(
            active_bandit, context, eligible, seed
        )
        scorer_predictions = (
            learned_policy.score(snapshot, belief, eligible) if learned_policy is not None else {}
        )
        learned_ready = (
            mode is DecisionMode.LEARNED
            and approved
            and evidence_count >= self.minimum_learned_evidence
            and active_bandit is not None
            and context is not None
            and would_select is not None
        )
        effective_mode = mode
        if mode is DecisionMode.SHADOW:
            selected = reference
            reason_codes = ("SHADOW_REFERENCE_DELIVERY", *reference_reasons, *bandit_reasons)
        elif mode is DecisionMode.LEARNED and not learned_ready:
            selected = reference
            effective_mode = DecisionMode.CONSERVATIVE_FALLBACK
            reason_codes = ("COLD_START_REFERENCE_FALLBACK", *reference_reasons)
            propensities = {}
        elif learned_ready:
            assert would_select is not None
            selected = _candidate_for_arm(eligible, would_select)
            reason_codes = ("SEEDED_LEARNED_SELECTION", *bandit_reasons)
        elif mode in _REFERENCE_MODES:
            selected = reference
            reason_codes = reference_reasons
            propensities = {}
        else:
            selected = reference
            reason_codes = reference_reasons
            propensities = {}

        if not propensities:
            propensities = {
                str(candidate.action_id): (
                    1.0 if candidate.action_id == selected.action_id else 0.0
                )
                for candidate in eligible
            }
        records = []
        for item in eligibility:
            action_id = item.candidate.action_id
            bandit_prediction = predictions.get(item.candidate.action_type.value)
            scorer_prediction = scorer_predictions.get(action_id)
            predicted = bandit_prediction or scorer_prediction
            matched = tuple(f"MATCHED:{code}" for code in item.matched_codes)
            records.append(
                PolicyCandidateRecord(
                    action_id=action_id,
                    action_type=item.candidate.action_type,
                    propensity=propensities.get(str(action_id), 0.0) if item.eligible else 0.0,
                    eligible=item.eligible,
                    reason_codes=(("ELIGIBLE", *matched) if item.eligible else item.reason_codes),
                    predicted_reward=None if predicted is None else predicted[0],
                    uncertainty=None if predicted is None else predicted[1],
                )
            )
        records.sort(key=_rank_key)
        stable_key = f"{episode_id}|{POLICY_VERSION}|{seed}"
        return PolicyDecisionRecord(
            decision_id=PolicyDecisionId(uuid5(_DECISION_NAMESPACE, stable_key)),
            episode_id=episode_id,
            feature_snapshot_id=snapshot.snapshot_id,
            selected_action_id=selected.action_id,
            mode=effective_mode,
            policy_version=(
                active_bandit.version
                if learned_ready and active_bandit is not None
                else POLICY_VERSION
            ),
            support_catalogue_version=self.catalogue_version,
            candidates=tuple(records),
            reason_codes=reason_codes,
            decided_at=decided_at,
            random_seed=seed,
        )


def _reference_choice(
    eligible: tuple[SupportCandidate, ...],
    snapshot: FeatureSnapshotRecord,
    belief: MisconceptionDistribution,
    table: ReferencePolicyTable | None,
) -> tuple[SupportCandidate, tuple[str, ...]]:
    top_code = max(belief.probabilities, key=belief.probabilities.__getitem__)
    preferred = None if table is None else table.preferred_type(str(snapshot.skill_id), top_code)
    if preferred is None:
        return min(eligible, key=lambda candidate: str(candidate.action_id)), (
            "REFERENCE_TABLE_MISS",
        )
    action_type = action_type_for(preferred)
    matches = [
        candidate
        for candidate in eligible
        if action_type is not None and candidate.action_type is action_type
    ]
    if not matches:
        return min(eligible, key=lambda candidate: str(candidate.action_id)), (
            "REFERENCE_TYPE_UNAVAILABLE",
        )
    return min(matches, key=lambda candidate: str(candidate.action_id)), (
        "AUTHORED_REFERENCE_TABLE",
    )


def _bandit_view(
    bandit: ContextualBanditPolicy | None,
    context: BanditContext | None,
    eligible: tuple[SupportCandidate, ...],
    seed: int,
) -> tuple[dict[str, tuple[float, float]], dict[str, float], str | None, tuple[str, ...]]:
    if bandit is None or context is None:
        return {}, {}, None, ()
    arms = tuple(sorted({candidate.action_type.value for candidate in eligible}))
    predictions = bandit.predict(context, arms)
    chosen, arm_propensities = bandit.sample_action(context, arms, seed=seed)
    grouped: dict[str, list[SupportCandidate]] = defaultdict(list)
    for candidate in eligible:
        grouped[candidate.action_type.value].append(candidate)
    propensities: dict[str, float] = {}
    for arm, group in grouped.items():
        share = arm_propensities.get(arm, 0.0) / len(group)
        for candidate in group:
            propensities[str(candidate.action_id)] = share
    reasons = [f"BANDIT_WOULD_SELECT:{chosen}"]
    samples = getattr(bandit, "monte_carlo_samples", None)
    if samples is not None:
        reasons.append(f"THOMPSON_MC_SAMPLES:{samples}")
    return predictions, propensities, chosen, tuple(reasons)


def _candidate_for_arm(eligible: tuple[SupportCandidate, ...], arm: str) -> SupportCandidate:
    matches = [candidate for candidate in eligible if candidate.action_type.value == arm]
    if not matches:
        raise ValueError(f"sampled arm {arm} has no eligible candidate")
    return min(matches, key=lambda candidate: str(candidate.action_id))


def _rank_key(record: PolicyCandidateRecord) -> tuple[int, float, str]:
    reward = record.predicted_reward
    ranked_reward = float("-inf") if reward is None else reward
    return (0 if record.eligible else 1, -ranked_reward, str(record.action_id))

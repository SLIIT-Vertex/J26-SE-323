"""Replay logged decisions into a bandit and seal the parameters as an artifact."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

from app.gamification.modeling.shared.artifact_registry import (
    ManifestReference,
    ModelArtifactBundle,
)
from app.gamification.modeling.support_selection.context import CONTEXT_VERSION, BanditContext
from app.gamification.modeling.support_selection.learned_policy import ContextualBanditPolicy
from app.gamification.modeling.support_selection.reward import IndependenceGainReward

MODEL_NAME = "support-policy"
MODEL_VERSION = "contextual-bandit-v1"


@dataclass(frozen=True, slots=True)
class LoggedBanditDecision:
    learner_id: str
    decided_at: datetime
    context: BanditContext
    arm: str
    propensity: float


class RewardableOutcome(Protocol):
    validity: object
    raw_gain: float | None


def fit_from_logged_decisions(
    decisions: Iterable[LoggedBanditDecision],
    outcomes: Iterable[RewardableOutcome],
    policy: ContextualBanditPolicy,
    *,
    reward: IndependenceGainReward,
    train_learner_ids: Iterable[str],
    manifest: ManifestReference,
    seed: int,
    source_commit: str,
) -> ModelArtifactBundle:
    """Update only the train learners, in decision-time order. Held-out learners are ignored.

    ``decisions`` and ``outcomes`` are parallel sequences. A decision whose learner is
    outside ``train_learner_ids`` is not replayed.
    """

    allowed = set(train_learner_ids)
    paired = [
        (decision, outcome)
        for decision, outcome in zip(decisions, outcomes, strict=True)
        if decision.learner_id in allowed
    ]
    for decision, outcome in sorted(
        paired, key=lambda item: (item[0].decided_at, item[0].learner_id)
    ):
        try:
            observed = reward(outcome)
        except ValueError:
            continue
        policy.update(decision.context, decision.arm, observed)
    parameters = policy.parameters()
    parameters["model_card"] = _model_card(policy.version, manifest)
    parameters["context_version"] = CONTEXT_VERSION
    return ModelArtifactBundle.create(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        source_commit=source_commit,
        feature_definition_version=CONTEXT_VERSION,
        manifest=manifest,
        seed=seed,
        parameters=parameters,
    )


def _model_card(policy_version: str, manifest: ManifestReference) -> str:
    evidence = "synthetic engineering data only" if manifest.synthetic else "declared dataset"
    return "\n".join(
        (
            f"# Model card: {MODEL_NAME} {MODEL_VERSION}",
            "",
            f"- Policy: `{policy_version}`",
            "- model_role: support_policy",
            f"- Dataset manifest: `{manifest.digest}`",
            f"- Evidence: {evidence}",
            "- Reward: raw-ig-reward-v1, valid Independence Gain only",
            "- Approval: candidate only; registration does not authorize child-facing use",
            "- Limitations: not an educational-effectiveness result",
        )
    )

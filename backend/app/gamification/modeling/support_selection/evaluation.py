from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol


class LoggedPolicyRow(Protocol):
    episode_id: str
    action_id: str
    reward: float | None
    propensity: float | None
    valid_outcome: bool


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    sample_count: int
    ips: float
    self_normalized_ips: float
    direct_method: float | None
    doubly_robust: float | None


def evaluate_logged_policy(
    rows: Iterable[LoggedPolicyRow],
    target_probabilities: Mapping[tuple[str, str], float],
) -> PolicyEvaluation:
    """Evaluate logged actions only when positive propensities make IPS valid."""

    usable = [row for row in rows if row.valid_outcome and row.reward is not None]
    if any(row.propensity is None or row.propensity <= 0 for row in usable):
        raise ValueError("off-policy evaluation requires positive logged propensities")
    if not usable:
        raise ValueError("off-policy evaluation requires valid rewarded episodes")
    weights = [
        target_probabilities.get((row.episode_id, row.action_id), 0.0) / row.propensity
        for row in usable
        if row.propensity is not None
    ]
    weighted_rewards = [weight * float(row.reward) for weight, row in zip(weights, usable)]
    total_weight = sum(weights)
    return PolicyEvaluation(
        sample_count=len(usable),
        ips=sum(weighted_rewards) / len(usable),
        self_normalized_ips=(sum(weighted_rewards) / total_weight if total_weight else 0.0),
        direct_method=None,
        doubly_robust=None,
    )

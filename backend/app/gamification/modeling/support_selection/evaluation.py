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
    reward_estimates: Mapping[tuple[str, str], float] | None = None,
) -> PolicyEvaluation:
    """Evaluate logged actions only when propensities are positive and not deterministic.

    Direct-method and doubly-robust estimates stay empty unless the caller supplies the
    bandit's own reward estimates. This function does not invent a reward model.
    """

    usable = [row for row in rows if row.valid_outcome and row.reward is not None]
    if any(row.propensity is None or row.propensity <= 0 for row in usable):
        raise ValueError("off-policy evaluation requires positive logged propensities")
    if any(row.propensity is not None and row.propensity >= 1 for row in usable):
        raise ValueError("degenerate logging propensities")
    if not usable:
        raise ValueError("off-policy evaluation requires valid rewarded episodes")
    weights = [
        target_probabilities.get((row.episode_id, row.action_id), 0.0) / row.propensity
        for row in usable
        if row.propensity is not None
    ]
    weighted_rewards = [
        weight * float(row.reward) for weight, row in zip(weights, usable, strict=True)
    ]
    total_weight = sum(weights)
    direct_method, doubly_robust = _model_estimates(usable, target_probabilities, reward_estimates)
    return PolicyEvaluation(
        sample_count=len(usable),
        ips=sum(weighted_rewards) / len(usable),
        self_normalized_ips=(sum(weighted_rewards) / total_weight if total_weight else 0.0),
        direct_method=direct_method,
        doubly_robust=doubly_robust,
    )


def cumulative_regret(optimal: Iterable[float], chosen: Iterable[float]) -> float:
    """Simulation-only gap between the best expected reward and the action that was taken."""

    optimal_values = tuple(optimal)
    chosen_values = tuple(chosen)
    if len(optimal_values) != len(chosen_values):
        raise ValueError("regret requires paired optimal and chosen values")
    return sum(best - actual for best, actual in zip(optimal_values, chosen_values, strict=True))


def _model_estimates(
    usable: list[LoggedPolicyRow],
    target_probabilities: Mapping[tuple[str, str], float],
    reward_estimates: Mapping[tuple[str, str], float] | None,
) -> tuple[float | None, float | None]:
    if reward_estimates is None:
        return None, None
    direct_values: list[float] = []
    robust_values: list[float] = []
    for row in usable:
        actions = {
            action for episode_id, action in target_probabilities if episode_id == row.episode_id
        }
        actions.add(row.action_id)
        if any((row.episode_id, action) not in reward_estimates for action in actions):
            raise ValueError("reward estimates are incomplete for the logged episode")
        direct = sum(
            target_probabilities.get((row.episode_id, action), 0.0)
            * reward_estimates[(row.episode_id, action)]
            for action in actions
        )
        logged = reward_estimates[(row.episode_id, row.action_id)]
        target = target_probabilities.get((row.episode_id, row.action_id), 0.0)
        propensity = row.propensity
        assert propensity is not None
        direct_values.append(direct)
        robust_values.append(direct + (float(row.reward) - logged) * target / propensity)
    return sum(direct_values) / len(direct_values), sum(robust_values) / len(robust_values)

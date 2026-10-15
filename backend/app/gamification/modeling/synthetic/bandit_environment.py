"""Seeded synthetic bandit world. Numbers from this module are not learner evidence."""

import random
from statistics import fmean

from app.gamification.modeling.support_selection.context import CONTEXT_VERSION, BanditContext
from app.gamification.modeling.support_selection.evaluation import cumulative_regret
from app.gamification.modeling.support_selection.learned_policy import (
    LinUCBPolicy,
    ThompsonSamplingPolicy,
)

GENERATOR_VERSION = "synthetic-bandit-environment-v1"
_ARMS = ("visual", "steps", "worked")
_MISCONCEPTIONS = ("m1", "m2", "m3")
_NAMES = ("bias", "belief:m1", "belief:m2", "belief:m3")
# Hidden expected Independence Gain. The fixed policy always picks visual, which is best
# for only one of the three hidden misconceptions.
_EXPECTED = {
    "m1": {"visual": 0.90, "steps": 0.10, "worked": 0.00},
    "m2": {"visual": 0.00, "steps": 0.90, "worked": 0.10},
    "m3": {"visual": 0.00, "steps": 0.10, "worked": 0.90},
}
_NOISE = 0.02


def run_bandit_simulation(
    *,
    seeds: int = 30,
    learners_per_seed: int = 12,
    rounds_per_learner: int = 12,
) -> dict[str, object]:
    """Compare policies where the best scaffold depends on a hidden misconception."""

    if seeds < 30:
        raise ValueError("the engineering comparison uses at least 30 seeds")
    names = (
        "performance_triggered_fixed",
        "random_eligible",
        "LinUCB",
        "ThompsonSampling",
        "LinUCB_belief_ablated",
    )
    regrets = {name: [] for name in names}
    rewards = {name: [] for name in names}
    arms = {name: [] for name in names}
    hidden: dict[str, list[str]] = {name: [] for name in names}
    for seed in range(seeds):
        per_seed = _one_seed(seed, learners_per_seed, rounds_per_learner)
        for name in names:
            regrets[name].append(per_seed[name]["regret"])
            rewards[name].extend(per_seed[name]["rewards"])
            arms[name].extend(per_seed[name]["arms"])
            hidden[name].extend(per_seed[name]["hidden"])
    return {
        "generator": GENERATOR_VERSION,
        "synthetic": True,
        "provenance": "synthetic",
        "seeds": seeds,
        "learners_per_seed": learners_per_seed,
        "rounds_per_learner": rounds_per_learner,
        "mean_valid_ig": {name: fmean(rewards[name]) for name in names},
        "mean_cumulative_regret": {name: fmean(regrets[name]) for name in names},
        "action_coverage": {name: len(set(arms[name])) / len(_ARMS) for name in names},
        "fallback_rate": {name: 0.0 for name in names},
        "per_misconception_mean_ig": {
            name: {
                code: fmean(
                    reward
                    for reward, label in zip(rewards[name], hidden[name], strict=True)
                    if label == code
                )
                for code in _MISCONCEPTIONS
            }
            for name in names
        },
        "ablation": "LinUCB_belief_ablated",
        "label": "synthetic engineering comparison; not educational effectiveness",
    }


def _one_seed(
    seed: int, learners_per_seed: int, rounds_per_learner: int
) -> dict[str, dict[str, object]]:
    linucb = LinUCBPolicy(epsilon_min=0.05)
    thompson = ThompsonSamplingPolicy(epsilon_min=0.05, monte_carlo_samples=40)
    ablated = LinUCBPolicy(epsilon_min=0.05)
    observed: dict[str, list[float]] = {
        "performance_triggered_fixed": [],
        "random_eligible": [],
        "LinUCB": [],
        "ThompsonSampling": [],
        "LinUCB_belief_ablated": [],
    }
    optimal: list[float] = []
    chosen = {name: [] for name in observed}
    arms: dict[str, list[str]] = {name: [] for name in observed}
    hidden_labels: list[str] = []
    for learner_index in range(learners_per_seed):
        hidden = _MISCONCEPTIONS[learner_index % len(_MISCONCEPTIONS)]
        context = _context(hidden)
        blinded = context.without_belief_block()
        best = max(_EXPECTED[hidden].values())
        for round_index in range(rounds_per_learner):
            draw = random.Random(seed * 1_000_003 + learner_index * 97 + round_index)
            optimal.append(best)
            hidden_labels.append(hidden)
            _record(
                "performance_triggered_fixed",
                "visual",
                hidden,
                draw,
                observed,
                chosen,
                arms,
            )
            _record(
                "random_eligible",
                draw.choice(_ARMS),
                hidden,
                draw,
                observed,
                chosen,
                arms,
            )
            full_arm, _ = linucb.sample_action(context, _ARMS, seed=draw.randint(0, 10**9))
            _record("LinUCB", full_arm, hidden, draw, observed, chosen, arms)
            linucb.update(context, full_arm, observed["LinUCB"][-1])
            thompson_arm, _ = thompson.sample_action(context, _ARMS, seed=draw.randint(0, 10**9))
            _record("ThompsonSampling", thompson_arm, hidden, draw, observed, chosen, arms)
            thompson.update(context, thompson_arm, observed["ThompsonSampling"][-1])
            blind_arm, _ = ablated.sample_action(blinded, _ARMS, seed=draw.randint(0, 10**9))
            _record("LinUCB_belief_ablated", blind_arm, hidden, draw, observed, chosen, arms)
            ablated.update(blinded, blind_arm, observed["LinUCB_belief_ablated"][-1])
    return {
        name: {
            "regret": cumulative_regret(optimal, values),
            "rewards": observed[name],
            "arms": arms[name],
            "hidden": hidden_labels,
        }
        for name, values in chosen.items()
    }


def _record(
    name: str,
    arm: str,
    hidden: str,
    draw: random.Random,
    observed: dict[str, list[float]],
    chosen: dict[str, list[float]],
    arms: dict[str, list[str]],
) -> None:
    expected = _EXPECTED[hidden][arm]
    noisy = min(1.0, max(-1.0, draw.gauss(expected, _NOISE)))
    observed[name].append(noisy)
    chosen[name].append(expected)
    arms[name].append(arm)


def _context(hidden: str) -> BanditContext:
    values = tuple(1.0 if name == "bias" or name == f"belief:{hidden}" else 0.0 for name in _NAMES)
    return BanditContext(CONTEXT_VERSION, _NAMES, values, {})

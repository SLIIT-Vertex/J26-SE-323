"""Disjoint linear contextual bandits. Provisional exploration settings, not calibrated."""

import math
import random
from collections.abc import Sequence
from typing import Protocol

from app.gamification.modeling.support_selection.context import BanditContext

# Provisional until an approved offline fit replaces them.
PROVISIONAL_ALPHA = 1.0
PROVISIONAL_EPSILON_MIN = 0.05
PROVISIONAL_RIDGE = 1.0
PROVISIONAL_PRIOR_VARIANCE = 1.0
PROVISIONAL_NOISE_VARIANCE = 0.25
PROVISIONAL_MONTE_CARLO_SAMPLES = 200


class ContextualBanditPolicy(Protocol):
    version: str

    def predict(
        self, context: BanditContext, arms: Sequence[str]
    ) -> dict[str, tuple[float, float]]: ...

    def sample_action(
        self, context: BanditContext, arms: Sequence[str], *, seed: int
    ) -> tuple[str, dict[str, float]]: ...

    def update(self, context: BanditContext, arm: str, reward: float) -> None: ...

    def parameters(self) -> dict[str, object]: ...


class LinUCBPolicy:
    """Disjoint per-arm ridge regression. The greedy arm is mixed with an exploration floor."""

    version = "linucb-disjoint-v1"

    def __init__(
        self,
        *,
        alpha: float = PROVISIONAL_ALPHA,
        ridge: float = PROVISIONAL_RIDGE,
        epsilon_min: float = PROVISIONAL_EPSILON_MIN,
    ) -> None:
        if alpha < 0 or ridge <= 0 or not 0 <= epsilon_min <= 1:
            raise ValueError("LinUCB settings are out of range")
        self.alpha = alpha
        self.ridge = ridge
        self.epsilon_min = epsilon_min
        self._arms: dict[str, dict[str, object]] = {}

    def predict(
        self, context: BanditContext, arms: Sequence[str]
    ) -> dict[str, tuple[float, float]]:
        vector = _vector(context)
        return {arm: self._predict_arm(arm, vector) for arm in _arms(arms)}

    def sample_action(
        self, context: BanditContext, arms: Sequence[str], *, seed: int
    ) -> tuple[str, dict[str, float]]:
        predictions = self.predict(context, arms)
        scores = {
            arm: mean + self.alpha * uncertainty for arm, (mean, uncertainty) in predictions.items()
        }
        winner = min(scores, key=lambda arm: (-scores[arm], arm))
        propensities = _floor_mixture(winner, tuple(predictions), self.epsilon_min)
        chosen = _choose(propensities, random.Random(seed))
        return chosen, propensities

    def update(self, context: BanditContext, arm: str, reward: float) -> None:
        vector = _vector(context)
        state = self._state(arm, len(vector))
        matrix = state["A"]
        target = state["b"]
        assert isinstance(matrix, list) and isinstance(target, list)
        for row_index, row_value in enumerate(vector):
            target[row_index] += reward * row_value
            for column_index, column_value in enumerate(vector):
                matrix[row_index][column_index] += row_value * column_value

    def parameters(self) -> dict[str, object]:
        return {
            "algorithm": "linucb",
            "model_role": "support_policy",
            "version": self.version,
            "alpha": self.alpha,
            "ridge": self.ridge,
            "epsilon_min": self.epsilon_min,
            "thresholds_status": "provisional_assumption",
            "arms": {
                arm: {"A": _copy_matrix(state["A"]), "b": list(state["b"])}
                for arm, state in sorted(self._arms.items())
            },
        }

    @classmethod
    def from_parameters(cls, parameters: dict[str, object]) -> "LinUCBPolicy":
        policy = cls(
            alpha=float(parameters["alpha"]),  # type: ignore[arg-type]
            ridge=float(parameters["ridge"]),  # type: ignore[arg-type]
            epsilon_min=float(parameters["epsilon_min"]),  # type: ignore[arg-type]
        )
        arms = parameters.get("arms")
        if not isinstance(arms, dict):
            raise TypeError("LinUCB parameters require an arms mapping")
        for arm, state in arms.items():
            if not isinstance(state, dict):
                raise TypeError("LinUCB arm state must be a mapping")
            policy._arms[str(arm)] = {
                "A": _copy_matrix(state["A"]),
                "b": [float(value) for value in state["b"]],
            }
        return policy

    def _predict_arm(self, arm: str, vector: tuple[float, ...]) -> tuple[float, float]:
        state = self._state(arm, len(vector))
        matrix = state["A"]
        target = state["b"]
        assert isinstance(matrix, list) and isinstance(target, list)
        solved = _solve(matrix, target)
        mean = _dot(solved, vector)
        variance = _dot(vector, _solve(matrix, list(vector)))
        return mean, math.sqrt(max(variance, 0.0))

    def _state(self, arm: str, dimension: int) -> dict[str, object]:
        state = self._arms.get(arm)
        if state is None:
            state = {"A": _identity(dimension, self.ridge), "b": [0.0] * dimension}
            self._arms[arm] = state
        target = state["b"]
        if not isinstance(target, list) or len(target) != dimension:
            raise ValueError("context dimension does not match the fitted policy")
        return state


class ThompsonSamplingPolicy:
    """Per-arm Bayesian linear regression with a Gaussian posterior."""

    version = "thompson-linear-v1"

    def __init__(
        self,
        *,
        prior_variance: float = PROVISIONAL_PRIOR_VARIANCE,
        noise_variance: float = PROVISIONAL_NOISE_VARIANCE,
        epsilon_min: float = PROVISIONAL_EPSILON_MIN,
        monte_carlo_samples: int = PROVISIONAL_MONTE_CARLO_SAMPLES,
    ) -> None:
        if prior_variance <= 0 or noise_variance <= 0 or monte_carlo_samples < 1:
            raise ValueError("Thompson sampling settings are out of range")
        if not 0 <= epsilon_min <= 1:
            raise ValueError("exploration floor must be between zero and one")
        self.prior_variance = prior_variance
        self.noise_variance = noise_variance
        self.epsilon_min = epsilon_min
        self.monte_carlo_samples = monte_carlo_samples
        self._arms: dict[str, dict[str, object]] = {}

    def predict(
        self, context: BanditContext, arms: Sequence[str]
    ) -> dict[str, tuple[float, float]]:
        vector = _vector(context)
        return {arm: self._predict_arm(arm, vector) for arm in _arms(arms)}

    def sample_action(
        self, context: BanditContext, arms: Sequence[str], *, seed: int
    ) -> tuple[str, dict[str, float]]:
        arm_names = _arms(arms)
        vector = _vector(context)
        counts = dict.fromkeys(arm_names, 0)
        for draw in range(self.monte_carlo_samples):
            scores = {
                arm: _dot(self._sample_theta(arm, len(vector), seed, draw), vector)
                for arm in arm_names
            }
            counts[min(scores, key=lambda arm: (-scores[arm], arm))] += 1
        raw = {arm: counts[arm] / self.monte_carlo_samples for arm in arm_names}
        propensities = _mix_floor(raw, self.epsilon_min)
        chosen = _choose(propensities, random.Random(seed))
        return chosen, propensities

    def update(self, context: BanditContext, arm: str, reward: float) -> None:
        vector = _vector(context)
        state = self._state(arm, len(vector))
        matrix = state["A"]
        target = state["b"]
        assert isinstance(matrix, list) and isinstance(target, list)
        scale = 1.0 / self.noise_variance
        for row_index, row_value in enumerate(vector):
            target[row_index] += scale * reward * row_value
            for column_index, column_value in enumerate(vector):
                matrix[row_index][column_index] += scale * row_value * column_value

    def parameters(self) -> dict[str, object]:
        return {
            "algorithm": "thompson_sampling",
            "model_role": "support_policy",
            "version": self.version,
            "prior_variance": self.prior_variance,
            "noise_variance": self.noise_variance,
            "epsilon_min": self.epsilon_min,
            "monte_carlo_samples": self.monte_carlo_samples,
            "thresholds_status": "provisional_assumption",
            "arms": {
                arm: {"A": _copy_matrix(state["A"]), "b": list(state["b"])}
                for arm, state in sorted(self._arms.items())
            },
        }

    @classmethod
    def from_parameters(cls, parameters: dict[str, object]) -> "ThompsonSamplingPolicy":
        policy = cls(
            prior_variance=float(parameters["prior_variance"]),  # type: ignore[arg-type]
            noise_variance=float(parameters["noise_variance"]),  # type: ignore[arg-type]
            epsilon_min=float(parameters["epsilon_min"]),  # type: ignore[arg-type]
            monte_carlo_samples=int(parameters["monte_carlo_samples"]),  # type: ignore[arg-type]
        )
        arms = parameters.get("arms")
        if not isinstance(arms, dict):
            raise TypeError("Thompson parameters require an arms mapping")
        for arm, state in arms.items():
            if not isinstance(state, dict):
                raise TypeError("Thompson arm state must be a mapping")
            policy._arms[str(arm)] = {
                "A": _copy_matrix(state["A"]),
                "b": [float(value) for value in state["b"]],
            }
        return policy

    def _predict_arm(self, arm: str, vector: tuple[float, ...]) -> tuple[float, float]:
        state = self._state(arm, len(vector))
        matrix = state["A"]
        target = state["b"]
        assert isinstance(matrix, list) and isinstance(target, list)
        mean = _dot(_solve(matrix, target), vector)
        variance = _dot(vector, _solve(matrix, list(vector)))
        return mean, math.sqrt(max(variance, 0.0))

    def _sample_theta(self, arm: str, dimension: int, seed: int, draw: int) -> list[float]:
        state = self._state(arm, dimension)
        matrix = state["A"]
        target = state["b"]
        assert isinstance(matrix, list) and isinstance(target, list)
        mean = _solve(matrix, target)
        lower = _cholesky(matrix)
        rng = random.Random((seed + 1) * 1_000_003 + draw * 97 + _arm_salt(arm))
        noise = [_box_muller(rng) for _ in range(dimension)]
        delta = _solve_upper(lower, noise)
        return [value + shift for value, shift in zip(mean, delta, strict=True)]

    def _state(self, arm: str, dimension: int) -> dict[str, object]:
        state = self._arms.get(arm)
        if state is None:
            state = {
                "A": _identity(dimension, 1.0 / self.prior_variance),
                "b": [0.0] * dimension,
            }
            self._arms[arm] = state
        target = state["b"]
        if not isinstance(target, list) or len(target) != dimension:
            raise ValueError("context dimension does not match the fitted policy")
        return state


def _vector(context: BanditContext) -> tuple[float, ...]:
    if not context.values:
        raise ValueError("bandit context is empty")
    return context.values


def _arms(arms: Sequence[str]) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(arms))
    if not names:
        raise ValueError("bandit requires at least one arm")
    return names


def _floor_mixture(winner: str, arms: Sequence[str], epsilon_min: float) -> dict[str, float]:
    if len(arms) * epsilon_min > 1:
        raise ValueError("exploration floor exceeds one")
    propensities = dict.fromkeys(arms, epsilon_min)
    propensities[winner] += 1.0 - len(arms) * epsilon_min
    return propensities


def _mix_floor(raw: dict[str, float], epsilon_min: float) -> dict[str, float]:
    if len(raw) * epsilon_min > 1:
        raise ValueError("exploration floor exceeds one")
    retained = 1.0 - len(raw) * epsilon_min
    return {arm: retained * probability + epsilon_min for arm, probability in raw.items()}


def _choose(propensities: dict[str, float], rng: random.Random) -> str:
    threshold = rng.random()
    cumulative = 0.0
    last = ""
    for arm in sorted(propensities):
        cumulative += propensities[arm]
        last = arm
        if threshold <= cumulative:
            return arm
    return last


def _arm_salt(arm: str) -> int:
    return int.from_bytes(arm.encode("utf-8"), "big") % 10_000_019


def _identity(dimension: int, scale: float) -> list[list[float]]:
    return [
        [scale if row == column else 0.0 for column in range(dimension)] for row in range(dimension)
    ]


def _copy_matrix(matrix: object) -> list[list[float]]:
    if not isinstance(matrix, list):
        raise TypeError("arm matrix must be a list of rows")
    return [[float(value) for value in row] for row in matrix]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _box_muller(rng: random.Random) -> float:
    first = max(rng.random(), 1e-12)
    second = rng.random()
    return math.sqrt(-2.0 * math.log(first)) * math.cos(2.0 * math.pi * second)


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            total = sum(lower[row][index] * lower[column][index] for index in range(column))
            if row == column:
                value = matrix[row][row] - total
                lower[row][column] = math.sqrt(value if value > 1e-12 else 1e-8)
            else:
                lower[row][column] = (matrix[row][column] - total) / lower[column][column]
    return lower


def _solve_lower(lower: list[list[float]], target: Sequence[float]) -> list[float]:
    solved = [0.0] * len(target)
    for row in range(len(target)):
        total = sum(lower[row][column] * solved[column] for column in range(row))
        solved[row] = (target[row] - total) / lower[row][row]
    return solved


def _solve_upper(lower: list[list[float]], target: Sequence[float]) -> list[float]:
    size = len(target)
    solved = [0.0] * size
    for row in range(size - 1, -1, -1):
        total = sum(lower[column][row] * solved[column] for column in range(row + 1, size))
        solved[row] = (target[row] - total) / lower[row][row]
    return solved


def _solve(matrix: list[list[float]], target: Sequence[float]) -> list[float]:
    lower = _cholesky(matrix)
    return _solve_upper(lower, _solve_lower(lower, target))

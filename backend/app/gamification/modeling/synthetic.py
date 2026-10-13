"""Synthetic engineering fixtures. Outputs are never research effectiveness evidence."""

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True, slots=True)
class SyntheticEpisode:
    synthetic: bool
    learner_id: str
    episode_id: str
    baseline_score: float
    verification_score: float
    structured_error_code: str | None
    learner_state_available: bool
    support_delivered: bool
    verification_valid: bool
    evidence_count: int


def generate_synthetic_episodes(*, seed: int) -> tuple[SyntheticEpisode, ...]:
    rng = Random(seed)
    cases = (
        ("success", 0.0, 1.0, "error-a", True, True, True, 30),
        ("failure", 0.5, 0.0, "error-b", True, True, True, 30),
        ("missing-data", 0.0, 0.5, None, False, True, True, 30),
        ("invalid-verification", 0.0, 1.0, "error-a", True, True, False, 30),
        ("cold-start", 0.0, 0.5, "error-a", True, True, True, 0),
    )
    return tuple(
        SyntheticEpisode(
            synthetic=True,
            learner_id=f"synthetic-learner-{index}",
            episode_id=f"synthetic-{name}-{rng.randrange(1_000_000):06d}",
            baseline_score=baseline,
            verification_score=verification,
            structured_error_code=error,
            learner_state_available=state,
            support_delivered=delivered,
            verification_valid=valid,
            evidence_count=count,
        )
        for index, (name, baseline, verification, error, state, delivered, valid, count) in enumerate(
            cases, start=1
        )
    )

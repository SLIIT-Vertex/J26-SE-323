"""Explicitly synthetic fixtures; never research-effectiveness evidence."""

from app.gamification.modeling.synthetic.episode_factory import (
    GENERATOR_VERSION,
    SYNTHETIC_SKILL_CODES,
    SyntheticEpisode,
    SyntheticMisconceptionObservation,
    generate_hidden_misconception_observations,
    generate_synthetic_episodes,
)

__all__ = [
    "GENERATOR_VERSION",
    "SYNTHETIC_SKILL_CODES",
    "SyntheticEpisode",
    "SyntheticMisconceptionObservation",
    "generate_hidden_misconception_observations",
    "generate_synthetic_episodes",
]

"""Framework-independent adaptive episode domain."""

from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.exceptions import (
    DomainValidationError,
    EpisodeTransitionError,
)
from app.gamification.domain.types import (
    DecisionMode,
    EpisodePhase,
    EvidenceSupportState,
    OutcomeValidity,
    SupportActionType,
)

__all__ = [
    "AdaptiveEpisode",
    "DecisionMode",
    "DomainValidationError",
    "EpisodePhase",
    "EpisodeTransitionError",
    "EvidenceSupportState",
    "OutcomeValidity",
    "SupportActionType",
]

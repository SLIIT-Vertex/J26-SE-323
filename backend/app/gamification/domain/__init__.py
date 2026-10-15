"""Framework-independent adaptive episode domain."""

from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.exceptions import (
    DomainValidationError,
    EpisodeTransitionError,
)
from app.gamification.domain.types import (
    AssistanceState,
    DecisionMode,
    EpisodePhase,
    EvidenceSupportState,
    ExperimentMode,
    MeasurementRole,
    OutcomeValidity,
    SupportActionType,
)

__all__ = [
    "AdaptiveEpisode",
    "AssistanceState",
    "DecisionMode",
    "DomainValidationError",
    "EpisodePhase",
    "EpisodeTransitionError",
    "EvidenceSupportState",
    "ExperimentMode",
    "MeasurementRole",
    "OutcomeValidity",
    "SupportActionType",
]

class GamificationDomainError(Exception):
    """Base exception for adaptive gamification domain failures."""


class DomainValidationError(GamificationDomainError, ValueError):
    """Raised when a domain value violates a stable invariant."""


class EpisodeTransitionError(GamificationDomainError):
    """Raised when an adaptive episode transition is not legal."""


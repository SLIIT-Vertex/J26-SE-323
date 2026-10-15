from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class MisconceptionDistribution:
    """Immutable cross-model belief contract produced before support selection."""

    probabilities: Mapping[str, float]
    entropy: float
    confidence: float
    abstained: bool
    model_version: str
    catalogue_version: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        probabilities = dict(self.probabilities)
        if not probabilities or abs(sum(probabilities.values()) - 1.0) > 1e-9:
            raise ValueError("misconception probabilities must sum to one")
        if any(value < 0 or value > 1 for value in probabilities.values()):
            raise ValueError("misconception probabilities must be in [0, 1]")
        object.__setattr__(self, "probabilities", MappingProxyType(probabilities))

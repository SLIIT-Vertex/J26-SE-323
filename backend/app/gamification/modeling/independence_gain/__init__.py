"""Public interface for versioned Independence Gain measurement."""

from app.gamification.modeling.independence_gain.calculator import (
    FORMULA_VERSION,
    RawIndependenceGainCalculator,
    calculate_independence_gain,
)
from app.gamification.modeling.independence_gain.contracts import (
    EquivalenceEvidence,
    IndependenceGainCalculator,
    IndependenceGainInput,
    IndependenceGainResult,
)

__all__ = [
    "FORMULA_VERSION",
    "EquivalenceEvidence",
    "IndependenceGainCalculator",
    "IndependenceGainInput",
    "IndependenceGainResult",
    "RawIndependenceGainCalculator",
    "calculate_independence_gain",
]

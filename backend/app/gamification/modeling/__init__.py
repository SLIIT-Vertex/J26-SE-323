"""Deliberate public facade for three independently packaged research models."""

from app.gamification.modeling.independence_gain import (
    FORMULA_VERSION,
    calculate_independence_gain,
)
from app.gamification.modeling.misconception_inference import (
    MISCONCEPTION_MODEL_VERSION,
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.shared import FEATURE_DEFINITION_VERSION, FeatureBuilder
from app.gamification.modeling.support_selection import POLICY_VERSION, SafeSupportPolicy

__all__ = [
    "FEATURE_DEFINITION_VERSION",
    "FORMULA_VERSION",
    "MISCONCEPTION_MODEL_VERSION",
    "POLICY_VERSION",
    "FeatureBuilder",
    "ProbabilisticMisconceptionModel",
    "SafeSupportPolicy",
    "calculate_independence_gain",
]

from app.gamification.domain.types import OutcomeValidity
from app.gamification.modeling.independence_gain.contracts import (
    IndependenceGainInput,
    IndependenceGainResult,
)
from app.gamification.modeling.independence_gain.validity import invalid_reason_codes

FORMULA_VERSION = "raw-independence-gain-v1"


class RawIndependenceGainCalculator:
    """Calculate the versioned raw gain only for a valid unsupported evidence pair."""

    def calculate(self, data: IndependenceGainInput) -> IndependenceGainResult:
        return calculate_independence_gain(data)


def calculate_independence_gain(data: IndependenceGainInput) -> IndependenceGainResult:
    if not 0 <= data.baseline_score <= 1 or not 0 <= data.verification_score <= 1:
        raise ValueError("scores must be between zero and one")
    reasons = invalid_reason_codes(data)
    return IndependenceGainResult(
        validity=OutcomeValidity.INVALID if reasons else OutcomeValidity.VALID,
        raw_gain=None if reasons else data.verification_score - data.baseline_score,
        formula_version=FORMULA_VERSION,
        invalid_reasons=reasons,
    )

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
from app.gamification.modeling.independence_gain.measurement import (
    FORMULA_VERSION as INDEPENDENCE_GAIN_FORMULA_VERSION,
)
from app.gamification.modeling.independence_gain.measurement import (
    AttemptSubmission,
    IndependenceMeasurement,
    ItemRubric,
    MeasurementInput,
    NormalizedEvent,
    PolicyUpdateStatus,
    Presentation,
    ProbeReservation,
    ProbeReservationLedger,
    ScaffoldExposure,
    ScoredAttempt,
    SecondaryMeasurement,
    ServerAuthoritativeScorer,
    SupportWithdrawal,
    assert_unsupported_after_may_begin,
    calculate_measurement,
    development_curriculum_scorer,
    replay_measurement,
    support_dependency_rate,
)

__all__ = [
    "FORMULA_VERSION",
    "INDEPENDENCE_GAIN_FORMULA_VERSION",
    "AttemptSubmission",
    "EquivalenceEvidence",
    "IndependenceGainCalculator",
    "IndependenceGainInput",
    "IndependenceGainResult",
    "IndependenceMeasurement",
    "ItemRubric",
    "MeasurementInput",
    "NormalizedEvent",
    "PolicyUpdateStatus",
    "Presentation",
    "ProbeReservation",
    "ProbeReservationLedger",
    "RawIndependenceGainCalculator",
    "ScaffoldExposure",
    "ScoredAttempt",
    "SecondaryMeasurement",
    "ServerAuthoritativeScorer",
    "SupportWithdrawal",
    "assert_unsupported_after_may_begin",
    "calculate_independence_gain",
    "calculate_measurement",
    "development_curriculum_scorer",
    "replay_measurement",
    "support_dependency_rate",
]

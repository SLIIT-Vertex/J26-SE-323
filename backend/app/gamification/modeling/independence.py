from dataclasses import dataclass
from datetime import datetime

from app.gamification.domain.types import EvidenceSupportState, OutcomeValidity

FORMULA_VERSION = "raw-independence-gain-v1"


@dataclass(frozen=True, slots=True)
class EquivalenceEvidence:
    primary_skill_match: bool
    cognitive_operation_match: bool
    difficulty_band_match: bool
    response_format_match: bool
    language_reviewed: bool
    expected_time_match: bool
    unseen_verification_item: bool
    answer_overlap_acceptable: bool
    equivalence_version: str
    approved: bool


@dataclass(frozen=True, slots=True)
class IndependenceGainInput:
    baseline_score: float
    verification_score: float
    baseline_support_state: EvidenceSupportState
    verification_support_state: EvidenceSupportState
    equivalence: EquivalenceEvidence
    support_delivered: bool
    support_completed: bool
    support_withdrawn_at: datetime | None
    verification_started_at: datetime
    idle_time_ms: int
    maximum_idle_time_ms: int
    ordering_valid: bool = True
    intervening_support: bool = False


@dataclass(frozen=True, slots=True)
class IndependenceGainResult:
    validity: OutcomeValidity
    raw_gain: float | None
    formula_version: str
    invalid_reasons: tuple[str, ...]


def calculate_independence_gain(data: IndependenceGainInput) -> IndependenceGainResult:
    if not 0 <= data.baseline_score <= 1 or not 0 <= data.verification_score <= 1:
        raise ValueError("scores must be between zero and one")
    reasons: list[str] = []
    if data.baseline_support_state is not EvidenceSupportState.UNSUPPORTED:
        reasons.append("BASELINE_NOT_UNSUPPORTED")
    if data.verification_support_state is not EvidenceSupportState.UNSUPPORTED:
        reasons.append("VERIFICATION_NOT_UNSUPPORTED")
    checks = {
        "PAIR_NOT_APPROVED": data.equivalence.approved,
        "PRIMARY_SKILL_MISMATCH": data.equivalence.primary_skill_match,
        "COGNITIVE_OPERATION_MISMATCH": data.equivalence.cognitive_operation_match,
        "DIFFICULTY_BAND_MISMATCH": data.equivalence.difficulty_band_match,
        "RESPONSE_FORMAT_MISMATCH": data.equivalence.response_format_match,
        "LANGUAGE_NOT_REVIEWED": data.equivalence.language_reviewed,
        "EXPECTED_TIME_MISMATCH": data.equivalence.expected_time_match,
        "VERIFICATION_ITEM_PREVIOUSLY_SEEN": data.equivalence.unseen_verification_item,
        "ANSWER_CLUE_OVERLAP": data.equivalence.answer_overlap_acceptable,
    }
    reasons.extend(reason for reason, passed in checks.items() if not passed)
    if not data.support_delivered:
        reasons.append("SUPPORT_NOT_DELIVERED")
    if not data.support_completed:
        reasons.append("SUPPORT_NOT_COMPLETED")
    if data.support_withdrawn_at is None:
        reasons.append("SUPPORT_NOT_WITHDRAWN")
    elif data.support_withdrawn_at > data.verification_started_at:
        reasons.append("SUPPORT_VISIBLE_DURING_VERIFICATION")
    if data.idle_time_ms > data.maximum_idle_time_ms:
        reasons.append("IDLE_THRESHOLD_EXCEEDED")
    if not data.ordering_valid:
        reasons.append("CLIENT_ORDERING_CORRUPT")
    if data.intervening_support:
        reasons.append("INTERVENING_SUPPORT")
    return IndependenceGainResult(
        validity=OutcomeValidity.INVALID if reasons else OutcomeValidity.VALID,
        raw_gain=None if reasons else data.verification_score - data.baseline_score,
        formula_version=FORMULA_VERSION,
        invalid_reasons=tuple(reasons),
    )

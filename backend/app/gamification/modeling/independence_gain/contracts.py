from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.gamification.domain.types import EvidenceSupportState, OutcomeValidity


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


class IndependenceGainCalculator(Protocol):
    """Measurement capability consumed by episode orchestration."""

    def calculate(self, data: IndependenceGainInput) -> IndependenceGainResult: ...

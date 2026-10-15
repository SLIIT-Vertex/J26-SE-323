from dataclasses import dataclass

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.modeling.shared.contracts import MisconceptionDistribution
from app.gamification.modeling.support_selection.contracts import SupportCandidate

# Provisional until labelled episodes can calibrate a floor. Not an empirical threshold.
PROVISIONAL_MISCONCEPTION_FLOOR = 0.05


@dataclass(frozen=True, slots=True)
class CandidateEligibility:
    candidate: SupportCandidate
    reason_codes: tuple[str, ...]
    matched_codes: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return not self.reason_codes


def evaluate_candidate_eligibility(
    *,
    snapshot: FeatureSnapshotRecord,
    belief: MisconceptionDistribution,
    candidates: tuple[SupportCandidate, ...],
    language: str,
    probability_floor: float = PROVISIONAL_MISCONCEPTION_FLOOR,
) -> tuple[CandidateEligibility, ...]:
    """Apply approval and compatibility gates before any candidate is scored or selected.

    A scaffold matches when any targeted misconception is above the floor. The top code
    alone does not decide eligibility. Matched codes are recorded separately from failure
    reasons so a match does not make the candidate ineligible.
    """

    if not 0 <= probability_floor <= 1:
        raise ValueError("probability floor must be between zero and one")
    results: list[CandidateEligibility] = []
    for candidate in candidates:
        reasons: list[str] = []
        matched = tuple(
            sorted(
                code
                for code in candidate.misconception_codes
                if belief.probabilities.get(code, 0.0) > probability_floor
            )
        )
        if not candidate.approved:
            reasons.append("CONTENT_NOT_APPROVED")
        if language not in candidate.languages:
            reasons.append("LANGUAGE_UNAVAILABLE")
        if str(snapshot.skill_id) not in candidate.skill_ids:
            reasons.append("SKILL_NOT_SUPPORTED")
        if candidate.misconception_codes and not matched:
            reasons.append("MISCONCEPTION_NOT_SUPPORTED")
        results.append(CandidateEligibility(candidate, tuple(reasons), matched))
    return tuple(results)

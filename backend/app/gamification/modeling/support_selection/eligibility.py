from dataclasses import dataclass

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.modeling.shared.contracts import MisconceptionDistribution
from app.gamification.modeling.support_selection.contracts import SupportCandidate


@dataclass(frozen=True, slots=True)
class CandidateEligibility:
    candidate: SupportCandidate
    reason_codes: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.reason_codes


def evaluate_candidate_eligibility(
    *,
    snapshot: FeatureSnapshotRecord,
    belief: MisconceptionDistribution,
    candidates: tuple[SupportCandidate, ...],
    language: str,
) -> tuple[CandidateEligibility, ...]:
    """Apply approval and compatibility gates before any candidate is scored or selected."""

    top_code = max(belief.probabilities, key=belief.probabilities.__getitem__)
    results: list[CandidateEligibility] = []
    for candidate in candidates:
        reasons = []
        if not candidate.approved:
            reasons.append("CONTENT_NOT_APPROVED")
        if language not in candidate.languages:
            reasons.append("LANGUAGE_UNAVAILABLE")
        if str(snapshot.skill_id) not in candidate.skill_ids:
            reasons.append("SKILL_NOT_SUPPORTED")
        if candidate.misconception_codes and top_code not in candidate.misconception_codes:
            reasons.append("MISCONCEPTION_NOT_SUPPORTED")
        results.append(CandidateEligibility(candidate, tuple(reasons)))
    return tuple(results)

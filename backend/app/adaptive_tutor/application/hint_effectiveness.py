"""Derive previous-hint effectiveness from researcher-reviewed attempts (provisional rule).

Controller V1 reads ``previous_hint_effective`` as "observable progress after the prior
assistance" (docs/adaptive-tutor/transition-policy.md). This rule only compares two reviewed
attempts on the same interaction; it never invents an outcome:

- the attempt after the hint is correct                         -> EFFECTIVE
- both attempts were scored under the same severity policy and
  the error became less severe                                  -> EFFECTIVE
- same policy, error equally or more severe                     -> INEFFECTIVE
- no reviewed attempt before the hint, or different policies    -> INSUFFICIENT_EVIDENCE

INSUFFICIENT_EVIDENCE reaches the Controller as ``None`` (unknown), never as ``False``.
The rule is a research design assumption pending pedagogical review, not a validated measure.
"""

from dataclasses import dataclass
from enum import StrEnum

HINT_EFFECTIVENESS_RULE_VERSION = "research-hint-effectiveness-v1"


class HintEffectiveness(StrEnum):
    EFFECTIVE = "EFFECTIVE"
    INEFFECTIVE = "INEFFECTIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class ReviewedAttempt:
    is_correct: bool
    severity_value: float
    severity_policy_version: str


def assess_hint_effectiveness(
    *,
    before_hint: ReviewedAttempt | None,
    after_hint: ReviewedAttempt,
) -> HintEffectiveness:
    if after_hint.is_correct:
        return HintEffectiveness.EFFECTIVE
    if (
        before_hint is None
        or before_hint.severity_policy_version != after_hint.severity_policy_version
    ):
        return HintEffectiveness.INSUFFICIENT_EVIDENCE
    if after_hint.severity_value < before_hint.severity_value:
        return HintEffectiveness.EFFECTIVE
    return HintEffectiveness.INEFFECTIVE


def as_controller_evidence(effectiveness: HintEffectiveness | None) -> bool | None:
    """Map a recorded status to Controller V1's nullable boolean without guessing."""

    if effectiveness is HintEffectiveness.EFFECTIVE:
        return True
    if effectiveness is HintEffectiveness.INEFFECTIVE:
        return False
    return None

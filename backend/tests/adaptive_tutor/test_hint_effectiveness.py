import pytest

from app.adaptive_tutor.application.hint_effectiveness import (
    HintEffectiveness,
    ReviewedAttempt,
    as_controller_evidence,
    assess_hint_effectiveness,
)

POLICY = "controlled-research-severity-v1"


def attempt(severity: float, *, correct: bool = False, policy: str = POLICY) -> ReviewedAttempt:
    return ReviewedAttempt(
        is_correct=correct, severity_value=severity, severity_policy_version=policy
    )


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (attempt(0.7), attempt(0.0, correct=True), HintEffectiveness.EFFECTIVE),
        (None, attempt(0.0, correct=True), HintEffectiveness.EFFECTIVE),
        (attempt(0.7), attempt(0.3), HintEffectiveness.EFFECTIVE),
        (attempt(0.7), attempt(0.7), HintEffectiveness.INEFFECTIVE),
        (attempt(0.4), attempt(0.8), HintEffectiveness.INEFFECTIVE),
        (None, attempt(0.7), HintEffectiveness.INSUFFICIENT_EVIDENCE),
        (
            attempt(0.7, policy="other-policy"),
            attempt(0.3),
            HintEffectiveness.INSUFFICIENT_EVIDENCE,
        ),
    ],
)
def test_effectiveness_compares_reviewed_attempts_only(
    before: ReviewedAttempt | None,
    after: ReviewedAttempt,
    expected: HintEffectiveness,
) -> None:
    assert assess_hint_effectiveness(before_hint=before, after_hint=after) is expected


def test_insufficient_evidence_reaches_the_controller_as_unknown_not_false() -> None:
    assert as_controller_evidence(HintEffectiveness.EFFECTIVE) is True
    assert as_controller_evidence(HintEffectiveness.INEFFECTIVE) is False
    assert as_controller_evidence(HintEffectiveness.INSUFFICIENT_EVIDENCE) is None
    assert as_controller_evidence(None) is None

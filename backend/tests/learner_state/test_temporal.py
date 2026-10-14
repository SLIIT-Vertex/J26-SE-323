import pytest

from app.learner_state.domain.temporal import (
    confusion_temporal_decision,
    disengagement_temporal_decision,
)

TRUSTED = [0.8, 0.8, 0.8]
PERSISTENT = [0.7, 0.7, 0.7]


def confusion(
    evidence: list[float],
    confidence: list[float] = TRUSTED,
    progress: list[float | None] | None = None,
) -> tuple[str, str]:
    decision = confusion_temporal_decision(evidence, confidence, progress)
    return decision.state, decision.support_need


def test_low_average_confidence_is_uncertain() -> None:
    assert confusion([0.9, 0.9, 0.9], [0.3, 0.3, 0.3]) == (
        "uncertain",
        "collect_more_evidence",
    )


def test_falling_evidence_with_positive_trend_is_recovering() -> None:
    assert confusion([0.8, 0.8, 0.3]) == ("recovering_from_confusion", "monitor")


def test_single_positive_window_is_transient() -> None:
    assert confusion([0.2, 0.2, 0.7]) == ("transient_confusion", "monitor")


def test_negative_evidence_is_no_confusion() -> None:
    assert confusion([0.2, 0.2, 0.2]) == ("no_confusion", "none")


def test_low_confidence_windows_do_not_count_as_persistent() -> None:
    decision = confusion_temporal_decision(PERSISTENT, [0.45, 0.45, 0.9])

    assert decision.persistent_count == 1
    assert decision.state == "transient_confusion"


def test_persistent_confusion_with_rising_progress_is_productive() -> None:
    assert confusion(PERSISTENT, progress=[0.30, 0.32, 0.35]) == (
        "productive_confusion",
        "monitor",
    )


@pytest.mark.parametrize(
    "progress",
    [
        [0.30, 0.31, 0.34],
        [0.60, 0.60, 0.60],
        [0.60, 0.50, 0.40],
    ],
)
def test_persistent_confusion_without_enough_progress_needs_support(
    progress: list[float | None],
) -> None:
    assert confusion(PERSISTENT, progress=progress) == (
        "intervention_worthy_confusion",
        "request_tutor_support",
    )


@pytest.mark.parametrize(
    "progress",
    [
        None,
        [None, None, None],
        [None, None, 0.9],
    ],
)
def test_unknown_progress_is_treated_as_intervention_worthy(
    progress: list[float | None] | None,
) -> None:
    decision = confusion_temporal_decision(PERSISTENT, TRUSTED, progress)

    assert decision.progress_gain is None
    assert decision.state == "intervention_worthy_confusion"


def test_progress_gain_ignores_missing_values_and_old_windows() -> None:
    decision = confusion_temporal_decision(
        [0.7, 0.7, 0.7, 0.7],
        [0.8, 0.8, 0.8, 0.8],
        [0.0, 0.40, None, 0.50],
    )

    assert decision.progress_gain == pytest.approx(0.10)
    assert decision.state == "productive_confusion"


def test_min_progress_gain_is_configurable() -> None:
    decision = confusion_temporal_decision(
        PERSISTENT,
        TRUSTED,
        [0.30, 0.32, 0.35],
        min_progress_gain=0.10,
    )

    assert decision.state == "intervention_worthy_confusion"


def test_temporal_summary_uses_confidence_weighted_recent_windows() -> None:
    decision = confusion_temporal_decision(
        [0.0, 0.2, 0.8, 0.8],
        [0.9, 0.5, 1.0, 1.0],
    )

    assert decision.temporal_score == pytest.approx((0.1 + 0.8 + 0.8) / 2.5)
    assert decision.avg_confidence == pytest.approx(2.5 / 3.0)
    assert decision.persistent_count == 2


def test_history_lengths_are_validated() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        confusion_temporal_decision([], [])

    with pytest.raises(ValueError, match="equal length"):
        confusion_temporal_decision([0.5, 0.5], [0.5])


@pytest.mark.parametrize(
    ("evidence", "confidence", "expected"),
    [
        ([0.9, 0.9, 0.9], [0.3, 0.3, 0.3], ("uncertain", "collect_more_evidence")),
        ([0.8, 0.8, 0.3], TRUSTED, ("recovering_engagement", "monitor")),
        (PERSISTENT, TRUSTED, ("persistent_disengagement", "request_reengagement_support")),
        ([0.2, 0.2, 0.7], TRUSTED, ("transient_disengagement", "monitor")),
        ([0.2, 0.2, 0.2], TRUSTED, ("engaged", "none")),
    ],
)
def test_disengagement_states(
    evidence: list[float],
    confidence: list[float],
    expected: tuple[str, str],
) -> None:
    decision = disengagement_temporal_decision(evidence, confidence)

    assert (decision.state, decision.support_need) == expected

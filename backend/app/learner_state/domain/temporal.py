from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TemporalDecision:
    temporal_score: float
    avg_confidence: float
    persistent_count: int
    state: str
    support_need: str
    recent_progress: float | None = None


def _validate_history(
    fused_evidence: Sequence[float],
    fusion_confidence: Sequence[float],
) -> None:
    if not fused_evidence:
        raise ValueError("fused_evidence history cannot be empty")

    if len(fused_evidence) != len(fusion_confidence):
        raise ValueError(
            "fused_evidence and fusion_confidence must have equal length"
        )


def _temporal_summary(
    fused_evidence: Sequence[float],
    fusion_confidence: Sequence[float],
    window_size: int,
    evidence_threshold: float,
    min_confidence: float,
) -> tuple[float, float, int]:
    if window_size < 1:
        raise ValueError("window_size must be at least 1")

    recent_evidence = list(
        fused_evidence[-window_size:]
    )

    recent_confidence = list(
        fusion_confidence[-window_size:]
    )

    confidence_sum = sum(recent_confidence)

    if confidence_sum > 0:
        temporal_score = sum(
            evidence * confidence
            for evidence, confidence in zip(
                recent_evidence,
                recent_confidence,
                strict=True,
            )
        ) / confidence_sum
    else:
        temporal_score = 0.5

    avg_confidence = (
        sum(recent_confidence)
        / len(recent_confidence)
    )

    persistent_count = sum(
        1
        for evidence, confidence in zip(
            recent_evidence,
            recent_confidence,
            strict=True,
        )
        if evidence >= evidence_threshold
        and confidence >= min_confidence
    )

    return (
        temporal_score,
        avg_confidence,
        persistent_count,
    )


def confusion_temporal_decision(
    fused_evidence: Sequence[float],
    fusion_confidence: Sequence[float],
    task_progress: Sequence[float | None] | None = None,
    *,
    window_size: int = 3,
    confusion_threshold: float = 0.50,
    intervention_threshold: float = 0.60,
    min_persistent_windows: int = 2,
    min_confidence: float = 0.50,
) -> TemporalDecision:
    _validate_history(
        fused_evidence,
        fusion_confidence,
    )

    temporal_score, avg_confidence, persistent_count = (
        _temporal_summary(
            fused_evidence,
            fusion_confidence,
            window_size,
            confusion_threshold,
            min_confidence,
        )
    )

    current_evidence = fused_evidence[-1]
    recent_progress: float | None = None

    if task_progress is not None:
        recent_values = [
            value
            for value in task_progress[-window_size:]
            if value is not None
        ]

        if recent_values:
            recent_progress = (
                sum(recent_values)
                / len(recent_values)
            )

    if avg_confidence < 0.40:
        state = "uncertain"
        support_need = "collect_more_evidence"

    elif (
        current_evidence < confusion_threshold
        and temporal_score >= confusion_threshold
    ):
        state = "recovering_from_confusion"
        support_need = "monitor"

    elif (
        current_evidence >= confusion_threshold
        and temporal_score >= intervention_threshold
        and persistent_count >= min_persistent_windows
    ):
        if (
            recent_progress is not None
            and recent_progress >= 0.50
        ):
            state = "productive_confusion"
            support_need = "monitor"
        else:
            state = "intervention_worthy_confusion"
            support_need = "request_tutor_support"

    elif current_evidence >= confusion_threshold:
        state = "transient_confusion"
        support_need = "monitor"

    else:
        state = "no_confusion"
        support_need = "none"

    return TemporalDecision(
        temporal_score=temporal_score,
        avg_confidence=avg_confidence,
        persistent_count=persistent_count,
        state=state,
        support_need=support_need,
        recent_progress=recent_progress,
    )


def disengagement_temporal_decision(
    fused_evidence: Sequence[float],
    fusion_confidence: Sequence[float],
    *,
    window_size: int = 3,
    disengagement_threshold: float = 0.50,
    intervention_threshold: float = 0.60,
    min_persistent_windows: int = 2,
    min_confidence: float = 0.50,
) -> TemporalDecision:
    _validate_history(
        fused_evidence,
        fusion_confidence,
    )

    temporal_score, avg_confidence, persistent_count = (
        _temporal_summary(
            fused_evidence,
            fusion_confidence,
            window_size,
            disengagement_threshold,
            min_confidence,
        )
    )

    current_evidence = fused_evidence[-1]

    if avg_confidence < 0.40:
        state = "uncertain"
        support_need = "collect_more_evidence"

    elif (
        current_evidence < disengagement_threshold
        and temporal_score >= disengagement_threshold
    ):
        state = "recovering_engagement"
        support_need = "monitor"

    elif (
        current_evidence >= disengagement_threshold
        and temporal_score >= intervention_threshold
        and persistent_count >= min_persistent_windows
    ):
        state = "persistent_disengagement"
        support_need = "request_reengagement_support"

    elif current_evidence >= disengagement_threshold:
        state = "transient_disengagement"
        support_need = "monitor"

    else:
        state = "engaged"
        support_need = "none"

    return TemporalDecision(
        temporal_score=temporal_score,
        avg_confidence=avg_confidence,
        persistent_count=persistent_count,
        state=state,
        support_need=support_need,
    )
from collections.abc import Sequence
from dataclasses import dataclass

from app.learner_state.domain.fusion import (
    reliability_aware_fusion,
    threshold_centered_evidence,
)
from app.learner_state.domain.temporal import (
    disengagement_temporal_decision,
)


@dataclass(frozen=True)
class DisengagementResult:
    visual_evidence: float
    behavior_evidence: float

    visual_weight: float
    behavior_weight: float

    fused_evidence: float
    modality_disagreement: float
    fusion_confidence: float

    temporal_score: float
    persistent_count: int

    state: str
    support_need: str


def evaluate_disengagement_window(
    *,
    visual_probability: float,
    behavior_probability: float,
    visual_reliability: float,
    behavior_reliability: float,
    previous_fused_evidence: Sequence[float] = (),
    previous_fusion_confidence: Sequence[float] = (),
    visual_threshold: float = 0.54,
    behavior_threshold: float = 0.53,
    temporal_window_size: int = 3,
    disengagement_threshold: float = 0.50,
    intervention_threshold: float = 0.60,
    min_persistent_windows: int = 2,
    min_confidence: float = 0.50,
) -> DisengagementResult:
    """
    Evaluate disengagement for one learner-state window.

    Previous temporal history is supplied by the application layer.
    This function itself does not store session state.
    """

    # 1. Normalize model probabilities around their
    #    validation-selected thresholds.

    visual_evidence = threshold_centered_evidence(
        visual_probability,
        visual_threshold,
    )

    behavior_evidence = threshold_centered_evidence(
        behavior_probability,
        behavior_threshold,
    )

    # 2. Reliability-aware multimodal fusion

    fusion = reliability_aware_fusion(
        visual_evidence=visual_evidence,
        behavior_evidence=behavior_evidence,
        visual_reliability=visual_reliability,
        behavior_reliability=behavior_reliability,
    )

    # 3. Add current window to temporal history

    fused_history = [
        *previous_fused_evidence,
        fusion.fused_evidence,
    ]

    confidence_history = [
        *previous_fusion_confidence,
        fusion.fusion_confidence,
    ]

    # 4. Temporal disengagement decision

    temporal = disengagement_temporal_decision(
        fused_evidence=fused_history,
        fusion_confidence=confidence_history,
        window_size=temporal_window_size,
        disengagement_threshold=disengagement_threshold,
        intervention_threshold=intervention_threshold,
        min_persistent_windows=min_persistent_windows,
        min_confidence=min_confidence,
    )

    # 5. Return final domain result

    return DisengagementResult(
        visual_evidence=visual_evidence,
        behavior_evidence=behavior_evidence,
        visual_weight=fusion.visual_weight,
        behavior_weight=fusion.behavior_weight,
        fused_evidence=fusion.fused_evidence,
        modality_disagreement=fusion.disagreement,
        fusion_confidence=fusion.fusion_confidence,
        temporal_score=temporal.temporal_score,
        persistent_count=temporal.persistent_count,
        state=temporal.state,
        support_need=temporal.support_need,
    )
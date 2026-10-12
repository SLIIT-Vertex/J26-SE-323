from dataclasses import dataclass


@dataclass(frozen=True)
class FusionResult:
    visual_weight: float
    behavior_weight: float
    fused_evidence: float
    disagreement: float
    weighted_reliability: float
    conflict_strength: float
    fusion_confidence: float


def _clip_01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def threshold_centered_evidence(
    probability: float,
    threshold: float,
) -> float:
    """
    Convert a model probability into normalized evidence where the
    model's selected decision threshold maps to 0.5.
    """

    probability = _clip_01(probability)
    threshold = float(threshold)

    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1")

    if probability <= threshold:
        return 0.5 * (probability / threshold)

    return 0.5 + 0.5 * (
        (probability - threshold) / (1.0 - threshold)
    )


def reliability_aware_fusion(
    visual_evidence: float,
    behavior_evidence: float,
    visual_reliability: float,
    behavior_reliability: float,
) -> FusionResult:
    """
    Fuse visual and behavioural evidence using reliability-based
    dynamic weighting and modality-conflict handling.
    """

    visual_evidence = _clip_01(visual_evidence)
    behavior_evidence = _clip_01(behavior_evidence)

    visual_reliability = _clip_01(visual_reliability)
    behavior_reliability = _clip_01(behavior_reliability)

    total_reliability = visual_reliability + behavior_reliability

    if total_reliability == 0.0:
        visual_weight = 0.5
        behavior_weight = 0.5
    else:
        visual_weight = visual_reliability / total_reliability
        behavior_weight = behavior_reliability / total_reliability

    fused_evidence = (
        visual_weight * visual_evidence
        + behavior_weight * behavior_evidence
    )

    disagreement = abs(
        visual_evidence - behavior_evidence
    )

    shared_reliability = min(
        visual_reliability,
        behavior_reliability,
    )

    conflict_strength = (
        disagreement * shared_reliability
    )

    weighted_reliability = (
        visual_weight * visual_reliability
        + behavior_weight * behavior_reliability
    )

    fusion_confidence = _clip_01(
        weighted_reliability
        * (1.0 - conflict_strength)
    )

    return FusionResult(
        visual_weight=visual_weight,
        behavior_weight=behavior_weight,
        fused_evidence=fused_evidence,
        disagreement=disagreement,
        weighted_reliability=weighted_reliability,
        conflict_strength=conflict_strength,
        fusion_confidence=fusion_confidence,
    )
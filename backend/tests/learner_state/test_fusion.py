import pytest

from app.learner_state.domain.fusion import (
    reliability_aware_fusion,
    threshold_centered_evidence,
)


@pytest.mark.parametrize(
    ("probability", "threshold", "expected"),
    [
        (0.0, 0.79, 0.0),
        (0.79, 0.79, 0.5),
        (1.0, 0.79, 1.0),
        (0.25, 0.50, 0.25),
        (0.895, 0.79, 0.75),
    ],
)
def test_threshold_centered_evidence_maps_threshold_to_half(
    probability: float,
    threshold: float,
    expected: float,
) -> None:
    assert threshold_centered_evidence(probability, threshold) == pytest.approx(expected)


def test_threshold_centered_evidence_clips_probability() -> None:
    assert threshold_centered_evidence(-0.2, 0.5) == 0.0
    assert threshold_centered_evidence(1.4, 0.5) == 1.0


@pytest.mark.parametrize("threshold", [0.0, 1.0, -0.1, 1.5])
def test_threshold_centered_evidence_rejects_invalid_threshold(threshold: float) -> None:
    with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
        threshold_centered_evidence(0.5, threshold)


def test_fusion_weights_follow_reliability() -> None:
    result = reliability_aware_fusion(
        visual_evidence=0.8,
        behavior_evidence=0.2,
        visual_reliability=0.9,
        behavior_reliability=0.3,
    )

    assert result.visual_weight == pytest.approx(0.75)
    assert result.behavior_weight == pytest.approx(0.25)
    assert result.fused_evidence == pytest.approx(0.75 * 0.8 + 0.25 * 0.2)


def test_unreliable_visual_modality_is_ignored() -> None:
    result = reliability_aware_fusion(
        visual_evidence=0.9,
        behavior_evidence=0.3,
        visual_reliability=0.0,
        behavior_reliability=0.7,
    )

    assert result.visual_weight == 0.0
    assert result.fused_evidence == pytest.approx(0.3)
    assert result.conflict_strength == 0.0
    assert result.fusion_confidence == pytest.approx(0.7)


def test_zero_reliability_uses_equal_weights_and_zero_confidence() -> None:
    result = reliability_aware_fusion(
        visual_evidence=0.8,
        behavior_evidence=0.4,
        visual_reliability=0.0,
        behavior_reliability=0.0,
    )

    assert result.visual_weight == 0.5
    assert result.behavior_weight == 0.5
    assert result.fused_evidence == pytest.approx(0.6)
    assert result.fusion_confidence == 0.0


def test_agreeing_reliable_modalities_keep_full_confidence() -> None:
    result = reliability_aware_fusion(
        visual_evidence=0.7,
        behavior_evidence=0.7,
        visual_reliability=0.8,
        behavior_reliability=0.8,
    )

    assert result.disagreement == 0.0
    assert result.fusion_confidence == pytest.approx(0.8)


def test_conflict_between_reliable_modalities_reduces_confidence() -> None:
    result = reliability_aware_fusion(
        visual_evidence=0.9,
        behavior_evidence=0.1,
        visual_reliability=0.8,
        behavior_reliability=0.8,
    )

    assert result.disagreement == pytest.approx(0.8)
    assert result.conflict_strength == pytest.approx(0.64)
    assert result.fusion_confidence == pytest.approx(0.8 * (1.0 - 0.64))


def test_repository_example_matches_documented_values() -> None:
    result = reliability_aware_fusion(
        visual_evidence=threshold_centered_evidence(0.5223562717437744, 0.50),
        behavior_evidence=threshold_centered_evidence(0.19043080508708954, 0.79),
        visual_reliability=0.95,
        behavior_reliability=0.63,
    )

    assert result.fused_evidence == pytest.approx(0.3621, abs=1e-4)
    assert result.fusion_confidence == pytest.approx(0.6142, abs=1e-4)

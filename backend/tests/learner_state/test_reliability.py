import pytest

from app.learner_state.infrastructure.reliability import (
    PITCH_Q75,
    PITCH_Q95,
    ROLL_Q95,
    RT_Q01,
    RT_Q99,
    YAW_Q95,
    calculate_behavior_reliability,
    calculate_visual_reliability,
)


def test_visible_face_with_normal_pose_is_fully_reliable() -> None:
    result = calculate_visual_reliability(
        mean_abs_pitch=0.0,
        mean_abs_yaw=0.0,
        mean_abs_roll=0.0,
        face_visibility_ratio=1.0,
    )

    assert result.pose_quality == 1.0
    assert result.reliability == 1.0


def test_extreme_pose_halves_visual_reliability() -> None:
    result = calculate_visual_reliability(
        mean_abs_pitch=PITCH_Q95,
        mean_abs_yaw=YAW_Q95,
        mean_abs_roll=ROLL_Q95,
        face_visibility_ratio=1.0,
    )

    assert result.pose_quality == 0.0
    assert result.reliability == pytest.approx(0.5)


def test_pose_quality_decreases_linearly_between_quantiles() -> None:
    result = calculate_visual_reliability(
        mean_abs_pitch=(PITCH_Q75 + PITCH_Q95) / 2.0,
        mean_abs_yaw=0.0,
        mean_abs_roll=0.0,
        face_visibility_ratio=1.0,
    )

    assert result.pose_quality == pytest.approx(2.5 / 3.0)


def test_hidden_face_makes_visual_modality_unreliable() -> None:
    result = calculate_visual_reliability(
        mean_abs_pitch=0.0,
        mean_abs_yaw=0.0,
        mean_abs_roll=0.0,
        face_visibility_ratio=0.0,
    )

    assert result.reliability == 0.0


def behavior_reliability(**overrides: float) -> float:
    data = {
        "ms_first_response": 10000.0,
        "overlap_time": 10000.0,
        "bottom_hint_missing": 0.0,
        "history_confidence": 1.0,
    }
    data.update(overrides)
    return calculate_behavior_reliability(**data).reliability


def test_complete_behaviour_with_full_history_is_fully_reliable() -> None:
    assert behavior_reliability() == pytest.approx(1.0)


def test_first_window_with_missing_bottom_hint() -> None:
    reliability = behavior_reliability(bottom_hint_missing=1.0, history_confidence=0.0)

    assert reliability == pytest.approx(0.9 * 0.7)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"ms_first_response": RT_Q01 - 1.0}, 0.9),
        ({"ms_first_response": RT_Q99 + 1.0}, 0.9),
        ({"overlap_time": -1.0}, 0.5),
        ({"ms_first_response": -1.0}, 0.4),
    ],
)
def test_timing_penalties(overrides: dict[str, float], expected: float) -> None:
    assert behavior_reliability(**overrides) == pytest.approx(expected)


def test_history_factor_grows_with_history_confidence() -> None:
    no_history = calculate_behavior_reliability(
        ms_first_response=10000.0,
        overlap_time=10000.0,
        bottom_hint_missing=0.0,
        history_confidence=0.0,
    )
    half_history = calculate_behavior_reliability(
        ms_first_response=10000.0,
        overlap_time=10000.0,
        bottom_hint_missing=0.0,
        history_confidence=0.5,
    )

    assert no_history.history_factor == pytest.approx(0.70)
    assert half_history.history_factor == pytest.approx(0.85)
    assert behavior_reliability(history_confidence=3.0) == pytest.approx(1.0)

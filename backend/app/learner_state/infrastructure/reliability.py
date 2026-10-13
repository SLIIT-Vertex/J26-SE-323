from dataclasses import dataclass
from typing import Final

PITCH_Q75: Final = 10.6009
PITCH_Q95: Final = 18.1916

YAW_Q75: Final = 11.3656
YAW_Q95: Final = 20.6081

ROLL_Q75: Final = 6.3687
ROLL_Q95: Final = 11.2431

RT_Q01: Final = 1969.0
RT_Q99: Final = 377326.28

def _clip_01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _pose_dimension_quality(
    value: float,
    q75: float,
    q95: float,
) -> float:
    normalized = (abs(value) - q75) / (q95 - q75)
    return 1.0 - _clip_01(normalized)


@dataclass(frozen=True)
class VisualReliabilityResult:
    pose_quality: float
    reliability: float


def calculate_visual_reliability(
    *,
    mean_abs_pitch: float,
    mean_abs_yaw: float,
    mean_abs_roll: float,
    face_visibility_ratio: float,
) -> VisualReliabilityResult:
    pitch_quality = _pose_dimension_quality(
        mean_abs_pitch,
        PITCH_Q75,
        PITCH_Q95,
    )

    yaw_quality = _pose_dimension_quality(
        mean_abs_yaw,
        YAW_Q75,
        YAW_Q95,
    )

    roll_quality = _pose_dimension_quality(
        mean_abs_roll,
        ROLL_Q75,
        ROLL_Q95,
    )

    pose_quality = (
        pitch_quality
        + yaw_quality
        + roll_quality
    ) / 3.0

    visibility = _clip_01(face_visibility_ratio)

    reliability = visibility * (
        0.5 + (0.5 * pose_quality)
    )

    return VisualReliabilityResult(
        pose_quality=_clip_01(pose_quality),
        reliability=_clip_01(reliability),
    )

@dataclass(frozen=True)
class BehaviorReliabilityResult:
    data_quality: float
    history_factor: float
    reliability: float


def calculate_behavior_reliability(
    *,
    ms_first_response: float,
    overlap_time: float,
    bottom_hint_missing: float,
    history_confidence: float,
) -> BehaviorReliabilityResult:
    """
    Estimate the reliability of the current behavioural observation.

    Reliability is reduced when:
    - bottom-hint information is missing
    - timing values are invalid
    - response time is outside the train-derived 1st/99th percentiles
    - little learner history is available
    """

    data_quality = 1.0

    if bottom_hint_missing >= 0.5:
        data_quality -= 0.10

    if ms_first_response < 0.0 or overlap_time < 0.0:
        data_quality -= 0.50

    if ms_first_response < RT_Q01:
        data_quality -= 0.10

    if ms_first_response > RT_Q99:
        data_quality -= 0.10

    data_quality = _clip_01(data_quality)

    history_confidence = _clip_01(history_confidence)

    history_factor = 0.70 + (0.30 * history_confidence)

    reliability = data_quality * history_factor

    return BehaviorReliabilityResult(
        data_quality=data_quality,
        history_factor=history_factor,
        reliability=_clip_01(reliability),
    )
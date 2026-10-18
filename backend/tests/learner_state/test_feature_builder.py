from dataclasses import replace
from math import log

import pytest

from app.learner_state.infrastructure.feature_builder import (
    BOTTOM_HINT_TRAIN_MEDIAN,
    HISTORY_WINDOW,
    MIN_BASELINE_HISTORY,
    BehaviorObservation,
    build_confusion_behavior_features,
    build_disengagement_behavior_features,
)
from app.learner_state.infrastructure.model_loader import (
    CONFUSION_BEHAVIOR_FEATURES,
    DISENGAGEMENT_BEHAVIOR_FEATURES,
)

DEVIATION_FEATURES = (
    "recent_log_rt",
    "recent_accuracy",
    "recent_attempts",
    "recent_hints",
    "rt_deviation",
    "attempt_deviation",
    "hint_deviation",
    "accuracy_deviation",
)


def observation(**overrides: object) -> BehaviorObservation:
    data: dict[str, object] = {
        "correct": 1.0,
        "bottom_hint": 0.0,
        "hint_count": 0.0,
        "attempt_count": 1.0,
        "ms_first_response": 999.0,
        "overlap_time": 5000.0,
        "original": 1.0,
    }
    data.update(overrides)
    return BehaviorObservation(**data)


def test_confusion_features_match_model_feature_order() -> None:
    features = build_confusion_behavior_features(observation())

    assert tuple(features) == CONFUSION_BEHAVIOR_FEATURES


def test_missing_bottom_hint_is_flagged() -> None:
    assert build_confusion_behavior_features(observation())["bottom_hint_missing"] == 0.0

    missing = build_confusion_behavior_features(observation(bottom_hint=None))

    assert missing["bottom_hint"] == BOTTOM_HINT_TRAIN_MEDIAN
    assert missing["bottom_hint_missing"] == 1.0


def test_missing_bottom_hint_is_filled_for_disengagement_too() -> None:
    features = build_disengagement_behavior_features(observation(bottom_hint=None), [])

    assert features["bottom_hint"] == BOTTOM_HINT_TRAIN_MEDIAN
    assert features["bottom_hint_missing"] == 1.0


def test_disengagement_features_match_model_feature_order() -> None:
    features = build_disengagement_behavior_features(observation(), [])

    assert tuple(features) == DISENGAGEMENT_BEHAVIOR_FEATURES


def test_baseline_is_unavailable_below_minimum_history() -> None:
    history = [observation()] * (MIN_BASELINE_HISTORY - 1)

    features = build_disengagement_behavior_features(observation(), history)

    assert features["baseline_available"] == 0.0
    assert features["history_confidence"] == pytest.approx(
        (MIN_BASELINE_HISTORY - 1) / HISTORY_WINDOW
    )
    assert all(features[name] is None for name in DEVIATION_FEATURES)


def test_deviation_from_learner_baseline() -> None:
    history = [observation()] * MIN_BASELINE_HISTORY
    current = observation(
        correct=0.0,
        hint_count=3.0,
        attempt_count=4.0,
        ms_first_response=9999.0,
    )

    features = build_disengagement_behavior_features(current, history)

    assert features["baseline_available"] == 1.0
    assert features["recent_log_rt"] == pytest.approx(log(1000.0))
    assert features["rt_deviation"] == pytest.approx(log(10.0))
    assert features["accuracy_deviation"] == pytest.approx(-1.0)
    assert features["hint_deviation"] == pytest.approx(3.0)
    assert features["attempt_deviation"] == pytest.approx(3.0)


def test_baseline_uses_only_most_recent_history_window() -> None:
    older = [observation(correct=1.0)] * 10
    recent = [observation(correct=0.0)] * HISTORY_WINDOW

    features = build_disengagement_behavior_features(observation(), older + recent)

    assert features["history_confidence"] == 1.0
    assert features["recent_accuracy"] == 0.0


def test_negative_response_time_is_treated_as_zero_in_log_features() -> None:
    history = [observation()] * MIN_BASELINE_HISTORY
    current = replace(observation(), ms_first_response=-50.0)

    features = build_disengagement_behavior_features(current, history)

    assert features["rt_deviation"] == pytest.approx(-log(1000.0))

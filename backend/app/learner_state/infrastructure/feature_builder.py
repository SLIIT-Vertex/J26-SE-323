from collections.abc import Sequence
from dataclasses import dataclass
from math import log1p
from typing import Final

HISTORY_WINDOW: Final = 20
MIN_BASELINE_HISTORY: Final = 5

# Training filled missing bottom_hint values with the train-split median
# (0.0) and kept `bottom_hint_missing` as a separate flag. Serving does the
# same so the models never receive a value pattern they were not trained on.
# Source: research/learner-state/notebooks (behaviour and disengagement).
BOTTOM_HINT_TRAIN_MEDIAN: Final = 0.0


@dataclass(frozen=True)
class BehaviorObservation:
    correct: float
    bottom_hint: float | None
    hint_count: float
    attempt_count: float
    ms_first_response: float
    overlap_time: float
    original: float


def _safe_log_response_time(value: float) -> float:
    return log1p(max(0.0, value))


def build_confusion_behavior_features(
    observation: BehaviorObservation,
) -> dict[str, float | None]:
    bottom_hint_missing = 1.0 if observation.bottom_hint is None else 0.0
    bottom_hint = (
        BOTTOM_HINT_TRAIN_MEDIAN
        if observation.bottom_hint is None
        else observation.bottom_hint
    )

    return {
        "correct": observation.correct,
        "bottom_hint": bottom_hint,
        "hint_count": observation.hint_count,
        "attempt_count": observation.attempt_count,
        "ms_first_response": observation.ms_first_response,
        "overlap_time": observation.overlap_time,
        "original": observation.original,
        "bottom_hint_missing": bottom_hint_missing,
    }


def build_disengagement_behavior_features(
    observation: BehaviorObservation,
    history: Sequence[BehaviorObservation],
) -> dict[str, float | None]:
    base_features = build_confusion_behavior_features(observation)

    recent_history = list(history[-HISTORY_WINDOW:])
    history_count = len(recent_history)

    history_confidence = min(
        history_count / HISTORY_WINDOW,
        1.0,
    )

    baseline_available = history_count >= MIN_BASELINE_HISTORY

    if not baseline_available:
        return {
            **base_features,
            "recent_log_rt": None,
            "recent_accuracy": None,
            "recent_attempts": None,
            "recent_hints": None,
            "rt_deviation": None,
            "attempt_deviation": None,
            "hint_deviation": None,
            "accuracy_deviation": None,
            "history_confidence": history_confidence,
            "baseline_available": 0.0,
        }

    recent_log_rt = sum(
        _safe_log_response_time(item.ms_first_response)
        for item in recent_history
    ) / history_count

    recent_accuracy = sum(
        item.correct
        for item in recent_history
    ) / history_count

    recent_attempts = sum(
        item.attempt_count
        for item in recent_history
    ) / history_count

    recent_hints = sum(
        item.hint_count
        for item in recent_history
    ) / history_count

    current_log_rt = _safe_log_response_time(
        observation.ms_first_response
    )

    return {
        **base_features,
        "recent_log_rt": recent_log_rt,
        "recent_accuracy": recent_accuracy,
        "recent_attempts": recent_attempts,
        "recent_hints": recent_hints,
        "rt_deviation": current_log_rt - recent_log_rt,
        "attempt_deviation": (
            observation.attempt_count - recent_attempts
        ),
        "hint_deviation": (
            observation.hint_count - recent_hints
        ),
        "accuracy_deviation": (
            observation.correct - recent_accuracy
        ),
        "history_confidence": history_confidence,
        "baseline_available": 1.0,
    }
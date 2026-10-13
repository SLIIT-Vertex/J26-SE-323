from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import xgboost as xgb

MODEL_DIRECTORY: Final = Path(__file__).resolve().parent / "models"


CONFUSION_BEHAVIOR_FEATURES: Final = (
    "correct",
    "bottom_hint",
    "hint_count",
    "attempt_count",
    "ms_first_response",
    "overlap_time",
    "first_action",
    "position",
    "original",
    "bottom_hint_missing",
)

VISUAL_FEATURES: Final = (
    "mean_eye_openness",
    "std_eye_openness",
    "mean_gaze_ratio",
    "std_gaze_ratio",
    "mean_pitch",
    "mean_yaw",
    "mean_roll",
    "mean_abs_pitch",
    "mean_abs_yaw",
    "mean_abs_roll",
    "face_visibility_ratio",
)

DISENGAGEMENT_BEHAVIOR_FEATURES: Final = (
    "correct",
    "bottom_hint",
    "hint_count",
    "attempt_count",
    "ms_first_response",
    "overlap_time",
    "first_action",
    "position",
    "original",
    "bottom_hint_missing",
    "recent_log_rt",
    "recent_accuracy",
    "recent_attempts",
    "recent_hints",
    "rt_deviation",
    "attempt_deviation",
    "hint_deviation",
    "accuracy_deviation",
    "history_confidence",
    "baseline_available",
)


def _load_model(
    filename: str,
    expected_features: tuple[str, ...],
) -> xgb.Booster:
    path = MODEL_DIRECTORY / filename

    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")

    model = xgb.Booster()
    model.load_model(path)

    actual_features = tuple(model.feature_names or ())

    if actual_features != expected_features:
        raise RuntimeError(
            f"Feature mismatch for {filename}. "
            f"Expected {expected_features}, got {actual_features}."
        )

    return model


def _predict_probability(
    model: xgb.Booster,
    features: dict[str, float | None],
    feature_order: tuple[str, ...],
) -> float:
    missing_features = [
        name
        for name in feature_order
        if name not in features
    ]

    if missing_features:
        raise ValueError(
            f"Missing required model features: {missing_features}"
        )

    values = [
        np.nan if features[name] is None else float(features[name])
        for name in feature_order
    ]

    matrix = xgb.DMatrix(
        np.asarray([values], dtype=np.float32),
        feature_names=list(feature_order),
        missing=np.nan,
    )

    probability = float(model.predict(matrix)[0])

    return max(0.0, min(1.0, probability))


@dataclass
class LearnerStateModels:
    confusion_behavior: xgb.Booster
    confusion_visual: xgb.Booster
    disengagement_behavior: xgb.Booster
    disengagement_visual: xgb.Booster

    @classmethod
    def load_default(cls) -> "LearnerStateModels":
        return cls(
            confusion_behavior=_load_model(
                "mindbridge_behavior_model.json",
                CONFUSION_BEHAVIOR_FEATURES,
            ),
            confusion_visual=_load_model(
                "mindbridge_visual_model.json",
                VISUAL_FEATURES,
            ),
            disengagement_behavior=_load_model(
                "mindbridge_disengagement_behavior_model_v2.json",
                DISENGAGEMENT_BEHAVIOR_FEATURES,
            ),
            disengagement_visual=_load_model(
                "mindbridge_disengagement_visual_model.json",
                VISUAL_FEATURES,
            ),
        )

    def predict_confusion_behavior(
        self,
        features: dict[str, float | None],
    ) -> float:
        return _predict_probability(
            self.confusion_behavior,
            features,
            CONFUSION_BEHAVIOR_FEATURES,
        )

    def predict_confusion_visual(
        self,
        features: dict[str, float | None],
    ) -> float:
        return _predict_probability(
            self.confusion_visual,
            features,
            VISUAL_FEATURES,
        )

    def predict_disengagement_behavior(
        self,
        features: dict[str, float | None],
    ) -> float:
        return _predict_probability(
            self.disengagement_behavior,
            features,
            DISENGAGEMENT_BEHAVIOR_FEATURES,
        )

    def predict_disengagement_visual(
        self,
        features: dict[str, float | None],
    ) -> float:
        return _predict_probability(
            self.disengagement_visual,
            features,
            VISUAL_FEATURES,
        )
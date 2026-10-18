import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

MODEL_DIRECTORY: Final = Path(__file__).resolve().parent / "models"


_FLOAT32_MAX: Final = 3.4028234663852886e38


def _float32(value: float) -> float:
    """Round to the nearest float32, as XGBoost does with inputs and split thresholds."""
    if abs(value) > _FLOAT32_MAX:
        # Too large for float32: XGBoost turns it into infinity; struct would raise instead.
        return math.copysign(math.inf, value)
    return struct.unpack("f", struct.pack("f", value))[0]


# The behaviour models were retrained without the ASSISTments-only fields `position` and
# `first_action`, which MindBridge cannot produce truthfully (ablation in
# research/learner-state/notebooks/kaggle_behaviour_ablation_cells.py).
CONFUSION_BEHAVIOR_FEATURES: Final = (
    "correct",
    "bottom_hint",
    "hint_count",
    "attempt_count",
    "ms_first_response",
    "overlap_time",
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


@dataclass(frozen=True)
class _Tree:
    left_children: tuple[int, ...]
    right_children: tuple[int, ...]
    split_indices: tuple[int, ...]
    split_conditions: tuple[float, ...]
    default_left: tuple[bool, ...]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "_Tree":
        tree = cls(
            left_children=tuple(data["left_children"]),
            right_children=tuple(data["right_children"]),
            split_indices=tuple(data["split_indices"]),
            # XGBoost compares in float32; the JSON stores thresholds as decimal text.
            split_conditions=tuple(_float32(value) for value in data["split_conditions"]),
            default_left=tuple(bool(value) for value in data["default_left"]),
        )
        node_count = len(tree.left_children)
        if not node_count or any(
            len(values) != node_count
            for values in (
                tree.right_children,
                tree.split_indices,
                tree.split_conditions,
                tree.default_left,
            )
        ):
            raise RuntimeError("Invalid tree arrays in learner-state model")
        return tree

    def predict_margin(self, values: tuple[float, ...]) -> float:
        node = 0
        while self.left_children[node] != -1:
            feature_value = values[self.split_indices[node]]
            go_left = (
                self.default_left[node]
                if math.isnan(feature_value)
                else feature_value < self.split_conditions[node]
            )
            node = self.left_children[node] if go_left else self.right_children[node]
        return self.split_conditions[node]


@dataclass(frozen=True)
class _JsonTreeModel:
    feature_names: tuple[str, ...]
    base_margin: float
    trees: tuple[_Tree, ...]

    def predict_probability(self, values: tuple[float, ...]) -> float:
        # XGBoost converts every input to float32 before comparing it with a threshold.
        # Comparing in float64 instead sends values that lie on or next to a threshold
        # (for example history_confidence = k / 20) down the wrong branch.
        values = tuple(value if math.isnan(value) else _float32(value) for value in values)
        margin = self.base_margin + sum(tree.predict_margin(values) for tree in self.trees)
        if margin >= 0:
            return 1.0 / (1.0 + math.exp(-margin))
        exp_margin = math.exp(margin)
        return exp_margin / (1.0 + exp_margin)


def _load_model(
    filename: str,
    expected_features: tuple[str, ...],
) -> _JsonTreeModel:
    path = MODEL_DIRECTORY / filename

    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")

    try:
        learner = json.loads(path.read_text(encoding="utf-8"))["learner"]
        actual_features = tuple(learner["feature_names"])
        booster = learner["gradient_booster"]
        objective = learner["objective"]["name"]
        base_score_text = learner["learner_model_param"]["base_score"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid learner-state model file: {filename}") from error

    if actual_features != expected_features:
        raise RuntimeError(
            f"Feature mismatch for {filename}. "
            f"Expected {expected_features}, got {actual_features}."
        )

    if booster.get("name") != "gbtree" or objective != "binary:logistic":
        raise RuntimeError(
            f"Unsupported learner-state model format in {filename}: "
            f"booster={booster.get('name')!r}, objective={objective!r}"
        )

    try:
        base_probability = float(base_score_text.strip("[]"))
        if not 0.0 < base_probability < 1.0:
            raise ValueError
        base_margin = math.log(base_probability / (1.0 - base_probability))
        trees = tuple(
            _Tree.from_json(tree)
            for tree in booster["model"]["trees"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Invalid learner-state model data: {filename}") from error

    return _JsonTreeModel(
        feature_names=actual_features,
        base_margin=base_margin,
        trees=trees,
    )


def _predict_probability(
    model: _JsonTreeModel,
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

    values = tuple(
        math.nan if features[name] is None else float(features[name])
        for name in feature_order
    )

    probability = model.predict_probability(values)

    return max(0.0, min(1.0, probability))


@dataclass
class LearnerStateModels:
    confusion_behavior: _JsonTreeModel
    confusion_visual: _JsonTreeModel
    disengagement_behavior: _JsonTreeModel
    disengagement_visual: _JsonTreeModel

    @classmethod
    def load_default(cls) -> "LearnerStateModels":
        return cls(
            confusion_behavior=_load_model(
                "mindbridge_behavior_model_v2.json",
                CONFUSION_BEHAVIOR_FEATURES,
            ),
            confusion_visual=_load_model(
                "mindbridge_visual_model.json",
                VISUAL_FEATURES,
            ),
            disengagement_behavior=_load_model(
                "mindbridge_disengagement_behavior_model_v3.json",
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

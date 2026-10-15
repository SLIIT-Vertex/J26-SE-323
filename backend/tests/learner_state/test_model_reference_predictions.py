import json
import math
from pathlib import Path

import pytest

from app.learner_state.infrastructure.model_loader import (
    CONFUSION_BEHAVIOR_FEATURES,
    DISENGAGEMENT_BEHAVIOR_FEATURES,
    VISUAL_FEATURES,
    _float32,
    _load_model,
)

# Reference predictions made by real XGBoost on the committed model files
# (research/learner-state/tools/generate_model_reference_predictions.py). They include inputs
# exactly on and next to the models' split thresholds and realistic learner sessions.
FIXTURE = Path(__file__).parent / "fixtures" / "model_reference_predictions.json"
REFERENCE = json.loads(FIXTURE.read_text(encoding="utf-8"))

EXPECTED_FEATURES = {
    "mindbridge_behavior_model.json": CONFUSION_BEHAVIOR_FEATURES,
    "mindbridge_visual_model.json": VISUAL_FEATURES,
    "mindbridge_disengagement_behavior_model_v2.json": DISENGAGEMENT_BEHAVIOR_FEATURES,
    "mindbridge_disengagement_visual_model.json": VISUAL_FEATURES,
}

# XGBoost sums leaf values in float32; the evaluator sums in float64.
TOLERANCE = 1e-6


@pytest.mark.parametrize("filename", sorted(EXPECTED_FEATURES))
@pytest.mark.parametrize("kind", ["boundary", "realistic"])
def test_evaluator_matches_xgboost(filename: str, kind: str) -> None:
    reference = REFERENCE["models"][filename]
    assert tuple(reference["features"]) == EXPECTED_FEATURES[filename]
    model = _load_model(filename, EXPECTED_FEATURES[filename])

    cases = [case for case in reference["cases"] if case["kind"] == kind]
    assert cases
    mismatches = []
    for case in cases:
        values = tuple(math.nan if v is None else v for v in case["values"])
        predicted = model.predict_probability(values)
        if abs(predicted - case["probability"]) > TOLERANCE:
            mismatches.append((case["values"], case["probability"], predicted))

    assert not mismatches, f"{len(mismatches)}/{len(cases)} differ, first: {mismatches[0]}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.15, 0.15000000596046448),
        (1.0, 1.0),
        (-2.5, -2.5),
        (1e40, math.inf),
        (-1e40, -math.inf),
        (math.inf, math.inf),
    ],
)
def test_float32_rounding_matches_xgboost_input_conversion(value: float, expected: float) -> None:
    assert _float32(value) == expected


def test_extreme_inputs_do_not_crash_prediction() -> None:
    model = _load_model("mindbridge_behavior_model.json", CONFUSION_BEHAVIOR_FEATURES)
    probability = model.predict_probability((1e40,) * len(CONFUSION_BEHAVIOR_FEATURES))
    assert 0.0 <= probability <= 1.0

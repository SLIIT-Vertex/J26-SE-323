import pytest

from app.gamification.modeling.misconception_inference import (
    UNKNOWN_CODE,
    DeterministicMisconceptionBaseline,
)
from app.gamification.modeling.shared import FeatureBuilder
from tests.gamification.modeling.fixtures import feature_input, misconception_model


def test_misconception_models_normalize_and_abstain() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    prediction = misconception_model().predict(snapshot)
    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.confidence > 0.6
    assert not prediction.abstained
    missing = misconception_model().predict(
        FeatureBuilder().build(feature_input(structured_error_code=None))
    )
    assert missing.abstained
    assert missing.entropy > 0
    baseline = DeterministicMisconceptionBaseline({"error-a": "m-a"})
    assert baseline.predict(snapshot, catalogue_version="v1").probabilities == {"m-a": 1.0}
    unknown = baseline.predict(
        FeatureBuilder().build(feature_input(structured_error_code=None)),
        catalogue_version="v1",
    )
    assert unknown.abstained and UNKNOWN_CODE in unknown.probabilities

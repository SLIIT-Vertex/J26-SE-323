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


def test_log_linear_candidate_rejects_a_different_catalogue_and_reloads_from_an_artifact() -> None:
    from app.gamification.modeling.offline import DatasetManifest, DatasetRow
    from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle

    model = misconception_model()
    mismatch = model.predict(
        FeatureBuilder().build(feature_input(misconception_catalogue_version="other-catalogue"))
    )
    assert mismatch.abstained
    assert mismatch.probabilities == {UNKNOWN_CODE: 1.0}
    assert "CATALOGUE_VERSION_MISMATCH" in mismatch.reason_codes

    manifest = DatasetManifest.build(
        [DatasetRow("episode", "learner", {}, "action", None, None, False)],
        dataset_id="synthetic-log-linear",
        split_seed=1,
        synthetic=True,
    )
    artifact = ModelArtifactBundle.create(
        model_name="misconception-log-linear",
        model_version="probabilistic-authored-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v1",
        manifest=manifest,
        seed=1,
        parameters=model.to_parameters(),
    )
    snapshot = FeatureBuilder().build(feature_input())
    restored = type(model).from_artifact(artifact)
    assert restored.predict(snapshot) == model.predict(snapshot)

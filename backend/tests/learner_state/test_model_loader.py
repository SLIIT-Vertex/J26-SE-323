import pytest

from app.learner_state.infrastructure.model_loader import (
    CONFUSION_BEHAVIOR_FEATURES,
    DISENGAGEMENT_BEHAVIOR_FEATURES,
    VISUAL_FEATURES,
    LearnerStateModels,
)


def _numbered_features(names: tuple[str, ...]) -> dict[str, float]:
    return {name: float(index) for index, name in enumerate(names, start=1)}


def test_committed_json_models_preserve_trained_xgboost_predictions() -> None:
    models = LearnerStateModels.load_default()
    behavior = _numbered_features(CONFUSION_BEHAVIOR_FEATURES)
    disengagement_behavior = _numbered_features(DISENGAGEMENT_BEHAVIOR_FEATURES)
    visual = _numbered_features(VISUAL_FEATURES)

    # Reference values were produced by XGBoost (3.4.1 for the visual models, 3.2.0 for the
    # behaviour models retrained without `position` and `first_action`) before switching the
    # runtime reader to the portable JSON-tree evaluator.
    assert models.predict_confusion_behavior(behavior) == pytest.approx(0.02733618, rel=1e-5)
    assert models.predict_confusion_visual(visual) == pytest.approx(0.8224369, rel=1e-5)
    assert models.predict_disengagement_behavior(disengagement_behavior) == pytest.approx(
        0.20429580, rel=1e-5
    )
    assert models.predict_disengagement_visual(visual) == pytest.approx(0.22835349, rel=1e-5)


def test_model_prediction_requires_every_named_feature() -> None:
    models = LearnerStateModels.load_default()
    incomplete = _numbered_features(CONFUSION_BEHAVIOR_FEATURES)
    del incomplete["correct"]

    with pytest.raises(ValueError, match="correct"):
        models.predict_confusion_behavior(incomplete)

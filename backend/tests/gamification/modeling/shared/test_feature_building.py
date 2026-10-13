from datetime import timedelta

import pytest

from app.gamification.modeling.shared import FeatureBuilder
from tests.gamification.modeling.fixtures import NOW, feature_input


def test_feature_snapshot_is_deterministic_and_has_missingness() -> None:
    builder = FeatureBuilder()
    first = builder.build(feature_input(response_time_ms=None))
    second = builder.build(feature_input(response_time_ms=None))
    assert first == second
    assert first.missingness["response_time_ms"] is True
    assert first.values["recent_accuracy"] == 0.5


@pytest.mark.parametrize("source", ["verification_score", "outcome", "support-exposure"])
def test_feature_builder_rejects_post_decision_sources(source: str) -> None:
    with pytest.raises(ValueError, match="post-decision"):
        FeatureBuilder().build(feature_input(source_as_of={source: NOW}))


def test_feature_builder_rejects_future_timestamp() -> None:
    with pytest.raises(ValueError, match="future evidence"):
        FeatureBuilder().build(
            feature_input(source_as_of={"mastery": NOW + timedelta(seconds=1)})
        )

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
        FeatureBuilder().build(feature_input(source_as_of={"mastery": NOW + timedelta(seconds=1)}))


def test_feature_builder_records_model_one_inputs_and_their_missingness() -> None:
    snapshot = FeatureBuilder().build(
        feature_input(
            response_time_ms=2_000,
            item_expected_time_ms=1_000,
            selected_option_id="option-a",
            distractor_misconception_code="m-a",
            prior_skill_accuracy=0.25,
            previous_scaffold_types={"visual_guidance": 2},
            previous_independence_gains=(0.0, 1.0),
            support_dependency_index=0.5,
            item_difficulty=2,
            template_key="choice_quest",
            prior_belief_age_ms=0,
        )
    )

    assert snapshot.feature_definition_version == "gamification-features-v2"
    assert snapshot.values["response_time_ratio"] == 2
    assert snapshot.values["previous_scaffold_count:visual_guidance"] == 2
    assert snapshot.values["previous_ig_count"] == 2
    assert snapshot.values["previous_ig_mean"] == 0.5
    assert snapshot.missingness["selected_option_id"] is False
    assert snapshot.missingness["template_key"] is False
    bare = FeatureBuilder().build(feature_input())
    for field in (
        "selected_option_id",
        "distractor_misconception_code",
        "response_time_ratio",
        "prior_skill_accuracy",
        "support_dependency_index",
        "item_difficulty",
        "template_key",
        "previous_scaffold_types",
        "previous_independence_gains",
    ):
        assert bare.missingness[field] is True


def test_current_episode_outcome_cannot_enter_as_a_feature_source() -> None:
    with pytest.raises(ValueError, match="post-decision"):
        FeatureBuilder().build(feature_input(source_as_of={"previous_independence_gains": NOW}))

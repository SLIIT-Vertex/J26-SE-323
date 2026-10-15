from datetime import timedelta
from uuid import uuid4

from app.gamification.application.records import SupportExposureEvidence
from app.gamification.domain.types import ActionId, CatalogueVersion
from app.gamification.modeling.independence_gain import RawIndependenceGainCalculator
from app.gamification.modeling.orchestration import ThreeModelPipeline
from app.gamification.modeling.shared import FeatureBuilder
from app.gamification.modeling.support_selection import SafeSupportPolicy
from tests.gamification.modeling.fixtures import (
    EPISODE,
    NOW,
    feature_input,
    gain_input,
    misconception_model,
    support_candidates,
)


def test_seeded_end_to_end_feature_inference_decision_and_outcome() -> None:
    pipeline = ThreeModelPipeline(
        feature_builder=FeatureBuilder(),
        misconception_predictor=misconception_model(),
        support_selector=SafeSupportPolicy(
            catalogue_version=CatalogueVersion("support-v1")
        ),
        independence_gain_calculator=RawIndependenceGainCalculator(),
    )
    decision = pipeline.decide(
        episode_id=EPISODE,
        features=feature_input(),
        candidates=support_candidates(),
        language="si",
        seed=42,
        decided_at=NOW,
    )
    completed = pipeline.complete(
        decision=decision,
        support_exposure=SupportExposureEvidence(
            exposure_id=uuid4(),
            action_id=ActionId("a-hint"),
            delivery_status="completed",
            presented_at=NOW,
            completed_at=NOW + timedelta(seconds=10),
            duration_ms=10_000,
            render_version="synthetic-render-v1",
        ),
        verification=gain_input(),
    )
    assert decision.feature_snapshot.values["current_score"] == 0.25
    assert decision.misconception.probabilities["m-a"] > 0.9
    assert decision.policy.selected_action_id == "a-hint"
    assert completed.support_exposure.delivery_status == "completed"
    assert completed.independence_outcome.raw_gain == 0.5

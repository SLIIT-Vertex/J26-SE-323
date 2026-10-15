from app.gamification.domain.types import CatalogueVersion, DecisionMode
from app.gamification.modeling.shared import FeatureBuilder
from app.gamification.modeling.support_selection import SafeSupportPolicy
from tests.gamification.modeling.fixtures import (
    EPISODE,
    NOW,
    feature_input,
    misconception_model,
    support_candidates,
)


class Scorer:
    version = "learned-candidate-v1"

    def score(self, snapshot, belief, available):
        return {
            candidate.action_id: (0.8, 0.1) if candidate.action_id == "b-worked" else (0.2, 0.2)
            for candidate in available
        }


def test_policy_logs_all_candidates_propensities_and_seed() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = misconception_model().predict(snapshot)
    policy = SafeSupportPolicy(catalogue_version=CatalogueVersion("support-v1"))
    first = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=7,
        decided_at=NOW,
    )
    second = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=7,
        decided_at=NOW,
    )
    assert first == second
    assert len(first.candidates) == 3
    assert sum(item.propensity for item in first.candidates if item.eligible) == 1
    assert all(item.propensity == 0 for item in first.candidates if not item.eligible)
    assert first.random_seed == 7


def test_policy_shadow_and_cold_start_do_not_control_delivery() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = misconception_model().predict(snapshot)
    policy = SafeSupportPolicy(
        catalogue_version=CatalogueVersion("support-v1"), minimum_learned_evidence=10
    )
    shadow = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=9,
        decided_at=NOW,
        mode=DecisionMode.SHADOW,
        learned_policy=Scorer(),
        evidence_count=100,
    )
    fallback = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=9,
        decided_at=NOW,
        mode=DecisionMode.LEARNED,
        learned_policy=Scorer(),
        evidence_count=0,
    )
    assert shadow.selected_action_id == "a-hint"
    assert shadow.mode is DecisionMode.SHADOW
    assert any(item.predicted_reward is not None for item in shadow.candidates)
    assert fallback.mode is DecisionMode.CONSERVATIVE_FALLBACK
    assert fallback.selected_action_id == "a-hint"


def test_learned_policy_without_an_approved_artifact_falls_back() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    decision = SafeSupportPolicy(catalogue_version=CatalogueVersion("support-v1")).decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=misconception_model().predict(snapshot),
        candidates=support_candidates(),
        language="si",
        seed=11,
        decided_at=NOW,
        mode=DecisionMode.LEARNED,
        learned_policy=Scorer(),
        evidence_count=100,
    )
    assert decision.mode is DecisionMode.CONSERVATIVE_FALLBACK
    assert decision.selected_action_id == "a-hint"
    assert decision.random_seed == 11

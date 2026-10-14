from datetime import UTC, datetime

import pytest

from app.gamification.domain.types import (
    ActionId,
    CatalogueVersion,
    DecisionMode,
    OutcomeValidity,
    SupportActionType,
)
from app.gamification.modeling.independence_gain.contracts import IndependenceGainResult
from app.gamification.modeling.shared import FeatureBuilder
from app.gamification.modeling.shared.artifact_registry import ApprovalGatedArtifactRegistry
from app.gamification.modeling.shared.contracts import MisconceptionDistribution
from app.gamification.modeling.support_selection.context import (
    CONTEXT_VERSION,
    BanditContextBuilder,
    QuestionContext,
    SupportHistory,
    policy_context_snapshot,
)
from app.gamification.modeling.support_selection.eligibility import (
    evaluate_candidate_eligibility,
)
from app.gamification.modeling.support_selection.evaluation import evaluate_logged_policy
from app.gamification.modeling.support_selection.learned_policy import (
    LinUCBPolicy,
    ThompsonSamplingPolicy,
)
from app.gamification.modeling.support_selection.offline_update import (
    LoggedBanditDecision,
    fit_from_logged_decisions,
)
from app.gamification.modeling.support_selection.reference_policy import SafeSupportPolicy
from app.gamification.modeling.support_selection.reference_table import (
    ReferencePolicyRow,
    ReferencePolicyTable,
)
from app.gamification.modeling.support_selection.reward import IndependenceGainReward
from app.gamification.modeling.synthetic.bandit_environment import run_bandit_simulation
from tests.gamification.modeling.fixtures import (
    EPISODE,
    NOW,
    feature_input,
    misconception_model,
    support_candidates,
)

_CODES = ("m-a", "m-b")
_SKILLS = ("opaque-skill-1",)


def _belief(**probabilities: float) -> MisconceptionDistribution:
    return MisconceptionDistribution(
        probabilities=probabilities,
        entropy=0.5,
        confidence=max(probabilities.values()),
        abstained=False,
        model_version="test",
        catalogue_version="test",
        reason_codes=(),
    )


def _context(snapshot, belief, *, history: SupportHistory | None = None):
    builder = BanditContextBuilder(catalogue_codes=_CODES, skill_ids=_SKILLS)
    return builder.build(
        snapshot,
        belief,
        QuestionContext("opaque-skill-1", 2, "single_choice", "choice_quest"),
        history or SupportHistory(),
    )


def _table(*rows: tuple[str, str, str]) -> ReferencePolicyTable:
    return ReferencePolicyTable(
        version="authored-reference-policy-v1",
        rows=tuple(
            ReferencePolicyRow(
                skill, code, scaffold, "lowest_assistance_among_scaffolds_targeting_code"
            )
            for skill, code, scaffold in rows
        ),
    )


def test_context_vector_order_and_version_are_stable() -> None:
    snapshot = FeatureBuilder().build(feature_input(recent_correctness=(False, True)))
    belief = _belief(**{"m-a": 0.7, "m-b": 0.3})
    builder = BanditContextBuilder(catalogue_codes=_CODES, skill_ids=_SKILLS)
    first = builder.build(
        snapshot,
        belief,
        QuestionContext("opaque-skill-1", 2, "single_choice", "choice_quest"),
        SupportHistory(mean_valid_ig={"conceptual_hint": 0.4}, counts={"conceptual_hint": 2}),
    )
    second = builder.build(
        snapshot,
        belief,
        QuestionContext("opaque-skill-1", 2, "single_choice", "choice_quest"),
        SupportHistory(mean_valid_ig={"conceptual_hint": 0.4}, counts={"conceptual_hint": 2}),
    )

    assert first == second
    assert first.version == CONTEXT_VERSION
    assert first.names == builder.feature_names
    assert first.names.index("belief:m-a") < first.names.index("belief:m-b")
    assert first.values[first.names.index("belief:m-a")] == pytest.approx(0.7)
    assert first.values[first.names.index("recent_accuracy")] == pytest.approx(0.5)
    assert first.values[first.names.index("conceptual_hint_ig_mean")] == pytest.approx(0.4)
    assert "mastery_missing" in first.missingness and first.missingness["mastery_missing"] is True


def test_context_marks_a_missing_learner_block() -> None:
    snapshot = FeatureBuilder().build(
        feature_input(recent_correctness=(), mastery_probability=None, source_as_of={})
    )
    belief = _belief(**{"m-a": 1.0})
    context = _context(snapshot, belief)
    names = context.names

    assert context.values[names.index("missing_learner_block")] == 1.0
    assert context.values[names.index("recent_accuracy_missing")] == 1.0
    assert context.values[names.index("mastery_missing")] == 1.0
    assert context.values[names.index("support_need_uncertain")] == 1.0
    stored = policy_context_snapshot(snapshot, context)
    assert stored.purpose == "policy_context"
    assert stored.values["bandit_context_version"] == CONTEXT_VERSION


def test_eligibility_floor_matches_any_targeted_code_above_the_floor() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = _belief(**{"m-a": 0.8, "m-b": 0.2})
    low = support_candidates()[1]
    secondary = type(low)(
        ActionId("c-steps"),
        SupportActionType.GUIDED_STEPS,
        ("si",),
        ("opaque-skill-1",),
        ("m-b",),
        True,
    )
    below = type(low)(
        ActionId("d-visual"),
        SupportActionType.VISUAL_GUIDANCE,
        ("si",),
        ("opaque-skill-1",),
        ("m-b",),
        True,
    )
    results = {
        item.candidate.action_id: item
        for item in evaluate_candidate_eligibility(
            snapshot=snapshot,
            belief=belief,
            candidates=(low, secondary, below),
            language="si",
            probability_floor=0.15,
        )
    }

    assert results["b-worked"].eligible
    assert results["b-worked"].matched_codes == ("m-a",)
    assert results["c-steps"].eligible
    assert results["c-steps"].matched_codes == ("m-b",)
    quiet = evaluate_candidate_eligibility(
        snapshot=snapshot,
        belief=_belief(**{"m-a": 0.99, "m-b": 0.01}),
        candidates=(below,),
        language="si",
        probability_floor=0.15,
    )[0]
    assert not quiet.eligible
    assert "MISCONCEPTION_NOT_SUPPORTED" in quiet.reason_codes


def test_reference_table_overrides_alphabetical_order_and_falls_back_on_a_miss() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = misconception_model().predict(snapshot)
    table = _table(("opaque-skill-1", "m-a", "similar_worked_example"))
    policy = SafeSupportPolicy(
        catalogue_version=CatalogueVersion("support-v1"), reference_table=table
    )
    chosen = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=3,
        decided_at=NOW,
        mode=DecisionMode.PERFORMANCE_TRIGGERED_FIXED,
    )
    missing = SafeSupportPolicy(catalogue_version=CatalogueVersion("support-v1")).decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=3,
        decided_at=NOW,
    )

    assert chosen.selected_action_id == "b-worked"
    assert chosen.mode is DecisionMode.PERFORMANCE_TRIGGERED_FIXED
    assert "AUTHORED_REFERENCE_TABLE" in chosen.reason_codes
    assert missing.selected_action_id == "a-hint"
    assert "REFERENCE_TABLE_MISS" in missing.reason_codes
    assert "DETERMINISTIC_REFERENCE_ALIAS" in missing.reason_codes


def test_exploration_floor_propensities_sum_to_one_and_are_reproducible() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = misconception_model().predict(snapshot)
    context = _context(snapshot, belief)
    linucb = LinUCBPolicy(epsilon_min=0.05)
    thompson = ThompsonSamplingPolicy(epsilon_min=0.05, monte_carlo_samples=40)
    arms = ("conceptual_hint", "similar_worked_example")
    first_linucb = linucb.sample_action(context, arms, seed=11)
    second_linucb = linucb.sample_action(context, arms, seed=11)
    first_thompson = thompson.sample_action(context, arms, seed=11)
    second_thompson = thompson.sample_action(context, arms, seed=11)

    for _arm, propensities in (first_linucb, first_thompson):
        assert sum(propensities.values()) == pytest.approx(1.0)
        assert min(propensities.values()) >= 0.05
    assert first_linucb == second_linucb
    assert first_thompson == second_thompson
    assert "THOMPSON_MC_SAMPLES:40" not in first_thompson[0]


def test_update_moves_predicted_reward_toward_the_observed_reward() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    context = _context(snapshot, _belief(**{"m-a": 1.0}))
    policy = LinUCBPolicy()
    before = policy.predict(context, ("conceptual_hint",))["conceptual_hint"][0]
    for _ in range(6):
        policy.update(context, "conceptual_hint", 0.8)
    after = policy.predict(context, ("conceptual_hint",))["conceptual_hint"][0]
    restored = LinUCBPolicy.from_parameters(policy.parameters())

    assert before < after
    assert after == pytest.approx(0.8, abs=0.25)
    assert restored.predict(context, ("conceptual_hint",))["conceptual_hint"][0] == pytest.approx(
        after
    )


def test_reward_accepts_only_a_valid_independence_gain() -> None:
    reward = IndependenceGainReward()
    valid = IndependenceGainResult(OutcomeValidity.VALID, 0.5, "raw-independence-gain-v1", ())
    invalid = IndependenceGainResult(
        OutcomeValidity.INVALID, None, "raw-independence-gain-v1", ("PAIR_NOT_APPROVED",)
    )

    assert reward.version == "raw-ig-reward-v1"
    assert reward(valid) == 0.5
    with pytest.raises(ValueError, match="valid independence gain"):
        reward(invalid)


def test_shadow_keeps_the_reference_action_and_logs_bandit_propensities() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = misconception_model().predict(snapshot)
    context = _context(snapshot, belief)
    table = _table(("opaque-skill-1", "m-a", "conceptual_hint"))
    policy = SafeSupportPolicy(
        catalogue_version=CatalogueVersion("support-v1"), reference_table=table
    )
    reference = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=5,
        decided_at=NOW,
        context=context,
    )
    shadow = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=5,
        decided_at=NOW,
        mode=DecisionMode.SHADOW,
        context=context,
        bandit=LinUCBPolicy(epsilon_min=0.05),
        artifact_approved=False,
    )
    eligible = [item for item in shadow.candidates if item.eligible]

    assert shadow.selected_action_id == reference.selected_action_id == "a-hint"
    assert shadow.mode is DecisionMode.SHADOW
    assert sum(item.propensity for item in eligible) == pytest.approx(1.0)
    assert min(item.propensity for item in eligible) >= 0.05
    assert all(item.predicted_reward is not None for item in eligible)
    assert any(code.startswith("BANDIT_WOULD_SELECT:") for code in shadow.reason_codes)


def test_learned_mode_samples_only_an_approved_artifact() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = misconception_model().predict(snapshot)
    context = _context(snapshot, belief)
    bandit = LinUCBPolicy(epsilon_min=0.05)
    for _ in range(4):
        bandit.update(context, "similar_worked_example", 0.9)
        bandit.update(context, "conceptual_hint", -0.2)
    policy = SafeSupportPolicy(catalogue_version=CatalogueVersion("support-v1"))
    blocked = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=4,
        decided_at=NOW,
        mode=DecisionMode.LEARNED,
        evidence_count=100,
        context=context,
        bandit=bandit,
        artifact_approved=False,
    )
    allowed = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=4,
        decided_at=NOW,
        mode=DecisionMode.LEARNED,
        evidence_count=100,
        context=context,
        bandit=bandit,
        artifact_approved=True,
    )
    again = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=support_candidates(),
        language="si",
        seed=4,
        decided_at=NOW,
        mode=DecisionMode.LEARNED,
        evidence_count=100,
        context=context,
        bandit=LinUCBPolicy.from_parameters(bandit.parameters()),
        artifact_approved=True,
    )

    assert blocked.mode is DecisionMode.CONSERVATIVE_FALLBACK
    assert allowed.mode is DecisionMode.LEARNED
    assert allowed.selected_action_id == again.selected_action_id
    assert allowed.policy_version == "linucb-disjoint-v1"
    assert sum(item.propensity for item in allowed.candidates if item.eligible) == pytest.approx(1)


def test_unapproved_artifact_cannot_be_activated_for_child_facing_use() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    context = _context(snapshot, _belief(**{"m-a": 1.0}))
    bandit = LinUCBPolicy()
    bandit.update(context, "conceptual_hint", 0.2)
    manifest = type("Manifest", (), {"digest": "a" * 64, "synthetic": True})()
    artifact = fit_from_logged_decisions(
        decisions=[
            LoggedBanditDecision("learner-a", NOW, context, "conceptual_hint", 0.5),
        ],
        outcomes=[
            IndependenceGainResult(OutcomeValidity.VALID, 0.2, "raw-independence-gain-v1", ())
        ],
        policy=LinUCBPolicy(),
        reward=IndependenceGainReward(),
        train_learner_ids=("learner-a",),
        manifest=manifest,
        seed=1,
        source_commit="abc",
    )
    registry = ApprovalGatedArtifactRegistry()
    registry.register(artifact)
    with pytest.raises(PermissionError):
        registry.activate(
            model_name=artifact.model_name,
            artifact_sha256=artifact.artifact_sha256,
            approved=False,
        )
    assert registry.active(artifact.model_name) is None
    assert artifact.parameters["model_role"] == "support_policy"


def test_offline_replay_ignores_held_out_learners_and_invalid_rewards() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    context = _context(snapshot, _belief(**{"m-a": 1.0}))
    later = datetime(2026, 10, 13, 11, tzinfo=UTC)
    decisions = [
        LoggedBanditDecision("held-out", NOW, context, "conceptual_hint", 0.5),
        LoggedBanditDecision("train", later, context, "conceptual_hint", 0.5),
    ]
    outcomes = [
        IndependenceGainResult(OutcomeValidity.VALID, 1.0, "raw-independence-gain-v1", ()),
        IndependenceGainResult(
            OutcomeValidity.INVALID, None, "raw-independence-gain-v1", ("INVALID",)
        ),
    ]
    policy = LinUCBPolicy()
    manifest = type("Manifest", (), {"digest": "b" * 64, "synthetic": True})()
    artifact = fit_from_logged_decisions(
        decisions,
        outcomes,
        policy,
        reward=IndependenceGainReward(),
        train_learner_ids=("train",),
        manifest=manifest,
        seed=2,
        source_commit="abc",
    )

    assert policy.predict(context, ("conceptual_hint",))["conceptual_hint"][0] == pytest.approx(0.0)
    assert "model_card" in artifact.parameters
    artifact.verify()


def test_off_policy_evaluation_uses_supplied_reward_estimates_and_refuses_degenerate_logs() -> None:
    rows = [
        type(
            "Row",
            (),
            {
                "episode_id": "e1",
                "action_id": "visual",
                "reward": 0.4,
                "propensity": 0.8,
                "valid_outcome": True,
            },
        )()
    ]
    estimates = {("e1", "visual"): 0.5, ("e1", "steps"): 0.1}
    targets = {("e1", "visual"): 0.25, ("e1", "steps"): 0.75}
    report = evaluate_logged_policy(rows, targets, estimates)

    assert report.direct_method == pytest.approx(0.25 * 0.5 + 0.75 * 0.1)
    assert report.doubly_robust is not None
    untouched = evaluate_logged_policy(rows, targets)
    assert untouched.direct_method is None
    assert untouched.doubly_robust is None
    with pytest.raises(ValueError, match="degenerate"):
        evaluate_logged_policy(
            [
                type(
                    "Row",
                    (),
                    {
                        "episode_id": "e1",
                        "action_id": "visual",
                        "reward": 0.4,
                        "propensity": 1.0,
                        "valid_outcome": True,
                    },
                )()
            ],
            targets,
        )


def test_synthetic_bandits_regret_the_fixed_and_ablated_policies() -> None:
    report = run_bandit_simulation()
    regret = report["mean_cumulative_regret"]
    assert isinstance(regret, dict)
    assert regret["LinUCB"] < regret["random_eligible"]
    assert regret["LinUCB"] < regret["performance_triggered_fixed"]
    assert regret["ThompsonSampling"] < regret["random_eligible"]
    assert regret["ThompsonSampling"] < regret["performance_triggered_fixed"]
    assert regret["LinUCB"] < regret["LinUCB_belief_ablated"]
    assert report["synthetic"] is True

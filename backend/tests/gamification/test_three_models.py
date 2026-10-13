from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.gamification.application.records import SupportExposureEvidence
from app.gamification.domain.types import (
    ActionId,
    CatalogueVersion,
    DecisionMode,
    EpisodeId,
    EvidenceSupportState,
    ProtocolVersion,
    SkillId,
    SupportActionType,
    TaxonomyVersion,
)
from app.gamification.modeling.features import DecisionFeatureInput, FeatureBuilder
from app.gamification.modeling.independence import (
    EquivalenceEvidence,
    IndependenceGainInput,
    calculate_independence_gain,
)
from app.gamification.modeling.misconception import (
    UNKNOWN_CODE,
    DeterministicMisconceptionBaseline,
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.offline import (
    ApprovalGatedArtifactRegistry,
    DatasetManifest,
    DatasetRow,
    ModelArtifactBundle,
    evaluate_classification,
    evaluate_logged_policy,
    load_default_prototype_rows,
    load_fake_expert_reviews,
    train_frequency_candidate,
)
from app.gamification.modeling.policy import SafeSupportPolicy, SupportCandidate
from app.gamification.modeling.pipeline import ThreeModelPipeline
from app.gamification.modeling.synthetic import generate_synthetic_episodes

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)
LEARNER = UUID("10000000-0000-4000-8000-000000000001")
EPISODE = EpisodeId(UUID("10000000-0000-4000-8000-000000000002"))


def feature_input(**changes) -> DecisionFeatureInput:
    base = DecisionFeatureInput(
        learner_id=LEARNER,
        skill_id=SkillId("opaque-skill-1"),
        captured_at=NOW,
        protocol_version=ProtocolVersion("adaptive-episode-v1"),
        skill_taxonomy_version=TaxonomyVersion("provisional-v1"),
        misconception_catalogue_version="provisional-misconceptions-v1",
        support_catalogue_version="provisional-support-v1",
        current_score=0.25,
        recent_correctness=(False, True),
        attempt_count=2,
        structured_error_code="error-a",
        mastery_probability=0.4,
        source_as_of={"mastery": NOW - timedelta(seconds=1)},
    )
    return replace(base, **changes)


def model() -> ProbabilisticMisconceptionModel:
    return ProbabilisticMisconceptionModel(
        catalogue_version="provisional-misconceptions-v1",
        error_likelihoods={"error-a": {"m-a": 4.0}},
        class_priors={"m-a": 0.5, "m-b": 0.45},
        abstain_threshold=0.6,
    )


def candidates() -> tuple[SupportCandidate, ...]:
    return (
        SupportCandidate(
            ActionId("a-hint"),
            SupportActionType.CONCEPTUAL_HINT,
            ("si",),
            ("opaque-skill-1",),
            ("m-a",),
            True,
        ),
        SupportCandidate(
            ActionId("b-worked"),
            SupportActionType.SIMILAR_WORKED_EXAMPLE,
            ("si",),
            ("opaque-skill-1",),
            ("m-a",),
            True,
        ),
        SupportCandidate(
            ActionId("blocked"),
            SupportActionType.FULL_EXPLANATION,
            ("en",),
            ("opaque-skill-1",),
            (),
            False,
        ),
    )


def equivalence() -> EquivalenceEvidence:
    return EquivalenceEvidence(
        primary_skill_match=True,
        cognitive_operation_match=True,
        difficulty_band_match=True,
        response_format_match=True,
        language_reviewed=True,
        expected_time_match=True,
        unseen_verification_item=True,
        answer_overlap_acceptable=True,
        equivalence_version="provisional-equivalence-v1",
        approved=True,
    )


def gain_input(**changes) -> IndependenceGainInput:
    base = IndependenceGainInput(
        baseline_score=0.25,
        verification_score=0.75,
        baseline_support_state=EvidenceSupportState.UNSUPPORTED,
        verification_support_state=EvidenceSupportState.UNSUPPORTED,
        equivalence=equivalence(),
        support_delivered=True,
        support_completed=True,
        support_withdrawn_at=NOW,
        verification_started_at=NOW + timedelta(seconds=1),
        idle_time_ms=100,
        maximum_idle_time_ms=1000,
    )
    return replace(base, **changes)


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


def test_misconception_models_normalize_and_abstain() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    prediction = model().predict(snapshot)
    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.confidence > 0.6
    assert not prediction.abstained
    missing = model().predict(
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


def test_policy_logs_all_candidates_propensities_and_seed() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = model().predict(snapshot)
    policy = SafeSupportPolicy(catalogue_version=CatalogueVersion("support-v1"))
    first = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=candidates(),
        language="si",
        seed=7,
        decided_at=NOW,
    )
    second = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=candidates(),
        language="si",
        seed=7,
        decided_at=NOW,
    )
    assert first == second
    assert len(first.candidates) == 3
    assert sum(item.propensity for item in first.candidates if item.eligible) == 1
    assert all(item.propensity == 0 for item in first.candidates if not item.eligible)
    assert first.random_seed == 7


class Scorer:
    version = "learned-candidate-v1"

    def score(self, snapshot, belief, available):
        return {
            candidate.action_id: (0.8, 0.1) if candidate.action_id == "b-worked" else (0.2, 0.2)
            for candidate in available
        }


def test_policy_shadow_and_cold_start_do_not_control_delivery() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    belief = model().predict(snapshot)
    policy = SafeSupportPolicy(
        catalogue_version=CatalogueVersion("support-v1"), minimum_learned_evidence=10
    )
    shadow = policy.decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=belief,
        candidates=candidates(),
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
        candidates=candidates(),
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


def test_learned_policy_seeded_selection() -> None:
    snapshot = FeatureBuilder().build(feature_input())
    decision = SafeSupportPolicy(catalogue_version=CatalogueVersion("support-v1")).decide(
        episode_id=EPISODE,
        snapshot=snapshot,
        belief=model().predict(snapshot),
        candidates=candidates(),
        language="si",
        seed=11,
        decided_at=NOW,
        mode=DecisionMode.LEARNED,
        learned_policy=Scorer(),
        evidence_count=100,
    )
    assert decision.selected_action_id == "b-worked"
    assert decision.random_seed == 11


def test_independence_gain_formula_and_invalid_reasons() -> None:
    valid = calculate_independence_gain(gain_input())
    assert valid.raw_gain == 0.5
    assert not valid.invalid_reasons
    invalid = calculate_independence_gain(
        gain_input(
            verification_support_state=EvidenceSupportState.SUPPORTED,
            equivalence=replace(equivalence(), unseen_verification_item=False),
            intervening_support=True,
        )
    )
    assert invalid.raw_gain is None
    assert set(invalid.invalid_reasons) == {
        "VERIFICATION_NOT_UNSUPPORTED",
        "VERIFICATION_ITEM_PREVIOUSLY_SEEN",
        "INTERVENING_SUPPORT",
    }


def dataset_rows() -> list[DatasetRow]:
    return [
        DatasetRow(f"e{i}", f"l{i}", {"score": i / 10}, "a-hint", 0.5, 0.5, True)
        for i in range(10)
    ]


def test_learner_splits_reproducible_and_disjoint() -> None:
    first = DatasetManifest.build(
        dataset_rows(), dataset_id="synthetic-v1", split_seed=42, synthetic=True
    )
    second = DatasetManifest.build(
        dataset_rows(), dataset_id="synthetic-v1", split_seed=42, synthetic=True
    )
    assert first == second
    first.assert_no_learner_leakage()
    bad = replace(first, learner_splits={"train": ("l1",), "test": ("l1",)})
    with pytest.raises(ValueError, match="multiple"):
        bad.assert_no_learner_leakage()


def test_off_policy_evaluation_requires_propensities() -> None:
    rows = dataset_rows()
    report = evaluate_logged_policy(
        rows, {(row.episode_id, row.action_id): 0.5 for row in rows}
    )
    assert report.ips == pytest.approx(0.5)
    with pytest.raises(ValueError, match="positive logged propensities"):
        evaluate_logged_policy(
            [replace(rows[0], propensity=None)], {("e0", "a-hint"): 1.0}
        )


def test_calibration_and_slice_report_uses_supplied_labels() -> None:
    report = evaluate_classification(
        [
            {
                "label": "m-a",
                "probabilities": {"m-a": 0.8, "unknown/other": 0.2},
                "abstained": False,
                "skill_id": "opaque-skill-1",
            },
            {
                "label": "unknown/other",
                "probabilities": {"m-a": 0.4, "unknown/other": 0.6},
                "abstained": True,
                "skill_id": "opaque-skill-2",
            },
        ]
    )
    assert report.sample_count == 2
    assert report.accuracy == 0.5
    assert report.abstention_rate == 0.5
    assert report.slices["opaque-skill-1"]["sample_count"] == 1


def test_artifact_hash_approval_and_rollback() -> None:
    manifest = DatasetManifest.build(
        dataset_rows(), dataset_id="synthetic-v1", split_seed=42, synthetic=True
    )
    first = ModelArtifactBundle.create(
        model_name="misconception",
        model_version="candidate-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v1",
        manifest=manifest,
        seed=42,
        parameters={"weights": [0.1, 0.2]},
    )
    second = ModelArtifactBundle.create(
        model_name="misconception",
        model_version="candidate-v2",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v1",
        manifest=manifest,
        seed=43,
        parameters={"weights": [0.2, 0.3]},
    )
    first.verify()
    with pytest.raises(ValueError, match="hash mismatch"):
        replace(first, parameters={"weights": [9]}).verify()
    registry = ApprovalGatedArtifactRegistry()
    registry.register(first)
    registry.register(second)
    with pytest.raises(PermissionError):
        registry.activate(
            model_name="misconception",
            artifact_sha256=first.artifact_sha256,
            approved=False,
        )
    registry.activate(
        model_name="misconception",
        artifact_sha256=second.artifact_sha256,
        approved=True,
        approver="synthetic-test-approver",
        approved_at=NOW,
    )
    registry.rollback(
        model_name="misconception",
        artifact_sha256=first.artifact_sha256,
        approved=True,
        approver="synthetic-test-approver",
        approved_at=NOW,
    )
    assert registry.active("misconception") == first


def test_offline_training_is_reproducible_and_train_split_only() -> None:
    rows = [replace(row, label="m-a" if index % 2 else "m-b") for index, row in enumerate(dataset_rows())]
    manifest = DatasetManifest.build(
        rows, dataset_id="synthetic-v1", split_seed=42, synthetic=True
    )
    first = train_frequency_candidate(
        rows,
        manifest=manifest,
        model_name="misconception-baseline",
        model_version="candidate-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v1",
        seed=42,
    )
    second = train_frequency_candidate(
        rows,
        manifest=manifest,
        model_name="misconception-baseline",
        model_version="candidate-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v1",
        seed=42,
    )
    assert first == second
    assert sum(first.parameters["class_priors"].values()) == pytest.approx(1.0)


def test_synthetic_generator_is_seeded_and_covers_required_cases() -> None:
    first = generate_synthetic_episodes(seed=5)
    assert first == generate_synthetic_episodes(seed=5)
    assert all(episode.synthetic for episode in first)
    assert any(not episode.learner_state_available for episode in first)
    assert any(not episode.verification_valid for episode in first)
    assert any(episode.evidence_count == 0 for episode in first)


def test_default_prototype_dataset_is_explicitly_synthetic_and_usable() -> None:
    rows = load_default_prototype_rows()
    assert len(rows) == 10
    assert all(row.learner_id.startswith("synthetic-default-") for row in rows)
    manifest = DatasetManifest.build(
        rows,
        dataset_id="default-synthetic-prototype-v1",
        split_seed=42,
        synthetic=True,
    )
    assert manifest.synthetic
    manifest.assert_no_learner_leakage()


def test_fake_expert_review_dataset_exercises_independent_review_workflow() -> None:
    payload = load_fake_expert_reviews()
    assert payload["synthetic"] is True
    assert payload["authorized_research_evidence"] is False
    cases = payload["cases"]
    assert len(cases) == 4
    assert all(len(case["independent_reviews"]) == 2 for case in cases)
    assert any(
        len({review["expert_misconception_label"] for review in case["independent_reviews"]})
        > 1
        for case in cases
    )


def test_seeded_end_to_end_feature_inference_decision_and_outcome() -> None:
    pipeline = ThreeModelPipeline(
        misconception_model=model(),
        support_catalogue_version=CatalogueVersion("support-v1"),
    )
    decision = pipeline.decide(
        episode_id=EPISODE,
        features=feature_input(),
        candidates=candidates(),
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

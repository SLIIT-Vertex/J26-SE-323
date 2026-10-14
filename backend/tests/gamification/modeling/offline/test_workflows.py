import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.gamification.modeling.misconception_inference.evaluation import (
    evaluate_classification,
)
from app.gamification.modeling.misconception_inference.training import (
    train_frequency_candidate,
)
from app.gamification.modeling.offline import DatasetManifest
from app.gamification.modeling.shared.artifact_registry import (
    ApprovalGatedArtifactRegistry,
    ModelArtifactBundle,
)
from app.gamification.modeling.support_selection.evaluation import evaluate_logged_policy
from app.gamification.modeling.synthetic.datasets import (
    EXPERT_REVIEW_SIMULATION,
    load_dataset_rows,
    load_default_prototype_rows,
    load_fake_expert_review_rows,
    load_fake_expert_review_simulation,
)
from tests.gamification.modeling.fixtures import NOW, dataset_rows


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
    rows = [
        replace(row, label="m-a" if index % 2 else "m-b")
        for index, row in enumerate(dataset_rows())
    ]
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


def test_fake_expert_review_simulation_exercises_independent_review_workflow() -> None:
    payload = load_fake_expert_review_simulation()
    assert payload["synthetic"] is True
    assert payload["authorized_research_evidence"] is False
    cases = payload["cases"]
    assert len(cases) == 8
    assert all(len(case["independent_reviews"]) == 2 for case in cases)
    assert any(
        len({review["expert_misconception_label"] for review in case["independent_reviews"]})
        > 1
        for case in cases
    )


def test_fake_expert_review_rows_are_model_ready_and_reference_catalogue_items() -> None:
    payload = load_fake_expert_review_simulation()
    rows = load_fake_expert_review_rows()
    assert load_dataset_rows(EXPERT_REVIEW_SIMULATION) == rows
    assert len(rows) == len(payload["cases"])
    assert all(row.learner_id.startswith("synthetic-expert-sim-") for row in rows)
    assert all(row.label for row in rows)

    item_path = (
        Path(__file__).resolve().parents[5]
        / "data"
        / "gamification"
        / "grade5-curriculum-game-dataset"
        / "v2"
        / "game_items.jsonl"
    )
    catalogue_items = {
        item["item_id"]: item
        for item in (json.loads(line) for line in item_path.read_text().splitlines())
    }
    assert {case["item_id"] for case in payload["cases"]} <= set(catalogue_items)
    for case in payload["cases"]:
        source = catalogue_items[case["item_id"]]
        question = case["question_item"]
        assert case["game_id"] == source["game_id"]
        assert case["subject"] == source["subject"]
        assert case["language"] == source["language"]
        assert question["prompt"] == (source["prompt_en"] or source["prompt_primary"])
        assert question["stimulus"] == (source["stimulus_en"] or source["stimulus_primary"])
        assert case["provisional_skill_id"] == source["primary_skill_candidate_id"]
        assert question["options"] == source["options"]
        assert question["correct_answer"] == source["correct_answers"][0]

    manifest = DatasetManifest.build(
        rows,
        dataset_id=str(payload["dataset_id"]),
        split_seed=42,
        synthetic=True,
    )
    candidate = train_frequency_candidate(
        rows,
        manifest=manifest,
        model_name="misconception-baseline",
        model_version="synthetic-fallback-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v1",
        seed=42,
    )
    candidate.verify()
    assert candidate.parameters["class_priors"]
